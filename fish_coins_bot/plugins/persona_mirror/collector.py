from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.log import logger

from .services.context_service import record_group_message_context
from .services.collector_service import collect_message_event


persona_collector = on_message(priority=1, block=False)


@persona_collector.handle()
async def handle_persona_collect(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent) -> None:
    if not isinstance(event, (GroupMessageEvent, PrivateMessageEvent)):
        return
    if str(event.user_id) == str(bot.self_id):
        return

    try:
        if isinstance(event, GroupMessageEvent):
            record_group_message_context(event)
        await collect_message_event(event)
    except Exception as exc:
        logger.error(f"persona_mirror 采集消息失败: {exc}")
