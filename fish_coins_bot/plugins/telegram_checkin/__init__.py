from nonebot import get_driver, require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_apscheduler")

from . import commands as commands  # noqa: E402, F401
from . import scheduler as scheduler  # noqa: E402, F401
from .services.telegram_client import disconnect_all_clients  # noqa: E402

__plugin_meta__ = PluginMetadata(
    name="telegram_checkin",
    description="使用绑定的 Telegram 个人号凭证定时或手动向机器人发送签到指令。",
    usage="@机器人 TG签到；绑定任务由管理员直接维护 telegram_checkin_binding 表。",
    type="application",
    homepage="https://github.com/nonebot/nonebot2",
    supported_adapters={"~onebot.v11"},
)


@get_driver().on_shutdown
async def shutdown_telegram_clients() -> None:
    await disconnect_all_clients()
