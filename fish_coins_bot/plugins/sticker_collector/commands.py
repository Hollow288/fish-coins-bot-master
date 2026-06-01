"""管理员指令：回复一条表情包消息并发送「拉黑」，把这张表情包全局拉黑，

之后 AI 闲聊挑候选时不再选它。复刻 translate 插件的「回复+指令+priority=10+block」
拦截模式，会在闲聊(priority=99)之前截断。

拦截边界（都放在 Rule 里判断）：只有「管理员 + 被回复消息里确实带表情包」时
本插件才会拦下处理。非管理员、或回复的是纯文本/无图消息时，规则返回 False ——
本插件不介入，消息继续向后传播(闲聊、人格模仿等插件照常处理)。
"""

from nonebot import on_message
from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent,
    Message,
    MessageEvent,
    PrivateMessageEvent,
)
from nonebot.log import logger
from nonebot.rule import Rule

from .config import get_plugin_config
from .services.picker_service import invalidate_pool_cache
from .services.storage_service import find_asset_by_content_url


TRIGGER_TEXT = "拉黑"


def _first_sticker_url(message: Message) -> str | None:
    """从被回复消息里取第一个带 url 的表情包资源（口径同采集器 _iter_sticker_segments）。"""
    for segment in message:
        segment_type = getattr(segment, "type", "")
        if segment_type not in {"image", "mface", "marketface"}:
            continue
        data = dict(getattr(segment, "data", {}) or {})
        url = data.get("url")
        if url:
            return str(url)
    return None


def _is_admin(event: MessageEvent) -> bool:
    # 与本功能「管理员限定」语义一致：ADMIN_ID 未配置(空)时一律视为非管理员。
    admin_ids = get_plugin_config().admin_ids
    return str(getattr(event, "user_id", "")) in admin_ids


def _is_reply_blacklist(event: MessageEvent) -> bool:
    if not isinstance(event, (GroupMessageEvent, PrivateMessageEvent)):
        return False
    if not get_plugin_config().blacklist_enabled:
        return False
    if event.get_plaintext().strip() != TRIGGER_TEXT:
        return False
    # 非管理员 → 不拦截，交给闲聊 / 人格模仿等后续插件
    if not _is_admin(event):
        return False
    reply = getattr(event, "reply", None)
    reply_message = getattr(reply, "message", None)
    if reply_message is None:
        return False
    # 回复的是纯文本 / 无图(不是表情包) → 不拦截，继续向后传播
    return _first_sticker_url(reply_message) is not None


blacklist_sticker = on_message(
    rule=Rule(_is_reply_blacklist),
    priority=10,
    block=True,
)


@blacklist_sticker.handle()
async def handle_blacklist_sticker(
    event: GroupMessageEvent | PrivateMessageEvent,
) -> None:
    # Rule 已保证：管理员 + 被回复消息里带表情包资源
    url = _first_sticker_url(event.reply.message)

    try:
        asset = await find_asset_by_content_url(url)
    except Exception as exc:
        logger.error(f"sticker_collector 拉黑匹配表情包失败: {exc}")
        return

    if asset is None:
        return

    asset.is_blacklisted = True
    await asset.save(update_fields=["is_blacklisted", "last_seen_at"])
    invalidate_pool_cache()
    logger.info(f"sticker_collector 管理员 {event.user_id} 拉黑表情包 #{asset.id}")
    await blacklist_sticker.finish("已拉黑，之后不会再用它回复了。")
