import time

from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
from nonebot.log import logger

from .config import get_auto_reply_cooldown, get_plugin_config
from .models import PersonaMessage, PersonaProfileState, PersonaTarget
from .services.context_service import get_recent_group_context
from .services.persona_service import get_effective_trigger_keywords
from .services.summarizer_service import generate_reply
from .utils import message_segments_to_list, normalize_text, now_shanghai


auto_persona_reply = on_message(priority=20, block=False)

# 内存缓存：避免每条群消息都查库
_target_cache: list[PersonaTarget] = []
_target_cache_ts: float = 0.0
_TARGET_CACHE_TTL: float = 60.0  # 缓存 60 秒


async def _get_active_targets() -> list[PersonaTarget]:
    global _target_cache, _target_cache_ts
    now = time.monotonic()
    if now - _target_cache_ts > _TARGET_CACHE_TTL:
        _target_cache = await PersonaTarget.filter(enabled=True, auto_reply_enabled=True)
        _target_cache_ts = now
    return _target_cache


def invalidate_target_cache() -> None:
    """供其他模块在修改 target 状态后调用。"""
    global _target_cache_ts
    _target_cache_ts = 0.0


def _extract_trigger_payload(event: GroupMessageEvent, target: PersonaTarget) -> dict | None:
    config = get_plugin_config()
    raw_segments = message_segments_to_list(event.message)
    at_matched = any(
        segment.get("type") == "at" and str(segment.get("data", {}).get("qq", "")) == target.target_user_id
        for segment in raw_segments
    )
    reply_to_target = False
    if getattr(event, "reply", None) and getattr(event.reply, "sender", None):
        reply_to_target = str(getattr(event.reply.sender, "user_id", "") or "") == target.target_user_id

    plain_text = event.get_plaintext().strip()
    keywords = get_effective_trigger_keywords(target)
    matched_keywords = [
        keyword
        for keyword in keywords
        if len(keyword) >= config.auto_reply_min_keyword_length and keyword in plain_text
    ]

    if not at_matched and not reply_to_target and not matched_keywords:
        return None

    intent_parts: list[str] = []
    for segment in raw_segments:
        segment_type = segment.get("type")
        data = segment.get("data", {})
        if segment_type == "at" and str(data.get("qq", "")) == target.target_user_id:
            continue
        if segment_type == "text":
            intent_parts.append(str(data.get("text", "")))
        elif segment_type == "face":
            intent_parts.append(f"[face:{data.get('id', '')}]")
        elif segment_type == "image":
            intent_parts.append("[image]")

    raw_intent = normalize_text("".join(intent_parts))
    cleaned_intent = raw_intent
    for keyword in sorted(matched_keywords, key=len, reverse=True):
        cleaned_intent = cleaned_intent.replace(keyword, " ")
    cleaned_intent = normalize_text(cleaned_intent)

    if not cleaned_intent and not raw_intent and not at_matched and not reply_to_target:
        return None

    score = (
        (120 if at_matched else 0)
        + (100 if reply_to_target else 0)
        + len(matched_keywords) * 10
        + sum(len(keyword) for keyword in matched_keywords)
    )
    return {
        "target": target,
        "intent_text": cleaned_intent,
        "raw_intent_text": raw_intent,
        "score": score,
        "at_matched": at_matched,
        "reply_to_target": reply_to_target,
        "matched_keywords": matched_keywords,
    }


@auto_persona_reply.handle()
async def handle_auto_persona_reply(bot: Bot, event: GroupMessageEvent) -> None:
    if not isinstance(event, GroupMessageEvent):
        return
    if str(event.user_id) == str(bot.self_id):
        return

    config = get_plugin_config()
    now = now_shanghai()
    targets = await _get_active_targets()
    candidate_payloads: list[dict] = []

    for target in targets:
        if target.target_user_id == str(event.user_id):
            continue
        cooldown = get_auto_reply_cooldown()
        if target.last_auto_reply_at and cooldown > 0:
            last_auto_reply_at = target.last_auto_reply_at
            if last_auto_reply_at.tzinfo is None:
                last_auto_reply_at = last_auto_reply_at.replace(tzinfo=now.tzinfo)
            diff_seconds = (now - last_auto_reply_at).total_seconds()
            if diff_seconds < cooldown:
                continue

        payload = _extract_trigger_payload(event, target)
        if payload is not None:
            candidate_payloads.append(payload)

    if not candidate_payloads:
        return

    # 批量检查目标在当前群是否有采集过消息（群隔离：防止目标在A群，机器人在B群回复）
    current_group_id = str(event.group_id)
    candidate_user_ids = list({p["target"].target_user_id for p in candidate_payloads})
    targets_in_group = set(
        await PersonaMessage.filter(
            target_user_id__in=candidate_user_ids,
            group_id=current_group_id,
        ).distinct().values_list("target_user_id", flat=True)
    )
    candidate_payloads = [p for p in candidate_payloads if p["target"].target_user_id in targets_in_group]

    if not candidate_payloads:
        return

    # 批量检查画像是否存在且消息量达标
    candidate_user_ids = list({p["target"].target_user_id for p in candidate_payloads})
    existing_profiles = await PersonaProfileState.filter(
        target_user_id__in=candidate_user_ids
    )
    min_msg = config.auto_reply_min_message_count
    qualified_user_ids = {
        ps.target_user_id
        for ps in existing_profiles
        if ps.total_message_count >= min_msg
    }
    candidate_payloads = [p for p in candidate_payloads if p["target"].target_user_id in qualified_user_ids]

    if not candidate_payloads:
        return

    selected = max(candidate_payloads, key=lambda item: item["score"])
    target = selected["target"]
    target_aliases = get_effective_trigger_keywords(target)
    recent_chat_messages = get_recent_group_context(
        group_id=event.group_id,
        target_user_id=target.target_user_id,
        target_aliases=target_aliases,
        limit=config.recent_context_size,
    )
    trigger_reason = {
        "source": "auto_group_trigger",
        "group_id": str(event.group_id),
        "trigger_user_id": str(event.user_id),
        "trigger_user_name": event.sender.card or event.sender.nickname or str(event.user_id),
        "at_target_user": selected["at_matched"],
        "reply_to_target_user": selected["reply_to_target"],
        "matched_keywords": selected["matched_keywords"],
        "raw_trigger_message": selected["raw_intent_text"],
    }

    try:
        result = await generate_reply(
            target,
            selected["intent_text"],
            recent_chat_messages=recent_chat_messages,
            trigger_reason=trigger_reason,
        )
    except Exception as exc:
        logger.error(f"persona_mirror 自动回复失败 {target.target_user_id}: {exc}")
        return

    reply_message = Message(result["reply"])
    face_id = result.get("face_id", "")
    if face_id.isdigit():
        reply_message += MessageSegment.face(int(face_id))

    await bot.send(event, reply_message)

    # 刷新数据库中的 target 记录（缓存的对象可能已过期）
    fresh_target = await PersonaTarget.get_or_none(id=target.id)
    if fresh_target:
        fresh_target.last_auto_reply_at = now
        await fresh_target.save()
    invalidate_target_cache()
