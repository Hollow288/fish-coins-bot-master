import asyncio
import mimetypes
import os
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from dotenv import load_dotenv
from nonebot import on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    Message,
    MessageEvent,
    MessageSegment,
    PrivateMessageEvent,
)
from nonebot.log import logger
from nonebot.rule import Rule

from fish_coins_bot.utils.ai_client import call_text_api

load_dotenv()

TRIGGER_TEXT = "翻译"
IMAGE_TRANSLATE_PATH_PREFIX = "/api/v1/ocr/translate-image"


@dataclass(frozen=True)
class DownloadedImage:
    content: bytes
    filename: str
    content_type: str


@dataclass(frozen=True)
class OcrTranslateConfig:
    base_uri: str
    api_key: str
    target_language: str
    min_confidence: float | None
    poll_interval_seconds: float
    timeout_seconds: float
    request_timeout_seconds: float


def _parse_float(raw: str | None, default: float, minimum: float) -> float:
    if raw is None or not raw.strip():
        return default
    try:
        return max(float(raw), minimum)
    except ValueError:
        return default


def _parse_optional_confidence(raw: str | None) -> float | None:
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return min(max(value, 0.0), 1.0)


def _derive_base_uri() -> str:
    raw_base = os.getenv("TRANSLATE_IMAGE_BASE_URI", "").strip()
    if raw_base:
        return raw_base.rstrip("/")

    raw_submit = os.getenv("TRANSLATE_IMAGE_SUBMIT_URI", "").strip()
    if raw_submit:
        normalized = raw_submit.rstrip("/")
        submit_suffix = f"{IMAGE_TRANSLATE_PATH_PREFIX}/submit"
        if normalized.endswith(submit_suffix):
            return normalized[: -len(submit_suffix)].rstrip("/")
        marker = IMAGE_TRANSLATE_PATH_PREFIX
        index = normalized.find(marker)
        if index >= 0:
            return normalized[:index].rstrip("/")

    return ""


def _get_config() -> OcrTranslateConfig:
    return OcrTranslateConfig(
        base_uri=_derive_base_uri(),
        api_key=(
            os.getenv("TRANSLATE_IMAGE_APIKEY", "").strip()
            or os.getenv("AI_TEXT_APIKEY", "").strip()
        ),
        target_language=(
            os.getenv("TRANSLATE_TARGET_LANGUAGE", "").strip()
            or "中文"
        ),
        min_confidence=_parse_optional_confidence(
            os.getenv("TRANSLATE_MIN_CONFIDENCE")
        ),
        poll_interval_seconds=_parse_float(
            os.getenv("TRANSLATE_POLL_INTERVAL_SECONDS"),
            default=2.0,
            minimum=0.5,
        ),
        timeout_seconds=_parse_float(
            os.getenv("TRANSLATE_TIMEOUT_SECONDS"),
            default=120.0,
            minimum=5.0,
        ),
        request_timeout_seconds=_parse_float(
            os.getenv("TRANSLATE_REQUEST_TIMEOUT_SECONDS"),
            default=70.0,
            minimum=5.0,
        ),
    )


def _is_reply_translate(event: MessageEvent) -> bool:
    if not isinstance(event, (GroupMessageEvent, PrivateMessageEvent)):
        return False
    if getattr(event, "reply", None) is None:
        return False
    return event.get_plaintext().strip() == TRIGGER_TEXT


reply_translate = on_message(
    rule=Rule(_is_reply_translate),
    priority=10,
    block=True,
)


def _extract_first_image_segment(message: Message) -> dict[str, Any] | None:
    for segment in message:
        if getattr(segment, "type", "") != "image":
            continue
        data = dict(getattr(segment, "data", {}) or {})
        if data.get("url"):
            return data
    return None


def _extract_reply_text(message: Message) -> str:
    return message.extract_plain_text().strip()


def _guess_filename(url: str, content_type: str) -> str:
    parsed_path = unquote(urlparse(url).path)
    name = Path(parsed_path).name
    if name and "." in name:
        return name
    suffix = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".png"
    return f"reply-image{suffix}"


async def _download_image(url: str, timeout: float) -> DownloadedImage:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    content = response.content
    if not content:
        raise RuntimeError("图片内容为空。")

    content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip()
    if not content_type:
        guessed_type, _ = mimetypes.guess_type(url)
        content_type = guessed_type or "image/png"
    if not content_type.startswith("image/"):
        raise RuntimeError(f"被回复图片的 Content-Type 不支持: {content_type}")

    return DownloadedImage(
        content=content,
        filename=_guess_filename(url, content_type),
        content_type=content_type,
    )


async def _submit_image_task(
    client: httpx.AsyncClient,
    config: OcrTranslateConfig,
    image: DownloadedImage,
) -> str:
    params: dict[str, str] = {"targetLanguage": config.target_language}
    if config.min_confidence is not None:
        params["minConfidence"] = str(config.min_confidence)

    response = await client.post(
        f"{config.base_uri}{IMAGE_TRANSLATE_PATH_PREFIX}/submit",
        params=params,
        files={"file": (image.filename, image.content, image.content_type)},
        headers={"X-API-KEY": config.api_key},
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 200:
        raise RuntimeError(payload.get("msg") or "图片翻译任务提交失败。")

    task_id = (payload.get("data") or {}).get("taskId")
    if not isinstance(task_id, str) or not task_id.strip():
        raise RuntimeError(f"图片翻译提交接口未返回 taskId: {payload}")
    return task_id.strip()


async def _wait_image_task(
    client: httpx.AsyncClient,
    config: OcrTranslateConfig,
    task_id: str,
) -> None:
    deadline = time.monotonic() + config.timeout_seconds
    while True:
        response = await client.get(
            f"{config.base_uri}{IMAGE_TRANSLATE_PATH_PREFIX}/result/{task_id}",
            headers={"X-API-KEY": config.api_key},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 200:
            raise RuntimeError(payload.get("msg") or "图片翻译结果查询失败。")

        data = payload.get("data") or {}
        status = str(data.get("status") or "").upper()
        if status == "SUCCESS":
            return
        if status == "FAILED":
            raise RuntimeError(data.get("errorMsg") or "图片翻译任务失败。")
        if time.monotonic() >= deadline:
            raise TimeoutError("图片翻译任务等待超时。")

        await asyncio.sleep(config.poll_interval_seconds)


async def _fetch_result_image(
    client: httpx.AsyncClient,
    config: OcrTranslateConfig,
    task_id: str,
) -> bytes:
    response = await client.get(
        f"{config.base_uri}{IMAGE_TRANSLATE_PATH_PREFIX}/file/{task_id}",
        headers={"X-API-KEY": config.api_key},
    )
    response.raise_for_status()
    content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip()
    if content_type and not content_type.startswith("image/"):
        raise RuntimeError(f"图片翻译结果不是图片: {content_type}")
    if not response.content:
        raise RuntimeError("图片翻译结果为空。")
    return response.content


async def _translate_image(image_url: str) -> bytes:
    config = _get_config()
    if not config.base_uri or not config.api_key:
        raise RuntimeError(
            "图片翻译接口未配置，请设置 TRANSLATE_IMAGE_BASE_URI "
            "或 TRANSLATE_IMAGE_SUBMIT_URI，并设置 TRANSLATE_IMAGE_APIKEY "
            "或 AI_TEXT_APIKEY。"
        )

    source_image = await _download_image(image_url, config.request_timeout_seconds)
    async with httpx.AsyncClient(
        timeout=config.request_timeout_seconds,
        follow_redirects=True,
    ) as client:
        task_id = await _submit_image_task(client, config, source_image)
        await _wait_image_task(client, config, task_id)
        return await _fetch_result_image(client, config, task_id)


def _build_text_translate_prompt(text: str, target_language: str) -> str:
    return (
        f"请把下面这段内容翻译成{target_language}。\n"
        "要求：只输出译文，不要解释；保留原文的换行、列表结构和语气；"
        "专有名词、人名、游戏术语在不确定时保留原文或采用常见译名。\n\n"
        f"原文：\n{text}"
    )


async def _translate_text(text: str, event: MessageEvent) -> str | None:
    config = _get_config()
    prompt = _build_text_translate_prompt(text, config.target_language)
    return await call_text_api(
        prompt,
        memory_id=f"translate-text-{event.user_id}-{event.message_id}",
        fresh_memory_each_retry=True,
        retries=3,
        timeout=config.request_timeout_seconds,
        log_tag="translate.text",
    )


@reply_translate.handle()
async def handle_reply_translate(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent) -> None:
    if str(event.user_id) == str(bot.self_id):
        return

    reply = getattr(event, "reply", None)
    reply_message = getattr(reply, "message", None)
    if reply_message is None:
        await reply_translate.finish("请回复一条包含图片或文本的消息再发送“翻译”。")

    image_data = _extract_first_image_segment(reply_message)
    if image_data is not None:
        image_url = str(image_data.get("url") or "")
        await reply_translate.send("图片翻译处理中，请稍等。")
        try:
            result_image = await _translate_image(image_url)
        except Exception as exc:
            logger.error(f"translate 图片翻译失败: {exc}")
            await reply_translate.finish(f"图片翻译失败：{exc}")
        await reply_translate.finish(MessageSegment.image(BytesIO(result_image)))

    reply_text = _extract_reply_text(reply_message)
    if not reply_text:
        await reply_translate.finish("被回复的消息里没有可翻译的图片或文本。")

    try:
        result_text = await _translate_text(reply_text, event)
    except Exception as exc:
        logger.error(f"translate 文本翻译失败: {exc}")
        await reply_translate.finish(f"文本翻译失败：{exc}")
        return

    if not result_text:
        await reply_translate.finish("文本翻译失败：接口没有返回有效结果。")
    await reply_translate.finish(result_text)
