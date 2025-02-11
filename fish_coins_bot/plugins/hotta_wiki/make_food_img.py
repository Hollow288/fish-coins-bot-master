
from nonebot import require

from fish_coins_bot.utils.image_utils import make_food_image

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

@scheduler.scheduled_job("cron", hour=4, minute=30, second=0, id="food_img_scheduled")
async def food_img_scheduled():
    await make_food_image()