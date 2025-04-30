from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot import get_bot,require
from io import BytesIO

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

@scheduler.scheduled_job("cron", day="last", hour=18, minute=30, second=0, id="home_special_voucher")
async def home_special_voucher():
    bot = get_bot()
    group_list = await bot.get_group_list()

    image_path = Path(__file__).parent.parent.parent / "img" / "special_voucher.png"

    # 检查文件是否存在
    if image_path.exists():
        buffer = BytesIO()
        with image_path.open("rb") as f:
            buffer.write(f.read())
        buffer.seek(0)

        image_message = MessageSegment.image(buffer)
        # 发送图片
        for group in group_list:
            await bot.send_group_msg(group_id=group['group_id'], message=image_message)