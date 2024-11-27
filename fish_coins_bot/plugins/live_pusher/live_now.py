from fish_coins_bot.database.models import BotLiveState
import httpx
from nonebot.log import logger
from fish_coins_bot.utils.image_utils import make_live_image
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot import get_bot,require
from io import BytesIO

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

@scheduler.scheduled_job("interval", seconds=10, id="live_scheduled")
async def live_scheduled():
    bot = get_bot()
    all_records = await BotLiveState.all().filter(del_flag="0")

    allowed_status = {"0", "1", "2"}  # 允许的状态集合

    # 遍历所有记录并发送 HTTP GET 请求
    async with httpx.AsyncClient() as client:
        for record in all_records:
            params_room_info = {"id": record.live_id}

            # 添加请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
            }

            try:
                response_room_info = await client.get(
                    "https://api.live.bilibili.com/room/v1/Room/get_info",
                    params=params_room_info,
                    headers=headers,
                )

                # 检查响应状态码
                if response_room_info.status_code == 200:
                    response_room_data = response_room_info.json()

                    live_status = str(response_room_data["data"]["live_status"])

                    if live_status == str(record.live_state) or live_status not in allowed_status:
                        continue

                    if live_status == '0':
                        # 下波
                        await BotLiveState.filter(id=record.id).update(live_state=live_status)
                    elif live_status == '1':

                        params_host_info = {"mid": response_room_data["data"]["uid"]}

                        response_host_info = await client.get(
                            "https://api.bilibili.com/x/web-interface/card",
                            params=params_host_info,
                            headers=headers,
                        )

                        if response_host_info.status_code == 200:
                            response_host_data = response_host_info.json()
                            # 开播
                            await BotLiveState.filter(id=record.id).update(live_state=live_status)

                            live_cover_url = response_room_data["data"]["user_cover"]
                            live_avatar_url = response_host_data["data"]["card"]["face"]
                            live_name = response_host_data["data"]["card"]["name"]
                            live_address = f"https://live.bilibili.com/{record.live_id}"
                            live_title = response_room_data["data"]["title"]

                            image = await make_live_image(live_cover_url,live_avatar_url,live_name,live_address,live_title)
                            buffer = BytesIO()
                            image.save(buffer, format="PNG")
                            buffer.seek(0)

                            message = (
                                    MessageSegment.image(buffer)  # 添加图片
                                    + "\n"  # 换行
                                    + live_address  # 添加直播地址
                            )

                            await bot.send_group_msg(group_id=record.group_number, message=message)

                        else:
                            logger.error(f"Failed for Host ID {response_room_data["data"]["uid"]}, Status: {response_host_info.status_code}")
                    else:
                        continue

                else:
                    logger.error(f"Failed for Live ID {record.live_id}, Status: {response_room_info.status_code}")
            except httpx.RequestError as exc:
                logger.error(f"Error while requesting Live ID {record.live_id} : {exc}")