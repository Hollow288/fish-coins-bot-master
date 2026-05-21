import os
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from nonebot.log import logger

load_dotenv()

_AI_TEXT_URI = os.getenv("AI_TEXT_URI")
_AI_TEXT_APIKEY = os.getenv("AI_TEXT_APIKEY")
_AI_IMAGE_RECOGNIZE_URI = os.getenv("AI_IMAGE_RECOGNIZE_URI")
_AI_IMAGE_RECOGNIZE_APIKEY = os.getenv("AI_IMAGE_RECOGNIZE_APIKEY")


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


async def call_image_recognize_api(
    b64_data: str,
    mime_type: str,
    message: str | None = None,
    *,
    memory_id: str | None = None,
    uri: str | None = None,
    api_key: str | None = None,
    retries: int = 3,
    timeout: float = 120,
    log_tag: str = "ai-image",
) -> str | None:
    """调用图片识别接口，返回成功的 message 文本，失败返回 None。

    :param b64_data: 图片纯 base64（不带 data:image/...;base64, 前缀）
    :param mime_type: 必须与 b64_data 内容匹配，如 image/png / image/jpeg / image/webp
    :param message: 给视觉模型的提问，缺省由后端使用默认 prompt
    :param memory_id: 该接口不写历史，仅原样回传，仅用于日志关联
    :param uri: 接口地址，默认读取 AI_IMAGE_RECOGNIZE_URI
    :param api_key: API Key，默认读取 AI_IMAGE_RECOGNIZE_APIKEY
    :param retries: 失败重试次数
    :param timeout: 请求超时秒数（识图通常更慢，默认 120s）
    :param log_tag: 日志中标识调用来源的标签
    """
    request_uri = uri or _AI_IMAGE_RECOGNIZE_URI
    request_key = api_key or _AI_IMAGE_RECOGNIZE_APIKEY

    if not request_uri or not request_key:
        raise RuntimeError(
            f"{log_tag} 调用图片识别接口失败：AI_IMAGE_RECOGNIZE_URI / AI_IMAGE_RECOGNIZE_APIKEY 未配置。"
        )

    payload: dict[str, Any] = {
        "data": b64_data,
        "mimeType": mime_type,
    }
    if message:
        payload["message"] = message
    if memory_id:
        payload["memoryId"] = memory_id

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(1, retries + 1):
            response: httpx.Response | None = None
            try:
                response = await client.post(
                    request_uri,
                    json=payload,
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
                logger.error(f"{log_tag} 图片识别接口返回非预期结构: {data}")
            except Exception as exc:
                body = response.text if response is not None else ""
                logger.error(f"{log_tag} 第 {attempt} 次调用失败: {exc}")
                if memory_id:
                    logger.error(f"{log_tag} 本次请求 memoryId: {memory_id}")
                if body:
                    logger.error(f"{log_tag} 响应体: {body}")
    return None
