from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger

from .config import get_plugin_config
from .services.storage_service import collect_stickers_from_event


sticker_collector = on_message(priority=1, block=False)


@sticker_collector.handle()
async def handle_sticker_collect(
    bot: Bot, event: GroupMessageEvent | PrivateMessageEvent
) -> None:
    if not isinstance(event, (GroupMessageEvent, PrivateMessageEvent)):
        return
    if str(event.user_id) == str(bot.self_id):
        return
    if not get_plugin_config().collector_enabled:
        return

    try:
        await collect_stickers_from_event(event)
    except Exception as exc:
        logger.error(f"sticker_collector 采集表情包失败: {exc}")
