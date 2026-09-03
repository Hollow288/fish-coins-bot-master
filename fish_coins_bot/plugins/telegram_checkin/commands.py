from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.log import logger
from nonebot.rule import to_me

from .models import TelegramCheckinBinding
from .services.checkin_service import checkin_bindings, format_checkin_results


telegram_checkin_cmd = on_command(
    "TG签到",
    rule=to_me(),
    priority=10,
    block=True,
)


@telegram_checkin_cmd.handle()
async def handle_telegram_checkin(event: MessageEvent) -> None:
    qq_user_id = str(event.user_id)
    try:
        bindings = await TelegramCheckinBinding.filter(
            qq_user_id=qq_user_id,
            enabled=True,
        ).order_by("id")
    except Exception as exc:
        logger.error(f"[telegram_checkin] 查询 QQ {qq_user_id} 的绑定失败: {exc}")
        await telegram_checkin_cmd.finish("查询 TG 签到任务失败，请稍后再试。")
        return

    if not bindings:
        await telegram_checkin_cmd.finish("你没有启用中的 TG 签到任务。")

    results = await checkin_bindings(list(bindings))
    await telegram_checkin_cmd.finish(
        format_checkin_results(results, automatic=False)
    )
