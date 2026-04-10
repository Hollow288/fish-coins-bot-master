from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler

from .config import get_plugin_config
from .models import PersonaTarget
from .services.summarizer_service import summarize_target


def _get_interval_minutes() -> int:
    try:
        return get_plugin_config().summary_interval_minutes
    except Exception:
        return 30


@scheduler.scheduled_job(
    "interval",
    minutes=_get_interval_minutes(),
    id="persona_mirror_incremental_summary",
)
async def persona_mirror_incremental_summary() -> None:
    config = get_plugin_config()
    if not config.scheduler_enabled:
        return

    targets = await PersonaTarget.filter(enabled=True)
    for target in targets:
        try:
            success, detail = await summarize_target(target, force=False)
            if success:
                logger.info(f"persona_mirror 自动总结成功: {target.target_user_id} - {detail}")
        except Exception as exc:
            logger.error(f"persona_mirror 自动总结失败 {target.target_user_id}: {exc}")
