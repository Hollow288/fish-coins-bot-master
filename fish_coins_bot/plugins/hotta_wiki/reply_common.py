from nonebot import on_notice
from nonebot.adapters.onebot.v11 import Bot, Event, PokeNotifyEvent
from nonebot.rule import Rule
from nonebot.log import logger

def is_poke_me(event: Event) -> bool:
    return isinstance(event, PokeNotifyEvent) and event.target_id == event.self_id and event.group_id is not None

poke_me = on_notice(rule=Rule(is_poke_me))

@poke_me.handle()
async def handle_poke_event(bot: Bot, event: PokeNotifyEvent):
    user_id = event.user_id
    group_id = event.group_id
    logger.warning("=============bot================")
    logger.warning(bot)
    logger.warning(event)
    logger.warning("=============bot end================")
    # 发送回复消息
    await bot.send_group_msg(group_id=group_id, message=f"{user_id} 拍了拍我的肩膀")