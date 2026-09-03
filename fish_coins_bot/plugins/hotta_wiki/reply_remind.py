from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot import get_bot,require
from nonebot.log import logger
from io import BytesIO

from fish_coins_bot.utils.dynamics_config import load_group_ids

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

@scheduler.scheduled_job("cron", day="last", hour=18, minute=30, second=0, id="home_special_voucher")
async def home_special_voucher():
    group_ids = load_group_ids("hotta")
    if not group_ids:
        logger.warning("[hotta_wiki] dynamics_list.json 的 hotta 群列表为空，跳过特殊凭证提醒。")
        return

    bot = get_bot()

    image_path = Path(__file__).parent.parent.parent / "img" / "special_voucher.png"

    # 检查文件是否存在
    if image_path.exists():
        buffer = BytesIO()
        with image_path.open("rb") as f:
            buffer.write(f.read())
        buffer.seek(0)

        image_message = MessageSegment.image(buffer)
        # 发送图片
        for group_id in group_ids:
            try:
                await bot.send_group_msg(group_id=int(group_id), message=image_message)
            except Exception as exc:
                logger.error(f"[hotta_wiki] 特殊凭证提醒发送失败 group={group_id}: {exc}")
