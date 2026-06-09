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


def _parse_group_ids(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    return frozenset(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class FundPluginConfig:
    push_enabled: bool
    api_base_url: str
    group_ids: frozenset[str]
    cron_hour: int
    cron_minute: int
    trend_days: int
    request_timeout_seconds: int
    ai_enabled: bool
    admin_ids: frozenset[str]


@lru_cache(maxsize=1)
def get_plugin_config() -> FundPluginConfig:
    return FundPluginConfig(
        push_enabled=_parse_bool(os.getenv("FUND_PUSH_ENABLED"), default=True),
        api_base_url=(
            os.getenv("FUND_API_BASE_URL") or "http://127.0.0.1:5777/api/v1/fund"
        ).rstrip("/"),
        group_ids=_parse_group_ids(os.getenv("FUND_PUSH_GROUP_IDS")),
        cron_hour=_parse_int(os.getenv("FUND_PUSH_CRON_HOUR"), default=19, minimum=0),
        cron_minute=_parse_int(os.getenv("FUND_PUSH_CRON_MINUTE"), default=0, minimum=0),
        trend_days=_parse_int(os.getenv("FUND_TREND_DAYS"), default=90, minimum=2),
        request_timeout_seconds=_parse_int(
            os.getenv("FUND_REQUEST_TIMEOUT_SECONDS"), default=20, minimum=1
        ),
        ai_enabled=_parse_bool(os.getenv("FUND_AI_ENABLED"), default=True),
        admin_ids=parse_admin_ids(os.getenv("ADMIN_ID")),
    )
