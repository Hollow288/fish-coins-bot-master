"""调用 AI 图片识别接口，给 StickerAsset 写回 is_suitable_sticker / sticker_meaning。"""

import asyncio
import base64
import json
import re
from datetime import datetime
from typing import Any

import pytz
from nonebot.log import logger

from fish_coins_bot.utils.ai_client import call_image_recognize_api
from fish_coins_bot.utils.minio_client import minio_client

from ..config import get_plugin_config
from ..models import StickerAsset

_SHANGHAI_TZ = pytz.timezone("Asia/Shanghai")


def _now_shanghai() -> datetime:
    return datetime.now(_SHANGHAI_TZ)


RECOGNIZE_PROMPT = (
    "你是聊天表情包鉴定助手，只看图片本身。\n"
    "请严格按以下 JSON 返回，不要任何额外文字、不要 markdown 代码块：\n"
    '{"suitable": true/false, "meaning": "..."}\n'
    "\n"
    "判断标准：\n"
    "- suitable=true：明显用于聊天的表情包/梗图（情绪、态度、调侃，常带文字或夸张表情）\n"
    "- suitable=false：风景、广告、自拍、复杂截图、二维码、无明显情绪表达的普通图片\n"
    "\n"
    "meaning 字段要求：\n"
    "- suitable=true：用一句不超过 30 字的中文，说明这张表情包通常想表达什么情绪/含义（例如\"震惊无语\"、\"卖萌求抱抱\"）\n"
    "- suitable=false：meaning 填空字符串 \"\""
)

_EXT_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _mime_type_for(asset: StickerAsset) -> str | None:
    if asset.content_type and asset.content_type.startswith("image/"):
        return asset.content_type
    if asset.file_ext:
        return _EXT_TO_MIME.get(asset.file_ext.lower())
    return None


async def _fetch_object_bytes(bucket_name: str, object_name: str) -> bytes:
    def _read() -> bytes:
        response = minio_client.get_object(bucket_name, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    return await asyncio.to_thread(_read)


def _parse_recognize_response(raw: str) -> tuple[bool, str] | None:
    """从 AI 返回里抽出 {suitable, meaning}，解析不出来返回 None。"""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*?\}", text, re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(payload, dict):
        return None

    raw_suitable = payload.get("suitable")
    if isinstance(raw_suitable, bool):
        suitable = raw_suitable
    elif isinstance(raw_suitable, str):
        suitable = raw_suitable.strip().lower() in {"true", "yes", "1", "是"}
    else:
        return None

    meaning = payload.get("meaning")
    if meaning is None:
        meaning = ""
    if not isinstance(meaning, str):
        meaning = str(meaning)

    return suitable, meaning.strip()


async def _recognize_one(asset: StickerAsset, max_attempts: int) -> str:
    """识别单张表情包，返回结果状态: done / failed / pending。"""
    mime_type = _mime_type_for(asset)
    if not mime_type:
        asset.recognize_status = "failed"
        asset.recognize_attempts = max_attempts
        asset.recognize_error = (
            f"无法判定 mimeType: content_type={asset.content_type}, file_ext={asset.file_ext}"
        )
        asset.recognized_at = _now_shanghai()
        await asset.save()
        logger.warning(
            f"sticker_collector 识别失败 #{asset.id}: {asset.recognize_error}"
        )
        return "failed"

    try:
        content = await _fetch_object_bytes(asset.bucket_name, asset.object_name)
    except Exception as exc:
        asset.recognize_attempts = (asset.recognize_attempts or 0) + 1
        asset.recognize_error = f"MinIO 读取失败: {exc}"
        if asset.recognize_attempts >= max_attempts:
            asset.recognize_status = "failed"
            asset.recognized_at = _now_shanghai()
        await asset.save()
        logger.error(
            f"sticker_collector MinIO 读取失败 #{asset.id} "
            f"({asset.bucket_name}/{asset.object_name}): {exc}"
        )
        return asset.recognize_status

    b64_data = base64.b64encode(content).decode("ascii")
    memory_id = f"sticker-{asset.id}"

    try:
        raw = await call_image_recognize_api(
            b64_data,
            mime_type,
            message=RECOGNIZE_PROMPT,
            memory_id=memory_id,
            log_tag=f"sticker#{asset.id}",
        )
    except Exception as exc:
        asset.recognize_attempts = (asset.recognize_attempts or 0) + 1
        asset.recognize_error = f"调用接口异常: {exc}"
        if asset.recognize_attempts >= max_attempts:
            asset.recognize_status = "failed"
            asset.recognized_at = _now_shanghai()
        await asset.save()
        logger.error(f"sticker_collector 识别接口异常 #{asset.id}: {exc}")
        return asset.recognize_status

    if raw is None:
        asset.recognize_attempts = (asset.recognize_attempts or 0) + 1
        asset.recognize_error = "识别接口连续重试均失败"
        if asset.recognize_attempts >= max_attempts:
            asset.recognize_status = "failed"
            asset.recognized_at = _now_shanghai()
        await asset.save()
        return asset.recognize_status

    parsed = _parse_recognize_response(raw)
    if parsed is None:
        asset.recognize_status = "failed"
        asset.recognize_attempts = max_attempts
        asset.recognize_error = f"无法解析 AI 返回: {raw[:500]}"
        asset.recognized_at = _now_shanghai()
        await asset.save()
        logger.warning(f"sticker_collector JSON 解析失败 #{asset.id}: {raw}")
        return "failed"

    suitable, meaning = parsed
    asset.is_suitable_sticker = suitable
    asset.sticker_meaning = meaning if suitable else ""
    asset.recognize_status = "done"
    asset.recognize_attempts = (asset.recognize_attempts or 0) + 1
    asset.recognize_error = None
    asset.recognized_at = _now_shanghai()
    await asset.save()
    logger.info(
        f"sticker_collector 识别完成 #{asset.id} suitable={suitable} meaning={meaning!r}"
    )
    return "done"


async def run_pending_sticker_recognition() -> dict[str, Any]:
    config = get_plugin_config()
    batch_size = config.recognize_batch_size
    max_attempts = config.recognize_max_attempts
    throttle_ms = config.recognize_throttle_ms

    pending = await (
        StickerAsset
        .filter(recognize_status="pending", recognize_attempts__lt=max_attempts)
        .order_by("id")
        .limit(batch_size)
    )

    stats = {"picked": len(pending), "done": 0, "failed": 0, "retry": 0}
    if not pending:
        return stats

    for index, asset in enumerate(pending):
        try:
            result = await _recognize_one(asset, max_attempts)
        except Exception as exc:
            logger.error(f"sticker_collector 识别未捕获异常 #{asset.id}: {exc}")
            stats["failed"] += 1
            continue

        if result == "done":
            stats["done"] += 1
        elif result == "failed":
            stats["failed"] += 1
        else:
            stats["retry"] += 1

        if throttle_ms > 0 and index < len(pending) - 1:
            await asyncio.sleep(throttle_ms / 1000.0)

    logger.info(
        "sticker_collector 识别批次完成: "
        f"picked={stats['picked']} done={stats['done']} "
        f"failed={stats['failed']} retry={stats['retry']}"
    )
    return stats
