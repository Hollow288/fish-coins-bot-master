import time

from fish_coins_bot.database.bilibili.live.models import BotLiveState
import json
from pathlib import Path
from nonebot import get_bot,require
from fish_coins_bot.utils.image_utils import screenshot_first_dyn_by_keyword
from tortoise import Tortoise
import json
import asyncio
from pathlib import Path
from bilibili_api import user
from fish_coins_bot.database import database_config
from fish_coins_bot.database.bilibili.dynamics.models import DynamicsHistory
from fish_coins_bot.utils.model_utils import find_key_word_by_type
from nonebot.adapters.onebot.v11 import MessageSegment
from io import BytesIO

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

@scheduler.scheduled_job("interval", seconds=60, id="dynamics_push")
async def dynamics_push():
    bot = get_bot()

    valid_types = {"DYNAMIC_TYPE_DRAW", "DYNAMIC_TYPE_WORD", "DYNAMIC_TYPE_ARTICLE", "DYNAMIC_TYPE_AV"}

    with open(Path(__file__).parent / 'dynamics_list.json', 'r',
              encoding='utf-8') as f:
        dynamics_list = json.load(f)

    for uid in dynamics_list:
        u = user.User(int(uid))  # 注意要转换为 int
        dynamics = await u.get_dynamics_new()

        items = dynamics['items']

        for index, item in enumerate(items):
            type_ = item['type']
            # 如果类型不是目标类型之一，跳过
            if type_ not in valid_types:
                continue

            id_str = item['id_str']
            exists = await DynamicsHistory.exists(uid=uid, id_str=id_str)
            if not exists:

                pub_ts = item['modules']['module_author']['pub_ts']
                now_ts = int(time.time())  # 当前时间戳（秒）
                if now_ts - pub_ts >= 2 * 60 * 60:  # 2 小时 = 7200 秒
                    await DynamicsHistory.create(
                        uid=uid,
                        id_str=item['id_str']
                    )
                    continue

                key_word = find_key_word_by_type(type=type_, item=item)
                image = await screenshot_first_dyn_by_keyword(
                    url=f"https://space.bilibili.com/{uid}/dynamic",
                    keyword=key_word,
                    fallback_index=index
                )
                buffer = BytesIO()
                image.save(buffer, format="PNG")
                buffer.seek(0)
                message_img = (
                    MessageSegment.image(buffer)
                )

                group_list = dynamics_list[uid]
                for group_id in group_list:
                    await bot.send_group_msg(group_id=group_id, message=message_img)

                await DynamicsHistory.create(
                    uid=uid,
                    id_str=item['id_str']
                )