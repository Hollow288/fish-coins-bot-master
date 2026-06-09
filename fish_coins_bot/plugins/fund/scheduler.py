from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler

from .config import get_plugin_config
from .services.push_service import run_daily_push


def _cron_hour() -> int:
    try:
        return get_plugin_config().cron_hour
    except Exception:
        return 19


def _cron_minute() -> int:
    try:
        return get_plugin_config().cron_minute
    except Exception:
        return 0


@scheduler.scheduled_job(
    "cron",
    hour=_cron_hour(),
    minute=_cron_minute(),
    id="fund_daily_push",
    max_instances=1,
    coalesce=True,
    timezone="Asia/Shanghai",
)
async def fund_daily_push_job() -> None:
    try:
        await run_daily_push()
    except Exception as exc:
        logger.error(f"[fund] 定时任务执行异常: {exc}")
