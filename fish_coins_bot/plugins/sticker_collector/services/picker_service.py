"""为 AI 回复挑选候选表情包：从已识别且适合作表情包的资产里按情绪分桶抽样，并加内存缓存。"""

import asyncio
import random
import time
from io import BytesIO

from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.log import logger

from fish_coins_bot.utils.minio_client import minio_client

from ..models import StickerAsset


_CACHE_TTL_SECONDS = 300
_POOL_SIZE = 50

_cache_lock = asyncio.Lock()
_cache: dict[str, object] = {"expires_at": 0.0, "pool": []}


async def _fetch_object_bytes(bucket_name: str, object_name: str) -> bytes:
    def _read() -> bytes:
        response = minio_client.get_object(bucket_name, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    return await asyncio.to_thread(_read)


async def _refresh_pool() -> list[StickerAsset]:
    pool = await (
        StickerAsset
        .filter(is_suitable_sticker=True, recognize_status="done")
        .order_by("-used_count", "-id")
        .limit(_POOL_SIZE)
    )
    return list(pool)


async def _get_pool() -> list[StickerAsset]:
    now = time.monotonic()
    expires_at = float(_cache.get("expires_at") or 0.0)
    pool = _cache.get("pool") or []
    if expires_at > now and pool:
        return pool  # type: ignore[return-value]

    async with _cache_lock:
        now = time.monotonic()
        expires_at = float(_cache.get("expires_at") or 0.0)
        pool = _cache.get("pool") or []
        if expires_at > now and pool:
            return pool  # type: ignore[return-value]

        fresh = await _refresh_pool()
        _cache["pool"] = fresh
        _cache["expires_at"] = now + _CACHE_TTL_SECONDS
        logger.info(f"sticker picker 刷新候选池: {len(fresh)} 张")
        return fresh


def _sample_by_emotion(pool: list[StickerAsset], limit: int) -> list[StickerAsset]:
    if not pool or limit <= 0:
        return []
    if len(pool) <= limit:
        shuffled = list(pool)
        random.shuffle(shuffled)
        return shuffled

    buckets: dict[str, list[StickerAsset]] = {}
    for asset in pool:
        tag = asset.emotion_tag or "其他"
        buckets.setdefault(tag, []).append(asset)

    for items in buckets.values():
        random.shuffle(items)

    bucket_keys = list(buckets.keys())
    random.shuffle(bucket_keys)

    picked: list[StickerAsset] = []
    while bucket_keys and len(picked) < limit:
        for key in list(bucket_keys):
            if not buckets[key]:
                bucket_keys.remove(key)
                continue
            picked.append(buckets[key].pop())
            if len(picked) >= limit:
                break
    return picked


async def pick_candidates_for_reply(limit: int = 15) -> list[StickerAsset]:
    """挑 limit 张表情包，覆盖尽量多的情绪桶，5 分钟缓存。"""
    pool = await _get_pool()
    return _sample_by_emotion(pool, limit)


async def get_sticker_segment(sticker_id: int) -> MessageSegment | None:
    """根据 sticker_id 取出 OneBot 图片消息段，找不到或拉取失败返回 None。"""
    asset = await StickerAsset.get_or_none(id=sticker_id)
    if asset is None or not asset.bucket_name or not asset.object_name:
        return None
    try:
        content = await _fetch_object_bytes(asset.bucket_name, asset.object_name)
    except Exception as exc:
        logger.error(f"sticker picker 拉取表情包失败 #{sticker_id}: {exc}")
        return None
    segment = MessageSegment.image(BytesIO(content))
    segment.data["sub_type"] = 1
    return segment
