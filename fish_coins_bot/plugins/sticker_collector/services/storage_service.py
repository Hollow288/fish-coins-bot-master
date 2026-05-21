"""表情包采集核心：从消息事件取出表情包资源，下载、去重、上传 MinIO，并维护使用记录。"""

import asyncio
import hashlib
import mimetypes
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from minio.error import S3Error
from nonebot.log import logger
from tortoise.exceptions import IntegrityError

from fish_coins_bot.utils.minio_client import minio_client

from ..models import StickerAsset, StickerUsage


STICKER_BUCKET = "fish-coins-bot-master"
STICKER_PREFIX = "sticker"


def _guess_image_info(
    content: bytes,
    content_type: str | None,
    source_url: str | None,
    source_file: str | None,
) -> tuple[str, str]:
    normalized_type = (content_type or "").split(";")[0].strip().lower()
    suffix = ""

    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        normalized_type = "image/png"
        suffix = ".png"
    elif content.startswith(b"\xff\xd8\xff"):
        normalized_type = "image/jpeg"
        suffix = ".jpg"
    elif content.startswith((b"GIF87a", b"GIF89a")):
        normalized_type = "image/gif"
        suffix = ".gif"
    elif len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        normalized_type = "image/webp"
        suffix = ".webp"
    elif content.startswith(b"BM"):
        normalized_type = "image/bmp"
        suffix = ".bmp"

    if not suffix and normalized_type:
        suffix = mimetypes.guess_extension(normalized_type) or ""

    if not suffix:
        for raw_path in (source_file, urlparse(source_url or "").path):
            if not raw_path:
                continue
            candidate = Path(unquote(raw_path)).suffix.lower()
            if candidate in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
                suffix = ".jpg" if candidate == ".jpeg" else candidate
                break

    if not normalized_type:
        normalized_type = mimetypes.types_map.get(suffix, "application/octet-stream")

    return normalized_type, suffix or ".bin"


def _iter_sticker_segments(event: Any) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for segment in getattr(event, "message", []):
        segment_type = getattr(segment, "type", "")
        data = dict(getattr(segment, "data", {}) or {})
        url = data.get("url")
        if segment_type == "image" and url:
            segments.append({"type": segment_type, "data": data})
        elif segment_type in {"mface", "marketface"} and url:
            segments.append({"type": segment_type, "data": data})
    return segments


def _sender_name(event: Any) -> str:
    sender = getattr(event, "sender", None)
    if sender is None:
        return str(getattr(event, "user_id", "") or "")
    return (
        getattr(sender, "card", "")
        or getattr(sender, "nickname", "")
        or str(getattr(event, "user_id", "") or "")
    )


async def _download_sticker_bytes(url: str) -> tuple[bytes, str | None]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content, response.headers.get("Content-Type")


async def _ensure_bucket_exists(bucket_name: str) -> None:
    exists = await asyncio.to_thread(minio_client.bucket_exists, bucket_name)
    if not exists:
        await asyncio.to_thread(minio_client.make_bucket, bucket_name)


async def _minio_object_exists(bucket_name: str, object_name: str) -> bool:
    try:
        await asyncio.to_thread(minio_client.stat_object, bucket_name, object_name)
        return True
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
            return False
        raise


async def _upload_sticker_if_needed(
    bucket_name: str,
    object_name: str,
    content: bytes,
    content_type: str,
) -> None:
    await _ensure_bucket_exists(bucket_name)
    if await _minio_object_exists(bucket_name, object_name):
        return
    await asyncio.to_thread(
        minio_client.put_object,
        bucket_name,
        object_name,
        BytesIO(content),
        len(content),
        content_type=content_type,
    )


async def _upsert_sticker_asset(
    *,
    segment: dict[str, Any],
    content: bytes,
    content_type: str,
    file_ext: str,
    source_url: str | None,
    source_file: str | None,
) -> StickerAsset:
    content_sha256 = hashlib.sha256(content).hexdigest()
    content_md5 = hashlib.md5(content).hexdigest()
    object_name = f"{STICKER_PREFIX}/{content_sha256}{file_ext}"

    await _upload_sticker_if_needed(
        STICKER_BUCKET,
        object_name,
        content,
        content_type,
    )

    asset = await StickerAsset.get_or_none(content_sha256=content_sha256)
    if asset is None:
        try:
            asset = await StickerAsset.create(
                content_sha256=content_sha256,
                content_md5=content_md5,
                bucket_name=STICKER_BUCKET,
                object_name=object_name,
                content_type=content_type,
                file_ext=file_ext,
                file_size=len(content),
                used_count=1,
                source_url=source_url,
                source_file=source_file,
                raw_segment_json=segment,
            )
            return asset
        except IntegrityError:
            asset = await StickerAsset.get(content_sha256=content_sha256)

    asset.used_count += 1
    asset.bucket_name = STICKER_BUCKET
    asset.object_name = object_name
    asset.content_type = content_type
    asset.file_ext = file_ext
    asset.file_size = len(content)
    asset.source_url = source_url
    asset.source_file = source_file
    asset.raw_segment_json = segment
    if asset.recognize_status == "failed":
        logger.info(f"sticker_collector 复活 #{asset.id} (重新挑回识别队列)")
        asset.recognize_status = "pending"
        asset.recognize_attempts = 0
        asset.recognize_error = None
        asset.recognized_at = None
    await asset.save()
    return asset


async def _upsert_sticker_usage(
    *,
    asset: StickerAsset,
    event: Any,
) -> None:
    user_id = str(getattr(event, "user_id", "") or "")
    if not user_id:
        return
    group_id = str(getattr(event, "group_id", "") or "") or None
    platform_message_id = str(getattr(event, "message_id", "") or "") or None
    sender_name = _sender_name(event)

    usage = await StickerUsage.get_or_none(sticker_id=asset.id, user_id=user_id)
    if usage is None:
        try:
            await StickerUsage.create(
                sticker_id=asset.id,
                user_id=user_id,
                used_count=1,
                last_group_id=group_id,
                last_sender_name=sender_name or None,
                last_platform_message_id=platform_message_id,
            )
            return
        except IntegrityError:
            usage = await StickerUsage.get(sticker_id=asset.id, user_id=user_id)

    usage.used_count += 1
    usage.last_group_id = group_id
    usage.last_sender_name = sender_name or None
    usage.last_platform_message_id = platform_message_id
    await usage.save()


async def collect_stickers_from_event(event: Any) -> None:
    """主入口：扫描事件里所有表情包资源，下载/去重/上传/记录。

    调用方不需要关心发送者身份，每条消息都可以传进来。
    """
    sticker_segments = _iter_sticker_segments(event)
    if not sticker_segments:
        return

    for segment in sticker_segments:
        segment_data = segment.get("data", {})
        url = str(segment_data.get("url") or "")
        if not url:
            continue
        source_file = str(segment_data.get("file") or "") or None
        try:
            content, response_content_type = await _download_sticker_bytes(url)
            if not content:
                continue
            content_type, file_ext = _guess_image_info(
                content,
                response_content_type,
                url,
                source_file,
            )
            if not content_type.startswith("image/"):
                logger.warning(f"sticker_collector 跳过非图片资源: {content_type}")
                continue
            asset = await _upsert_sticker_asset(
                segment=segment,
                content=content,
                content_type=content_type,
                file_ext=file_ext,
                source_url=url,
                source_file=source_file,
            )
            await _upsert_sticker_usage(asset=asset, event=event)
        except Exception as exc:
            logger.error(f"sticker_collector 表情包保存失败: {exc}")
