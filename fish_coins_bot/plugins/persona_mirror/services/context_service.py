from collections import defaultdict, deque
from typing import Any

from nonebot.adapters.onebot.v11 import GroupMessageEvent

from ..config import get_plugin_config
from ..utils import datetime_from_timestamp, message_segments_to_list, normalize_text, render_segments_as_text


_GROUP_MESSAGE_CACHE: dict[str, deque[dict[str, Any]]] = defaultdict(
    lambda: deque(maxlen=max(get_plugin_config().recent_context_size * 4, 20))
)


def _get_cached_messages(
    group_id: str | int,
    exclude_message_id: str | None = None,
) -> list[dict[str, Any]]:
    cached = list(_GROUP_MESSAGE_CACHE.get(str(group_id), []))
    if exclude_message_id is None:
        return cached
    return [item for item in cached if item["message_id"] != str(exclude_message_id)]


def _safe_sender_name(event: GroupMessageEvent) -> str:
    return event.sender.card or event.sender.nickname or str(event.user_id)


def _safe_reply_sender_name(reply) -> str:
    if not reply or not getattr(reply, "sender", None):
        return ""
    sender = reply.sender
    return getattr(sender, "card", "") or getattr(sender, "nickname", "") or str(getattr(sender, "user_id", ""))


def record_group_message_context(event: GroupMessageEvent) -> None:
    group_id = str(event.group_id)
    raw_segments = message_segments_to_list(event.message)
    rendered_text = render_segments_as_text(raw_segments)
    if not rendered_text:
        rendered_text = normalize_text(event.get_plaintext())

    reply_message = getattr(event, "reply", None)
    reply_rendered_text = ""
    reply_to_user_id = ""
    if reply_message:
        reply_rendered_text = render_segments_as_text(message_segments_to_list(reply_message.message))
        if getattr(reply_message, "sender", None):
            reply_to_user_id = str(getattr(reply_message.sender, "user_id", "") or "")

    _GROUP_MESSAGE_CACHE[group_id].append(
        {
            "group_id": group_id,
            "message_id": str(event.message_id),
            "user_id": str(event.user_id),
            "sender_name": _safe_sender_name(event),
            "rendered_text": rendered_text,
            "raw_segments": raw_segments,
            "reply_to_user_id": reply_to_user_id,
            "reply_to_sender_name": _safe_reply_sender_name(reply_message),
            "reply_rendered_text": reply_rendered_text,
            "timestamp": datetime_from_timestamp(getattr(event, "time", None)).isoformat(),
        }
    )


def get_recent_context_texts(
    group_id: str | int,
    limit: int = 3,
    exclude_message_id: str | None = None,
) -> list[str]:
    """获取最近几条群消息的纯文本，用于给 collector 存发言前上下文。"""
    cached = _get_cached_messages(group_id, exclude_message_id=exclude_message_id)
    recent = cached[-limit:]
    return [
        f"{item['sender_name']}: {item['rendered_text']}"
        for item in recent
        if item.get("rendered_text")
    ]


def get_recent_context_structured(
    group_id: str | int,
    limit: int = 5,
    exclude_message_id: str | None = None,
) -> list[dict[str, str]]:
    """获取最近几条群消息的结构化数据，用于给 collector 存发言前上下文。"""
    cached = _get_cached_messages(group_id, exclude_message_id=exclude_message_id)
    recent = cached[-limit:]
    return [
        {
            "user_id": item["user_id"],
            "name": item["sender_name"],
            "text": item["rendered_text"],
        }
        for item in recent
        if item.get("rendered_text")
    ]


def check_target_mentioned_recently(
    group_id: str | int,
    target_user_id: str,
    target_aliases: list[str],
    lookback: int = 3,
    exclude_message_id: str | None = None,
) -> tuple[bool, bool]:
    """检查目标最近是否被 @ 或被提到名字。返回 (was_at, was_mentioned_by_name)。"""
    cached = _get_cached_messages(group_id, exclude_message_id=exclude_message_id)
    recent = cached[-lookback:]
    alias_set = {a for a in target_aliases if a}

    was_at = False
    was_mentioned = False

    for item in recent:
        if item["user_id"] == target_user_id:
            continue
        for seg in item.get("raw_segments", []):
            if seg.get("type") == "at" and str(seg.get("data", {}).get("qq", "")) == target_user_id:
                was_at = True
                break
        text = item.get("rendered_text", "")
        if alias_set and any(alias in text for alias in alias_set):
            was_mentioned = True

    return was_at, was_mentioned


def is_last_message_from_user(
    group_id: str | int,
    user_id: str,
    exclude_message_id: str | None = None,
) -> bool:
    """判断该群最后一条缓存消息是否来自指定用户（用于检测连续发言）。"""
    cached = _get_cached_messages(group_id, exclude_message_id=exclude_message_id)
    if not cached:
        return False
    return cached[-1]["user_id"] == str(user_id)


def get_recent_group_context(
    group_id: str | int,
    target_user_id: str,
    target_aliases: list[str],
    limit: int | None = None,
    exclude_message_id: str | None = None,
) -> list[dict[str, Any]]:
    config = get_plugin_config()
    effective_limit = limit or config.recent_context_size
    cached_messages = _get_cached_messages(group_id, exclude_message_id=exclude_message_id)

    cached_messages = cached_messages[-effective_limit:]
    alias_set = {alias for alias in target_aliases if alias}
    context_messages: list[dict[str, Any]] = []

    for item in cached_messages:
        text = item.get("rendered_text", "")
        if not text:
            continue

        is_target_user = item["user_id"] == target_user_id
        mentions_target_user = any(alias in text for alias in alias_set) if alias_set else False
        context_messages.append(
            {
                "message_id": item["message_id"],
                "speaker_id": item["user_id"],
                "speaker_name": item["sender_name"],
                "is_target_user": is_target_user,
                "mentions_target_user": mentions_target_user,
                "reply_to_target_user": item.get("reply_to_user_id") == target_user_id,
                "reply_to_sender_name": item.get("reply_to_sender_name", ""),
                "reply_preview": item.get("reply_rendered_text", ""),
                "text": text,
                "timestamp": item.get("timestamp", ""),
            }
        )

    return context_messages
