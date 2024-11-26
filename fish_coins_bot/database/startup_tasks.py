import httpx
from fish_coins_bot.database.models import BotLiveState  # 假设模型文件路径为此
from nonebot.log import logger


async def initialize_live_state():

    # 查询表中所有数据
    all_records = await BotLiveState.all().filter(del_flag="0")

    allowed_status = {"0", "1", "2"}  # 允许的状态集合

    # 遍历所有记录并发送 HTTP GET 请求
    async with httpx.AsyncClient() as client:
        for record in all_records:
            params = {"id": record.live_id}

            # 添加请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
            }

            try:
                response = await client.get(
                    "https://api.live.bilibili.com/room/v1/Room/get_info",
                    params=params,
                    headers=headers,
                )

                # 检查响应状态码
                if response.status_code == 200:
                    response_data = response.json()


                    live_status = str(response_data["data"]["live_status"])

                    if live_status in allowed_status and live_status != str(record.live_state):
                        await BotLiveState.filter(id=record.id).update(live_state=live_status)
                        logger.success(f"Update for Live ID {record.live_id}, Status: {live_status}")
                    else:
                        continue
                else:
                    logger.error(f"Failed for Live ID {record.live_id}, Status: {response.status_code}")
            except httpx.RequestError as exc:
                logger.error(f"Error while requesting Live ID {record.live_id} : {exc}")