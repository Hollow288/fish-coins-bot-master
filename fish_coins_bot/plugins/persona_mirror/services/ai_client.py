from uuid import uuid4
from typing import Any

import httpx
from nonebot.log import logger

from ..config import get_plugin_config


def _build_request_memory_id(memory_prefix: str) -> str:
    prefix = (memory_prefix or "persona").strip()
    return f"{prefix}-{uuid4().hex}"


async def call_text_model(prompt: str, memory_prefix: str, retries: int = 3) -> str | None:
    config = get_plugin_config()
    if not config.text_api_uri or not config.text_api_key:
        raise RuntimeError("PERSONA_TEXT_URI / PERSONA_TEXT_APIKEY 未配置，且未找到 AI_TEXT_URI / AI_TEXT_APIKEY 回退值。")

    async with httpx.AsyncClient(timeout=70) as client:
        for attempt in range(1, retries + 1):
            response: httpx.Response | None = None
            request_memory_id = _build_request_memory_id(memory_prefix)
            try:
                response = await client.post(
                    config.text_api_uri,
                    json={
                        "message": prompt,
                        "memoryId": request_memory_id,
                    },
                    headers={
                        "X-API-KEY": config.text_api_key,
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                message = data.get("data", {}).get("message")
                if data.get("code") == 200 and isinstance(message, str) and message.strip():
                    return message
                logger.error(f"persona_mirror 文本接口返回非预期结构: {data}")
            except Exception as exc:
                body = response.text if response is not None else ""
                logger.error(f"persona_mirror 第 {attempt} 次调用失败: {exc}")
                logger.error(f"persona_mirror 本次请求 memoryId: {request_memory_id}")
                if body:
                    logger.error(f"persona_mirror 响应体: {body}")
    return None
