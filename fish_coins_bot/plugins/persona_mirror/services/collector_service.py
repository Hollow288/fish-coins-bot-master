from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent

from ..models import PersonaAsset, PersonaMessage, PersonaTarget
from ..utils import (
    build_feature_json,
    datetime_from_timestamp,
    message_segments_to_list,
    normalize_text,
    render_segments_as_text,
)
from .context_service import (
    check_target_mentioned_recently,
    get_recent_context_structured,
    is_last_message_from_user,
)
from .persona_service import get_effective_trigger_keywords


def _safe_reply_sender_name(reply) -> str:
    if not reply or not getattr(reply, "sender", None):
        return ""
    sender = reply.sender
    return getattr(sender, "card", "") or getattr(sender, "nickname", "") or str(getattr(sender, "user_id", ""))


def _classify_scene(
    event: GroupMessageEvent,
    target: PersonaTarget,
    is_continuation: bool,
    exclude_message_id: str | None = None,
) -> str:
    """根据上下文推断目标这条消息的场景类型。"""
    if is_continuation:
        return "连续发言"

    if getattr(event, "reply", None):
        return "回复他人"

    group_id = str(event.group_id)
    target_aliases = get_effective_trigger_keywords(target)
    was_at, was_mentioned = check_target_mentioned_recently(
        group_id,
        target.target_user_id,
        target_aliases,
        exclude_message_id=exclude_message_id,
    )
    if was_at:
        return "被@后回应"
    if was_mentioned:
        return "被提及后回应"

    return "主动发言"


async def _upsert_face_asset(target_user_id: str, message_ref_id: int, face_id: str) -> None:
    asset = await PersonaAsset.get_or_none(
        target_user_id=target_user_id,
        asset_type="face",
        asset_key=f"face:{face_id}",
    )
    if asset is None:
        await PersonaAsset.create(
            target_user_id=target_user_id,
            message_ref_id=message_ref_id,
            asset_type="face",
            asset_key=f"face:{face_id}",
            face_id=face_id,
            used_count=1,
        )
        return

    asset.used_count += 1
    asset.message_ref_id = message_ref_id
    await asset.save()


async def collect_message_event(event: GroupMessageEvent | PrivateMessageEvent) -> PersonaMessage | None:
    target_user_id = str(event.user_id)
    target = await PersonaTarget.get_or_none(target_user_id=target_user_id, enabled=True)
    if target is None:
        return None

    raw_segments = message_segments_to_list(event.message)
    plain_text = event.get_plaintext().strip()
    normalized_text = normalize_text(plain_text)

    context_json: list[dict] = []
    scene_type = "主动发言"
    reply_to_text: str | None = None
    reply_to_user_name: str | None = None
    is_continuation = False

    if isinstance(event, GroupMessageEvent):
        group_id = str(event.group_id)
        current_message_id = str(event.message_id)

        # 当前消息已提前写入缓存，采集时要显式排除自己，避免把自己当成发言前上下文。
        context_json = get_recent_context_structured(
            group_id,
            limit=5,
            exclude_message_id=current_message_id,
        )

        # 连续发言检测也要排除当前消息本身，只看它之前的最后一条消息。
        is_continuation = is_last_message_from_user(
            group_id,
            target_user_id,
            exclude_message_id=current_message_id,
        )

        # 回复信息提取
        reply = getattr(event, "reply", None)
        if reply and getattr(reply, "message", None):
            reply_to_text = render_segments_as_text(message_segments_to_list(reply.message))
            reply_to_user_name = _safe_reply_sender_name(reply)

        # 场景分类
        scene_type = _classify_scene(
            event,
            target,
            is_continuation,
            exclude_message_id=current_message_id,
        )

    feature_json = build_feature_json(raw_segments, plain_text)
    chat_type = "group" if isinstance(event, GroupMessageEvent) else "private"
    group_id_val = str(event.group_id) if isinstance(event, GroupMessageEvent) else None
    message_time = datetime_from_timestamp(getattr(event, "time", None))

    message_record = await PersonaMessage.create(
        target_user_id=target_user_id,
        group_id=group_id_val,
        chat_type=chat_type,
        platform_message_id=str(event.message_id),
        plain_text=plain_text or None,
        normalized_text=normalized_text or None,
        raw_segments_json=raw_segments,
        feature_json=feature_json,
        scene_type=scene_type,
        reply_to_text=reply_to_text,
        reply_to_user_name=reply_to_user_name,
        is_continuation=is_continuation,
        context_json=context_json,
        message_time=message_time,
    )

    target.total_collected_messages += 1
    sender_name = event.sender.card or event.sender.nickname
    if sender_name and not target.target_name:
        target.target_name = sender_name
    await target.save()

    for segment in raw_segments:
        segment_type = segment.get("type")
        segment_data = segment.get("data", {})
        if segment_type == "face" and segment_data.get("id") is not None:
            await _upsert_face_asset(target_user_id, message_record.id, str(segment_data.get("id")))

    return message_record
