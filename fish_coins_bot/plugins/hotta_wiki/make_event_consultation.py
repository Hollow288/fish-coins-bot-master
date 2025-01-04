
from nonebot import get_bot,require

from fish_coins_bot.utils.image_utils import make_event_consultation

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

@scheduler.scheduled_job("cron", hour="0,5,12", minute=5, second=0, id="event_consultation_scheduled")
async def event_consultation_scheduled():
    await make_event_consultation()
