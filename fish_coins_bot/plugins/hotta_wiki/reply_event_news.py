import pytz
from nonebot import on_notice, on_command
from nonebot.adapters.onebot.v11 import Bot, Event, PokeNotifyEvent, GroupMessageEvent
from nonebot.rule import Rule

from nonebot.adapters import Message
from nonebot.params import CommandArg
from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot import get_bot,require
from nonebot.log import logger
from datetime import datetime

from fish_coins_bot.database.hotta.event_news import EventNews
from fish_coins_bot.utils.dynamics_config import load_group_ids
from fish_coins_bot.utils.image_utils import make_event_news_end_image
from fish_coins_bot.utils.model_utils import days_diff_from_now

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler


def is_group_chat(event) -> bool:
    return isinstance(event, GroupMessageEvent)

event_news = on_command(
    "活动资讯",
    rule=Rule(is_group_chat),
    aliases={"近期活动", "塔塔活动"},
    priority=10,
    block=True,
)

@event_news.handle()
async def event_news_handle_function(args: Message = CommandArg()):
    image_path = Path("/app/screenshots/common") / "event-news.png"

    # 检查文件是否存在
    if image_path.exists():
        # 发送图片
        image_message = MessageSegment.image(f"file://{image_path}")
        await event_news.finish(image_message)
    else:
        await event_news.finish("哇哦,图片找不到了~")




@scheduler.scheduled_job("cron", hour=12, minute=30, second=0, id="event_news_end_scheduled")
async def event_news_end_scheduled():

    group_ids = load_group_ids("hotta")
    if not group_ids:
        logger.warning("[hotta_wiki] dynamics_list.json 的 hotta 群列表为空，跳过活动结束提醒。")
        return

    tz = pytz.timezone("Asia/Shanghai")
    current_time = datetime.now(tz)

    are_info_list = await EventNews.filter(
        del_flag="0",
        news_start__lte=current_time,
        news_end__gte=current_time
    ).order_by("news_end").values(
        "news_title",
        "news_start",
        "news_end"
    )

    is_need_send = False

    for info in are_info_list:
        if days_diff_from_now(info["news_end"]) <= 7:
            is_need_send = True

    await make_event_news_end_image()

    bot = get_bot()

    image_path = Path("/app/screenshots/common") / "event-news-end.png"
    image_message = MessageSegment.image(f"file://{image_path}")

    # 检查文件是否存在
    if image_path.exists() and is_need_send:
        # 发送图片
        for group_id in group_ids:
            try:
                await bot.send_group_msg(group_id=int(group_id), message=image_message)
            except Exception as exc:
                logger.error(f"[hotta_wiki] 活动结束提醒发送失败 group={group_id}: {exc}")
