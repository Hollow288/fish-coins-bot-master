
from nonebot import get_bot,require

from fish_coins_bot.utils.image_utils import make_all_willpower_image

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

@scheduler.scheduled_job("cron", hour=4, minute=0, second=0, id="willpower_img_scheduled")
async def willpower_img_scheduled():
    await make_all_willpower_image()