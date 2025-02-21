import pytz
from nonebot import on_notice, on_command
from nonebot.adapters.onebot.v11 import Bot, Event, PokeNotifyEvent, GroupMessageEvent
from nonebot.rule import Rule

from nonebot.adapters import Message
from nonebot.params import CommandArg
from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot import get_bot,require
from datetime import datetime

from fish_coins_bot.database.hotta.event_consultation import EventConsultation
from fish_coins_bot.utils.image_utils import make_event_consultation_end_image
from fish_coins_bot.utils.model_utils import days_diff_from_now

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler


def is_group_chat(event) -> bool:
    return isinstance(event, GroupMessageEvent)

event_consultation = on_command(
    "活动资讯",
    rule=Rule(is_group_chat),
    aliases={"近期活动", "塔塔活动"},
    priority=10,
    block=True,
)

@event_consultation.handle()
async def event_consultation_handle_function(args: Message = CommandArg()):
    image_path = Path("/app/screenshots/common") / "event-consultation.png"

    # 检查文件是否存在
    if image_path.exists():
        # 发送图片
        image_message = MessageSegment.image(f"file://{image_path}")
        await event_consultation.finish(image_message)
    else:
        await event_consultation.finish("哇哦,图片找不到了~")




@scheduler.scheduled_job("cron", hour=12, minute=30, second=0, id="event_consultation_end_scheduled")
async def event_consultation_end_scheduled():

    tz = pytz.timezone("Asia/Shanghai")
    current_time = datetime.now(tz)

    are_info_list = await EventConsultation.filter(
        del_flag="0",
        consultation_start__lte=current_time,
        consultation_end__gte=current_time
    ).order_by("consultation_end").values(
        "consultation_title",
        "consultation_start",
        "consultation_end"
    )

    is_need_send = False

    for info in are_info_list:
        if days_diff_from_now(info["consultation_end"]) <= 7:
            is_need_send = True

    await make_event_consultation_end_image()

    bot = get_bot()
    group_list = await bot.get_group_list()

    image_path = Path("/app/screenshots/common") / "event-consultation-end.png"
    image_message = MessageSegment.image(f"file://{image_path}")

    # 检查文件是否存在
    if image_path.exists() and is_need_send:
        # 发送图片
        for group in group_list:
            await bot.send_group_msg(group_id=group['group_id'], message=image_message)