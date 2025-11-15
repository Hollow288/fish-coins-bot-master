import os
from typing import Any, Coroutine

import httpx
from nonebot.adapters.onebot.v11 import MessageSegment
from dotenv import load_dotenv
from nonebot import  on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.rule import Rule, to_me
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.log import logger

from fish_coins_bot.utils.image_utils import get_first_image_base64_and_mime


def is_private_chat(event) -> bool:
    return isinstance(event, PrivateMessageEvent)

reply_chat = on_command(
    "chat",
    rule=Rule(is_private_chat),
    aliases={"ai"},
    priority=10,
    block=True,
)

load_dotenv()


AI_IMAGE_URI = os.getenv("AI_IMAGE_URI")
AI_IMAGE_APIKEY = os.getenv("AI_IMAGE_APIKEY")
AI_TEXT_URI = os.getenv("AI_TEXT_URI")
AI_TEXT_APIKEY = os.getenv("AI_TEXT_APIKEY")
ADMIN_ID = os.getenv("ADMIN_ID")

async def call_text_api(message: str, user_id: str, retries: int = 3) -> Any | None:
    """
    调用 API，如果失败重试最多 retries 次。
    返回最终成功的 message，否则返回 None。
    """
    async with httpx.AsyncClient(timeout=70) as client:
        for attempt in range(retries):
            try:
                response = await client.post(
                    AI_TEXT_URI,
                    json={
                        "message": message,
                        "memoryId": user_id
                    },
                    headers={
                        "X-API-KEY": AI_TEXT_APIKEY,
                        "Content-Type": "application/json"
                    }
                )
                data = response.json()
                # 检查返回格式
                if data.get("code") == 200 and "data" in data and data["data"].get("message"):
                    return data["data"]["message"]
            except Exception as e:
                # 这里可以打印日志或记录错误
                logger.error(f"尝试第 {attempt+1} 次失败: {e}")
                logger.error(f"解析 JSON 出错 response: {response.text}")
    return None


@reply_chat.handle()
async def reply_chat_handle(bot: Bot, event: PrivateMessageEvent, args: Message = CommandArg()):
    user_id = str(event.sender.user_id)


    if str(user_id) == str(ADMIN_ID):
        if message := args.extract_plain_text():
            result = await call_text_api(message, user_id)
            if result:
                await reply_chat.send(result)
            else:
                await reply_chat.send("接口请求失败，请稍后再试。")
        else:
            await reply_chat.send("请发送非空消息。")


reply_image = on_command(
    "image",
    rule=Rule(is_private_chat),
    aliases={"images"},
    priority=10,
    block=True,
)

async def call_image_api(message: str, user_id: str,img_base64: str,mime_type :str, retries: int = 3) -> Any | None:
    """
    调用 API，如果失败重试最多 retries 次。
    返回最终成功的 message，否则返回 None。
    """
    async with httpx.AsyncClient(timeout=70) as client:
        for attempt in range(retries):
            try:
                response = await client.post(
                    AI_IMAGE_URI,
                    json={
                        "message": message,
                        "memoryId": user_id,
                        "data": img_base64,
                        "mimeType": mime_type,
                    },
                    headers={
                        "X-API-KEY": AI_IMAGE_APIKEY,
                        "Content-Type": "application/json"
                    }
                )
                data = response.json()
                # 检查返回格式
                if data.get("code") == 200 and "data" in data and data["data"].get("data"):
                    return data["data"]["data"]
            except Exception as e:
                # 这里可以打印日志或记录错误
                logger.error(f"尝试第 {attempt+1} 次失败: {e}")
                logger.error(f"解析 JSON 出错 response: {response.text}")
    return None


@reply_image.handle()
async def reply_image_handle(bot: Bot, event: PrivateMessageEvent, args: Message = CommandArg()):
    user_id = str(event.sender.user_id)


    if str(user_id) == str(ADMIN_ID):
        if message := args.extract_plain_text():
            logger.info(f"图片指令消息event: {event}")

            img_base64, mime_type = await get_first_image_base64_and_mime(event)

            logger.info(f"图片指令消息img_base64: {img_base64}")
            logger.info(f"图片指令消息mime_type: {mime_type}")

            result = await call_image_api(message, user_id, img_base64, mime_type)
            logger.info(f"图片指令消息result: {result}")
            if result:
                await reply_image.send(MessageSegment.image(f"base64://{result}"))
            else:
                await reply_image.send("接口请求失败，请稍后再试。")
        else:
            await reply_image.send("请发送非空消息。")