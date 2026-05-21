import os
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from nonebot.log import logger

load_dotenv()

_AI_TEXT_URI = os.getenv("AI_TEXT_URI")
_AI_TEXT_APIKEY = os.getenv("AI_TEXT_APIKEY")


async def call_text_api(
    message: str,
    memory_id: str,
    *,
    uri: str | None = None,
    api_key: str | None = None,
    retries: int = 3,
    fresh_memory_each_retry: bool = False,
    timeout: float = 70,
    log_tag: str = "ai",
) -> str | None:
    """调用文本 AI 接口，失败重试 retries 次，返回成功的 message。

    :param message: 发送给 AI 的消息内容
    :param memory_id: 会话 ID；当 fresh_memory_each_retry=True 时作为前缀
    :param uri: 接口地址，默认读取 AI_TEXT_URI
    :param api_key: API Key，默认读取 AI_TEXT_APIKEY
    :param retries: 失败重试次数
    :param fresh_memory_each_retry: 是否每次重试都生成新的 memoryId（{memory_id}-{uuid}）
    :param timeout: 请求超时秒数
    :param log_tag: 日志中标识调用来源的标签
    """
    request_uri = uri or _AI_TEXT_URI
    request_key = api_key or _AI_TEXT_APIKEY

    if not request_uri or not request_key:
        raise RuntimeError(
            f"{log_tag} 调用文本 AI 接口失败：AI_TEXT_URI / AI_TEXT_APIKEY 未配置。"
        )

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(1, retries + 1):
            response: httpx.Response | None = None
            request_memory_id = (
                f"{memory_id}-{uuid4().hex}" if fresh_memory_each_retry else memory_id
            )
            try:
                response = await client.post(
                    request_uri,
                    json={
                        "message": message,
                        "memoryId": request_memory_id,
                    },
                    headers={
                        "X-API-KEY": request_key,
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                returned = data.get("data", {}).get("message")
                if data.get("code") == 200 and isinstance(returned, str) and returned.strip():
                    return returned
                logger.error(f"{log_tag} 文本接口返回非预期结构: {data}")
            except Exception as exc:
                body = response.text if response is not None else ""
                logger.error(f"{log_tag} 第 {attempt} 次调用失败: {exc}")
                logger.error(f"{log_tag} 本次请求 memoryId: {request_memory_id}")
                if body:
                    logger.error(f"{log_tag} 响应体: {body}")
    return None
