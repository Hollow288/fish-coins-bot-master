from collections import defaultdict

from nonebot import get_bot
from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler

from .config import get_plugin_config
from .models import TelegramCheckinBinding
from .services.checkin_service import checkin_bindings, format_checkin_results


def _job_jitter() -> int | None:
    value = get_plugin_config().cron_jitter_seconds
    return value if value > 0 else None


@scheduler.scheduled_job(
    "cron",
    hour=get_plugin_config().cron_hour,
    minute=get_plugin_config().cron_minute,
    jitter=_job_jitter(),
    id="telegram_daily_checkin",
    max_instances=1,
    coalesce=True,
    misfire_grace_time=3600,
    timezone="Asia/Shanghai",
)
async def telegram_daily_checkin_job() -> None:
    config = get_plugin_config()
    if not config.scheduler_enabled:
        logger.info("[telegram_checkin] 自动签到已关闭，跳过本次任务。")
        return

    try:
        bindings = await TelegramCheckinBinding.filter(enabled=True).order_by(
            "qq_user_id", "id"
        )
    except Exception as exc:
        logger.error(f"[telegram_checkin] 查询自动签到任务失败: {exc}")
        return

    if not bindings:
        logger.info("[telegram_checkin] 没有启用中的签到任务。")
        return

    grouped: dict[str, list[TelegramCheckinBinding]] = defaultdict(list)
    for binding in bindings:
        grouped[binding.qq_user_id].append(binding)

    bot = None
    if config.scheduled_notify:
        try:
            bot = get_bot()
        except Exception as exc:
            logger.warning(f"[telegram_checkin] 无可用 QQ Bot，无法发送签到汇总: {exc}")

    for qq_user_id, user_bindings in grouped.items():
        results = await checkin_bindings(user_bindings)
        summary = format_checkin_results(results, automatic=True)
        logger.info(
            f"[telegram_checkin] QQ {qq_user_id} 自动签到执行完成，共 {len(results)} 项。"
        )
        if bot is None:
            continue
        try:
            await bot.send_private_msg(user_id=int(qq_user_id), message=summary)
        except Exception as exc:
            logger.error(
                f"[telegram_checkin] 私聊 QQ {qq_user_id} 发送签到汇总失败: {exc}"
            )
