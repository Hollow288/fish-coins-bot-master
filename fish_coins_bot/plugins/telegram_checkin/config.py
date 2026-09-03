import os
from dataclasses import dataclass
from functools import lru_cache


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(
    value: str | None,
    *,
    default: int,
    minimum: int,
    maximum: int | None = None,
) -> int:
    try:
        parsed = int(value) if value is not None else default
    except ValueError:
        return default
    parsed = max(parsed, minimum)
    return min(parsed, maximum) if maximum is not None else parsed


@dataclass(frozen=True)
class TelegramCheckinConfig:
    scheduler_enabled: bool
    scheduled_notify: bool
    cron_hour: int
    cron_minute: int
    cron_jitter_seconds: int
    reply_timeout_seconds: int
    task_interval_seconds: int


@lru_cache(maxsize=1)
def get_plugin_config() -> TelegramCheckinConfig:
    return TelegramCheckinConfig(
        scheduler_enabled=_parse_bool(
            os.getenv("TG_CHECKIN_SCHEDULER_ENABLED"), default=True
        ),
        scheduled_notify=_parse_bool(
            os.getenv("TG_CHECKIN_SCHEDULED_NOTIFY"), default=True
        ),
        cron_hour=_parse_int(
            os.getenv("TG_CHECKIN_CRON_HOUR"), default=8, minimum=0, maximum=23
        ),
        cron_minute=_parse_int(
            os.getenv("TG_CHECKIN_CRON_MINUTE"), default=0, minimum=0, maximum=59
        ),
        cron_jitter_seconds=_parse_int(
            os.getenv("TG_CHECKIN_CRON_JITTER_SECONDS"), default=600, minimum=0
        ),
        reply_timeout_seconds=_parse_int(
            os.getenv("TG_CHECKIN_REPLY_TIMEOUT_SECONDS"), default=30, minimum=1
        ),
        task_interval_seconds=_parse_int(
            os.getenv("TG_CHECKIN_TASK_INTERVAL_SECONDS"), default=2, minimum=0
        ),
    )
