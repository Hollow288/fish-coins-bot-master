from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent

from ..models import PersonaAsset, PersonaMessage, PersonaTarget
from ..utils import (
    build_feature_json,
    datetime_from_timestamp,
    message_segments_to_list,
    normalize_text,
)
from .context_service import get_recent_context_texts


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

    # 在存特征前，先抓取目标发言前的群聊上下文
    context_before: list[str] | None = None
    if isinstance(event, GroupMessageEvent):
        context_before = get_recent_context_texts(str(event.group_id), limit=3)

    feature_json = build_feature_json(raw_segments, plain_text, context_before=context_before)
    chat_type = "group" if isinstance(event, GroupMessageEvent) else "private"
    group_id = str(event.group_id) if isinstance(event, GroupMessageEvent) else None
    message_time = datetime_from_timestamp(getattr(event, "time", None))

    message_record = await PersonaMessage.create(
        target_user_id=target_user_id,
        group_id=group_id,
        chat_type=chat_type,
        platform_message_id=str(event.message_id),
        plain_text=plain_text or None,
        normalized_text=normalized_text or None,
        raw_segments_json=raw_segments,
        feature_json=feature_json,
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
