from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler

from .config import get_plugin_config
from .services.recognize_service import run_pending_sticker_recognition


def _get_recognize_interval_minutes() -> int:
    try:
        return get_plugin_config().recognize_interval_minutes
    except Exception:
        return 10


@scheduler.scheduled_job(
    "interval",
    minutes=_get_recognize_interval_minutes(),
    id="sticker_collector_recognize",
    max_instances=1,
    coalesce=True,
)
async def sticker_recognize_job() -> None:
    config = get_plugin_config()
    if not config.recognize_enabled:
        return

    try:
        await run_pending_sticker_recognition()
    except Exception as exc:
        logger.error(f"sticker_collector 识别定时任务异常: {exc}")
