import os
from dataclasses import dataclass
from functools import lru_cache

from fish_coins_bot.utils.admin_utils import parse_admin_ids


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int, minimum: int) -> int:
    if value is None:
        return default
    try:
        return max(int(value), minimum)
    except ValueError:
        return default


@dataclass(frozen=True)
class StickerCollectorConfig:
    collector_enabled: bool
    collector_max_size_bytes: int
    recognize_enabled: bool
    recognize_interval_minutes: int
    recognize_batch_size: int
    recognize_max_attempts: int
    recognize_throttle_ms: int
    blacklist_enabled: bool
    admin_ids: frozenset[str]


@lru_cache(maxsize=1)
def get_plugin_config() -> StickerCollectorConfig:
    return StickerCollectorConfig(
        collector_enabled=_parse_bool(os.getenv("STICKER_COLLECTOR_ENABLED"), default=True),
        collector_max_size_bytes=_parse_int(
            os.getenv("STICKER_COLLECTOR_MAX_SIZE_BYTES"), default=512000, minimum=1
        ),
        recognize_enabled=_parse_bool(os.getenv("STICKER_RECOGNIZE_ENABLED"), default=True),
        recognize_interval_minutes=_parse_int(
            os.getenv("STICKER_RECOGNIZE_INTERVAL_MINUTES"), default=10, minimum=1
        ),
        recognize_batch_size=_parse_int(
            os.getenv("STICKER_RECOGNIZE_BATCH_SIZE"), default=20, minimum=1
        ),
        recognize_max_attempts=_parse_int(
            os.getenv("STICKER_RECOGNIZE_MAX_ATTEMPTS"), default=3, minimum=1
        ),
        recognize_throttle_ms=_parse_int(
            os.getenv("STICKER_RECOGNIZE_THROTTLE_MS"), default=500, minimum=0
        ),
        blacklist_enabled=_parse_bool(os.getenv("STICKER_BLACKLIST_ENABLED"), default=True),
        admin_ids=parse_admin_ids(os.getenv("ADMIN_ID")),
    )
