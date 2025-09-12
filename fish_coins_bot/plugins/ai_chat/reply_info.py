import os
from typing import Any, Coroutine

import httpx
from dotenv import load_dotenv
from nonebot import  on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.rule import Rule, to_me
from nonebot.adapters import Message
from nonebot.params import CommandArg

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


API_HOST = os.getenv("API_HOST")
API_KEY = os.getenv("API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

async def call_api(message: str, user_id: str, retries: int = 3) -> Any | None:
    """
    调用 API，如果失败重试最多 retries 次。
    返回最终成功的 message，否则返回 None。
    """
    headers = {
        "X-API-KEY": API_KEY,
        "Content-Type": "application/x-www-form-urlencoded"
    }

    payload = {
        "message": message,
        "memoryId": user_id
    }

    async with httpx.AsyncClient(timeout=70) as client:
        for attempt in range(retries):
            try:
                response = await client.post(API_HOST, json=payload, headers=headers)
                data = response.json()
                # 检查返回格式
                if data.get("code") == 200 and "data" in data and data["data"].get("message"):
                    return data["data"]["message"]
            except Exception as e:
                # 这里可以打印日志或记录错误
                print(f"尝试第 {attempt+1} 次失败: {e}")
    return None


@reply_chat.handle()
async def reply_chat_handle(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    user_id = str(event.sender.user_id)

    if user_id == ADMIN_ID:
        if message := args.extract_plain_text():
            result = await call_api(message, user_id)
            if result:
                await reply_chat.send(result)
            else:
                await reply_chat.send("接口请求失败，请稍后再试。")
        else:
            await reply_chat.send("请发送非空消息。")



