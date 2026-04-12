import os
from dataclasses import dataclass
from functools import lru_cache


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


def _parse_admin_ids(persona_admin_ids: str | None, fallback_admin_id: str | None) -> frozenset[str]:
    raw = persona_admin_ids or fallback_admin_id or ""
    admin_ids = [item.strip() for item in raw.split(",") if item.strip()]
    return frozenset(admin_ids)


@dataclass(frozen=True)
class PersonaMirrorConfig:
    text_api_uri: str | None
    text_api_key: str | None
    admin_ids: frozenset[str]
    summary_batch_size: int
    summary_sample_size: int
    speak_sample_size: int
    recent_context_size: int
    summary_interval_minutes: int
    scheduler_enabled: bool
    auto_reply_cooldown_seconds: int
    auto_reply_min_keyword_length: int
    auto_reply_min_message_count: int


@lru_cache(maxsize=1)
def get_plugin_config() -> PersonaMirrorConfig:
    return PersonaMirrorConfig(
        text_api_uri=os.getenv("PERSONA_TEXT_URI") or os.getenv("AI_TEXT_URI"),
        text_api_key=os.getenv("PERSONA_TEXT_APIKEY") or os.getenv("AI_TEXT_APIKEY"),
        admin_ids=_parse_admin_ids(os.getenv("PERSONA_ADMIN_IDS"), os.getenv("ADMIN_ID")),
        summary_batch_size=_parse_int(os.getenv("PERSONA_SUMMARY_BATCH_SIZE"), default=30, minimum=5),
        summary_sample_size=_parse_int(os.getenv("PERSONA_SUMMARY_SAMPLE_SIZE"), default=25, minimum=5),
        speak_sample_size=_parse_int(os.getenv("PERSONA_SPEAK_SAMPLE_SIZE"), default=8, minimum=3),
        recent_context_size=_parse_int(os.getenv("PERSONA_RECENT_CONTEXT_SIZE"), default=12, minimum=3),
        summary_interval_minutes=_parse_int(
            os.getenv("PERSONA_SUMMARY_INTERVAL_MINUTES"), default=30, minimum=5
        ),
        scheduler_enabled=_parse_bool(os.getenv("PERSONA_SCHEDULER_ENABLED"), default=True),
        auto_reply_cooldown_seconds=_parse_int(
            os.getenv("PERSONA_AUTO_REPLY_COOLDOWN_SECONDS"), default=180, minimum=0
        ),
        auto_reply_min_keyword_length=_parse_int(
            os.getenv("PERSONA_AUTO_REPLY_MIN_KEYWORD_LENGTH"), default=2, minimum=1
        ),
        auto_reply_min_message_count=_parse_int(
            os.getenv("PERSONA_AUTO_REPLY_MIN_MESSAGE_COUNT"), default=50, minimum=0
        ),
    )
