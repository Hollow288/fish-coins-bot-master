import asyncio
import json
import os
import time
from collections import defaultdict
from io import BytesIO
from pathlib import Path

import httpx
from bilibili_api import user
from nonebot import get_bot, require
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.log import logger
from tortoise import Tortoise

from fish_coins_bot.database import database_config
from fish_coins_bot.database.bilibili.dynamics.models import DynamicsHistory
from fish_coins_bot.database.bilibili.live.models import BotLiveState
from fish_coins_bot.utils.image_utils import screenshot_first_dyn_by_keyword, screenshot_opus_by_id
from fish_coins_bot.utils.model_utils import find_key_word_by_type

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler


VALID_DYNAMIC_TYPES = {
    "DYNAMIC_TYPE_DRAW",
    "DYNAMIC_TYPE_WORD",
    "DYNAMIC_TYPE_ARTICLE",
    "DYNAMIC_TYPE_AV",
}

# 超过此时长的动态视为历史动态, 标记已读后不再推送 (避免补关 UP 或 bot 重启后刷屏)
DYNAMIC_MAX_AGE_SECONDS = 12 * 60


# 旧实现: 逐 UP 调 user.get_dynamics_new() (走 feed/space) + 截 space.bilibili.com 时间线
# 已被 B 站对机房 IP 段精准风控 (HTTP 412), 在云服务器上无法工作, 仅保留作历史参考.
# scheduler 装饰器已移除, 不再定时执行.
async def dynamics_push():
    bot = get_bot()

    with open(Path(__file__).parent / 'dynamics_list.json', 'r',
              encoding='utf-8') as f:
        dynamics_list = json.load(f)

    for uid in dynamics_list:
        u = user.User(int(uid))
        dynamics = await u.get_dynamics_new()

        items = dynamics['items']

        for index, item in enumerate(items):
            type_ = item['type']
            if type_ not in VALID_DYNAMIC_TYPES:
                continue

            id_str = item['id_str']
            exists = await DynamicsHistory.exists(uid=uid, id_str=id_str)
            if not exists:

                pub_ts = int(item['modules']['module_author']['pub_ts'])
                now_ts = int(time.time())
                if now_ts - pub_ts >= DYNAMIC_MAX_AGE_SECONDS:
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


# 新实现: 用 bot 账号登录态调 feed/all 拿整条关注时间线, 按 UID 分组后再走
# www.bilibili.com/opus/{id_str} 截图. 这两个端点目前未被 B 站对机房 IP 风控.
# 前置: bot B 站账号必须关注 dynamics_list.json 里所有要监控的 UP 主, 否则拿不到他们的动态.
@scheduler.scheduled_job("interval", seconds=60, id="dynamics_push_v2")
async def dynamics_push_v2():
    with open(Path(__file__).parent / 'dynamics_list.json', 'r', encoding='utf-8') as f:
        dynamics_list = json.load(f)

    if not dynamics_list:
        return

    try:
        items = await _fetch_following_feed()
    except Exception as e:
        logger.error(f"[动态推送v2] feed/all 拉取异常: {e}")
        return

    if not items:
        return

    items_by_uid: dict[str, list] = defaultdict(list)
    for item in items:
        try:
            mid = str(item["modules"]["module_author"]["mid"])
            items_by_uid[mid].append(item)
        except (KeyError, TypeError):
            continue

    bot = get_bot()
    for uid, group_list in dynamics_list.items():
        user_items = items_by_uid.get(str(uid))
        if not user_items:
            continue

        for item in user_items:
            try:
                await _handle_one_dynamic(bot, uid, item, group_list)
            except Exception as e:
                logger.error(f"[动态推送v2] 处理动态失败 uid={uid}: {e}")


async def _handle_one_dynamic(bot, uid: str, item: dict, group_list: list) -> None:
    type_ = item.get("type")
    if type_ not in VALID_DYNAMIC_TYPES:
        return

    id_str = item.get("id_str")
    if not id_str:
        return

    if await DynamicsHistory.exists(uid=uid, id_str=id_str):
        return

    pub_ts = int(item["modules"]["module_author"]["pub_ts"])
    now_ts = int(time.time())
    if now_ts - pub_ts >= DYNAMIC_MAX_AGE_SECONDS:
        await DynamicsHistory.create(uid=uid, id_str=id_str)
        return

    image = await screenshot_opus_by_id(id_str)
    if image is None:
        logger.warning(f"[动态推送v2] opus 截图失败, 跳过 uid={uid} id={id_str}")
        return

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    message_img = MessageSegment.image(buffer)

    for group_id in group_list:
        try:
            await bot.send_group_msg(group_id=group_id, message=message_img)
        except Exception as e:
            logger.error(f"[动态推送v2] 发送群消息失败 group={group_id} id={id_str}: {e}")

    await DynamicsHistory.create(uid=uid, id_str=id_str)


async def _fetch_following_feed() -> list:
    sessdata = os.getenv("BILI_SESSDATA")
    bili_jct = os.getenv("BILI_JCT")
    buvid3 = os.getenv("BILI_BUVID3")

    if not sessdata:
        logger.warning("[动态推送v2] 未配置 BILI_SESSDATA, 跳过本次拉取")
        return []

    cookies = {
        "SESSDATA": sessdata,
        "bili_jct": bili_jct or "",
        "buvid3": buvid3 or "",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://t.bilibili.com/",
    }

    url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/all"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers, cookies=cookies)

    if resp.status_code != 200:
        logger.error(f"[动态推送v2] feed/all HTTP {resp.status_code}")
        return []

    data = resp.json()
    if data.get("code") != 0:
        logger.error(
            f"[动态推送v2] feed/all 返回 code={data.get('code')} message={data.get('message')!r}"
        )
        return []

    return data.get("data", {}).get("items", []) or []
