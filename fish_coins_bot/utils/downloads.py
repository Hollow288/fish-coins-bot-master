import asyncio
import hashlib
import mimetypes
from pathlib import Path
from io import BytesIO
from typing import Any, Sequence
from urllib.parse import unquote, urlparse

import httpx
import yt_dlp
from nonebot.log import logger
from tortoise.exceptions import IntegrityError

from fish_coins_bot.utils.minio_client import minio_client
from minio.error import S3Error

SUPPORTED_EXTENSIONS = {'.mp4', '.mkv', '.webm', '.mov', '.avi'}
PERSONA_STICKER_BUCKET = "fish-coins-bot-master"
PERSONA_STICKER_PREFIX = "persona_mirror"


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


def _iter_persona_sticker_segments(event: Any) -> list[dict[str, Any]]:
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


async def _upsert_persona_sticker_asset(
    *,
    event: Any,
    target_user_id: str,
    segment: dict[str, Any],
    content: bytes,
    content_type: str,
    file_ext: str,
) -> None:
    from fish_coins_bot.plugins.persona_mirror.models import PersonaStickerAsset

    sender_user_id = str(getattr(event, "user_id", "") or target_user_id)
    group_id = str(getattr(event, "group_id", "") or "") or None
    platform_message_id = str(getattr(event, "message_id", "") or "") or None
    segment_data = segment.get("data", {})
    source_file = str(segment_data.get("file") or "") or None
    source_url = str(segment_data.get("url") or "") or None
    content_sha256 = hashlib.sha256(content).hexdigest()
    content_md5 = hashlib.md5(content).hexdigest()
    asset_key = f"sticker:{content_sha256}"
    object_name = f"{PERSONA_STICKER_PREFIX}/{target_user_id}/{content_sha256}{file_ext}"

    await _upload_sticker_if_needed(
        PERSONA_STICKER_BUCKET,
        object_name,
        content,
        content_type,
    )

    asset = await PersonaStickerAsset.get_or_none(
        target_user_id=target_user_id,
        asset_key=asset_key,
    )
    if asset is None:
        try:
            await PersonaStickerAsset.create(
                target_user_id=target_user_id,
                sender_user_id=sender_user_id,
                asset_key=asset_key,
                content_sha256=content_sha256,
                content_md5=content_md5,
                bucket_name=PERSONA_STICKER_BUCKET,
                object_name=object_name,
                content_type=content_type,
                file_ext=file_ext,
                file_size=len(content),
                used_count=1,
                last_group_id=group_id,
                last_platform_message_id=platform_message_id,
                last_sender_name=_sender_name(event),
                source_file=source_file,
                source_url=source_url,
                raw_segment_json=segment,
            )
            return
        except IntegrityError:
            asset = await PersonaStickerAsset.get(
                target_user_id=target_user_id,
                asset_key=asset_key,
            )

    asset.used_count += 1
    asset.sender_user_id = sender_user_id
    asset.bucket_name = PERSONA_STICKER_BUCKET
    asset.object_name = object_name
    asset.content_type = content_type
    asset.file_ext = file_ext
    asset.file_size = len(content)
    asset.last_group_id = group_id
    asset.last_platform_message_id = platform_message_id
    asset.last_sender_name = _sender_name(event)
    asset.source_file = source_file
    asset.source_url = source_url
    asset.raw_segment_json = segment
    await asset.save()


async def save_persona_group_stickers(
    event: Any,
    target_user_ids: Sequence[str] | None = None,
) -> None:
    """保存 persona_mirror 已确认目标发出的表情包。

    这个函数只作为保存入口占位。调用方保证发送者已经是启用中的
    被模仿目标，才会进入这里。
    """
    sticker_segments = _iter_persona_sticker_segments(event)
    if not sticker_segments:
        return

    sender_user_id = str(getattr(event, "user_id", "") or "")
    effective_target_ids = [str(item) for item in (target_user_ids or []) if str(item)]
    if not effective_target_ids:
        effective_target_ids = [sender_user_id] if sender_user_id else []
    if not effective_target_ids:
        return

    target_user_id = effective_target_ids[0]
    for segment in sticker_segments:
        segment_data = segment.get("data", {})
        url = str(segment_data.get("url") or "")
        if not url:
            continue
        try:
            content, response_content_type = await _download_sticker_bytes(url)
            if not content:
                continue
            content_type, file_ext = _guess_image_info(
                content,
                response_content_type,
                url,
                str(segment_data.get("file") or ""),
            )
            if not content_type.startswith("image/"):
                logger.warning(f"跳过非图片表情包资源 {target_user_id}: {content_type}")
                continue
            await _upsert_persona_sticker_asset(
                event=event,
                target_user_id=target_user_id,
                segment=segment,
                content=content,
                content_type=content_type,
                file_ext=file_ext,
            )
        except Exception as exc:
            logger.error(f"persona_mirror 表情包保存失败 {target_user_id}: {exc}")


def download_video_code(url: str):
    download_video_dir = (
            Path(__file__).parent.parent.parent / "downloads" / "video"
    )
    download_video_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        'outtmpl': str(download_video_dir / '%(title)s.%(ext)s'),
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'retries': 10,
        'fragment_retries': 10,
        'ignoreerrors': True,
    }

    try:
        logger.info(f"正在准备解析: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        logger.success(f">>> 下载阶段完成: {url}")
    except Exception as e:
        logger.error(f"下载出错: {e}")
        raise e  # 抛出异常以便外层捕获


def object_exists(bucket, object_name) -> bool:
    try:
        minio_client.stat_object(bucket, object_name)
        return True
    except S3Error as e:
        if e.code == "NoSuchKey":
            return False
        raise


def sync_local_videos_to_minio():

    video_dir = Path(__file__).parent.parent.parent / "downloads" / "video"
    bucket_name = "big-file"

    if not video_dir.exists():
        logger.warning("下载目录不存在，跳过同步")
        return

    for video_file in video_dir.iterdir():
        if video_file.is_dir():
            continue

        if video_file.suffix == '.uploaded':
            continue

        if video_file.suffix not in SUPPORTED_EXTENSIONS:
            logger.debug(f"跳过非视频文件: {video_file.name}")
            continue

        object_name = f"movies/{video_file.name}"

        if object_exists(bucket_name, object_name):
            logger.info(f"MinIO已存在，标记为已上传: {video_file.name}")
            new_path = video_file.with_name(f"{video_file.name}.uploaded")
            video_file.rename(new_path)
            continue

        logger.warning(f"开始上传文件: {video_file.name}")

        try:
            minio_client.fput_object(
                bucket_name=bucket_name,
                object_name=object_name,
                file_path=str(video_file),
                content_type="video/mp4"
            )

            logger.success(f"上传完成: {video_file.name}")

            new_path = video_file.with_name(f"{video_file.name}.uploaded")
            video_file.rename(new_path)


        except Exception as e:
            logger.error(f"上传失败 {video_file.name}: {e}")


def task_workflow(url: str):
    # 1. 执行下载
    download_video_code(url)

    sync_local_videos_to_minio()
