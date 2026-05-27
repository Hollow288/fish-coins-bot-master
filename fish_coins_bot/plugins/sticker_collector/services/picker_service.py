"""为 AI 回复挑选候选表情包：从已识别且适合作表情包的资产里按情绪分桶抽样，并加内存缓存。"""

import asyncio
import random
import time
from collections import defaultdict, deque
from io import BytesIO

from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.log import logger
from tortoise import connections

from fish_coins_bot.utils.minio_client import minio_client

from ..models import StickerAsset


_CACHE_TTL_SECONDS = 300
_POOL_SIZE = 50
_UNIQUE_USER_SCORE_WEIGHT = 10.0

_cache_lock = asyncio.Lock()
_cache: dict[str, object] = {"expires_at": 0.0, "pool": []}
_GROUP_RECENT_REPLY_STICKERS: defaultdict[str, deque[int | None]] = defaultdict(
    lambda: deque(maxlen=2)
)


def record_bot_reply_sticker_usage(
    group_id: str | int,
    sticker_id: int | None,
) -> None:
    """记录机器人一次回复是否发了表情包，用于抑制连续重复。"""
    _GROUP_RECENT_REPLY_STICKERS[str(group_id)].append(sticker_id)


def get_temporarily_blocked_sticker_ids(group_id: str | int) -> set[int]:
    """如果同一张表情包连续发了两次，下一次候选里临时排除它。"""
    recent = list(_GROUP_RECENT_REPLY_STICKERS.get(str(group_id), []))
    if len(recent) == 2 and recent[0] is not None and recent[0] == recent[1]:
        return {recent[0]}
    return set()


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
    try:
        rows = await connections.get("default").execute_query_dict(
            """
            SELECT
              a.id
            FROM sticker_asset a
            LEFT JOIN (
              SELECT sticker_id, COUNT(*) AS unique_user_count
              FROM sticker_usage
              GROUP BY sticker_id
            ) u ON u.sticker_id = a.id
            WHERE a.is_suitable_sticker = 1
              AND a.recognize_status = 'done'
            ORDER BY
              COALESCE(u.unique_user_count, 0) * %s + LOG(1 + a.used_count) DESC,
              a.used_count DESC,
              a.id DESC
            LIMIT %s
            """,
            [_UNIQUE_USER_SCORE_WEIGHT, _POOL_SIZE],
        )
    except Exception as exc:
        logger.error(f"sticker picker 综合分排序失败，退回总次数排序: {exc}")
        return list(await (
            StickerAsset
            .filter(is_suitable_sticker=True, recognize_status="done")
            .order_by("-used_count", "-id")
            .limit(_POOL_SIZE)
        ))

    ordered_ids = [int(row["id"]) for row in rows]
    if not ordered_ids:
        return []

    assets = await StickerAsset.filter(id__in=ordered_ids)
    asset_by_id = {asset.id: asset for asset in assets}
    return [
        asset_by_id[sticker_id]
        for sticker_id in ordered_ids
        if sticker_id in asset_by_id
    ]


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


async def pick_candidates_for_reply(
    limit: int = 15,
    exclude_ids: set[int] | None = None,
) -> list[StickerAsset]:
    """挑 limit 张表情包，先从完整候选池排除指定 id，再按情绪桶补足抽样。"""
    pool = await _get_pool()
    if exclude_ids:
        pool = [asset for asset in pool if asset.id not in exclude_ids]
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
