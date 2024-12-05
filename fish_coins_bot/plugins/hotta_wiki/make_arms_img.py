
from nonebot import get_bot,require

from fish_coins_bot.utils.image_utils import make_all_arms_image

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

@scheduler.scheduled_job("cron", hour=3, minute=30, second=0, id="arms_img_scheduled")
async def arms_img_scheduled():
    await make_all_arms_image()