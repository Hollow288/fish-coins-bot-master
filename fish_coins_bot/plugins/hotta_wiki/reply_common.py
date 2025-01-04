from nonebot import on_notice, on_command
from nonebot.adapters.onebot.v11 import Bot, Event, PokeNotifyEvent, GroupMessageEvent
from nonebot.rule import Rule, to_me
from nonebot.log import logger
from nonebot.adapters import Message
from nonebot.params import CommandArg
from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment
import pytz
from datetime import datetime

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

    tz = pytz.timezone('Asia/Shanghai')
    utc8_time = datetime.now(tz)
    hour = utc8_time.hour

    if 5 <= hour < 11:
        greeting = "早上好"
    elif 11 <= hour < 13:
        greeting = "中午好"
    elif 13 <= hour < 18:
        greeting = "下午好"
    else:
        greeting = "晚上好"

    # 发送回复消息
    await bot.send_group_msg(group_id=group_id, message=f"执行者{greeting},@我并发送\"帮助\"获取指令菜单哦")



def is_group_chat(event) -> bool:
    return isinstance(event, GroupMessageEvent)

help_menu = on_command(
    "帮助",
    rule=to_me() & Rule(is_group_chat),
    aliases={"help", "菜单"},
    priority=10,
    block=True,
)

@help_menu.handle()
async def help_menu_handle_function(args: Message = CommandArg()):
    image_path = Path("/app/screenshots/common") / "wiki-help.png"

    # 检查文件是否存在
    if image_path.exists():
        # 发送图片
        image_message = MessageSegment.image(f"file://{image_path}")
        await help_menu.finish(image_message)
    else:
        await help_menu.finish("哇哦,图片找不到了~")


event_consultation = on_command(
    "活动资讯",
    rule=Rule(is_group_chat),
    aliases={"近期活动", "塔塔活动"},
    priority=10,
    block=True,
)

@event_consultation.handle()
async def event_consultation_handle_function(args: Message = CommandArg()):
    image_path = Path("/app/screenshots/common") / "event_consultation.png"

    # 检查文件是否存在
    if image_path.exists():
        # 发送图片
        image_message = MessageSegment.image(f"file://{image_path}")
        await event_consultation.finish(image_message)
    else:
        await event_consultation.finish("哇哦,图片找不到了~")