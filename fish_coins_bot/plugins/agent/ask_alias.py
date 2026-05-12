import json
import os
import re
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment, PrivateMessageEvent
from nonebot.log import logger
from nonebot.params import CommandArg

load_dotenv()

AGENT_ASK_URI = os.getenv("AGENT_ASK_URI")
AGENT_ASK_APIKEY = os.getenv("AGENT_ASK_APIKEY")

SCREENSHOTS_ROOT = Path("/app/screenshots")

agent_ask = on_command(
    "agent",
    priority=10,
    block=True,
)


async def call_agent_ask_api(message: str, retries: int = 3) -> Optional[dict]:
    """调用 /api/v1/agent/ask 接口, 解析 data.reply 后返回 dict; 失败返回 None."""
    if not AGENT_ASK_URI or not AGENT_ASK_APIKEY:
        logger.error("AGENT_ASK_URI 或 AGENT_ASK_APIKEY 未配置")
        return None

    async with httpx.AsyncClient(timeout=70) as client:
        for attempt in range(retries):
            response_text = ""
            try:
                response = await client.post(
                    AGENT_ASK_URI,
                    json={"message": message},
                    headers={
                        "X-API-KEY": AGENT_ASK_APIKEY,
                        "Content-Type": "application/json",
                    },
                )
                response_text = response.text
                data = response.json()

                if data.get("code") != 200:
                    logger.error(f"agent ask 接口返回非200: {data}")
                    continue

                reply = data.get("data", {}).get("reply")
                if not reply:
                    logger.error(f"agent ask 接口缺少 data.reply: {data}")
                    continue

                try:
                    return json.loads(reply)
                except json.JSONDecodeError:
                    # 兜底: AI 偶尔会带前后缀, 正则提取 {...}
                    match = re.search(r"\{[\s\S]*\}", reply)
                    if match:
                        return json.loads(match.group(0))
                    logger.error(f"reply 解析失败: {reply}")
            except Exception as e:
                logger.error(f"agent ask 第 {attempt + 1} 次失败: {e}")
                if response_text:
                    logger.error(f"解析 JSON 出错 response: {response_text}")
    return None


@agent_ask.handle()
async def agent_ask_handle(
    bot: Bot,
    event: GroupMessageEvent | PrivateMessageEvent,
    args: Message = CommandArg(),
):
    message = args.extract_plain_text().strip()
    if not message:
        await agent_ask.finish("请在 agent 后面接上要查询的内容。")

    result = await call_agent_ask_api(message)
    if result is None:
        await agent_ask.finish("接口请求失败，请稍后再试。")

    if result.get("type") is None:
        reason = result.get("reason") or "未在别名库中找到匹配项"
        await agent_ask.finish(reason)

    item_type = result.get("type")
    value = result.get("value")
    logger.info(f"agent ask 命中: {result}")

    if not value:
        await agent_ask.finish("接口返回缺少 value，无法定位图鉴。")

    if item_type == "意志":
        sub_dir = "willpower"
    elif item_type == "源器":
        sub_dir = "artifact"
    elif item_type == "武器":
        sub_dir = "arms-attack" if "详情" in message else "arms"
    else:
        await agent_ask.finish(f"未知类型: {item_type}")

    image_path = SCREENSHOTS_ROOT / sub_dir / f"{value}.png"
    if not image_path.exists():
        await agent_ask.finish(f"没有找到 `{value}` 的图鉴,快联系作者催他收录吧~")

    await agent_ask.finish(MessageSegment.image(f"file://{image_path}"))
