from nonebot import require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_apscheduler")

from . import dynamics_push as dynamics_push  # noqa: F401

__plugin_meta__ = PluginMetadata(
    name="x_monitor",
    description="监控 X/Twitter 用户推文，截图后推送到 QQ 群。",
    usage="配置 dynamics_list.json 的 x 段和 X_AUTH_TOKEN/X_CT0/X_TWID 后自动运行。",
    type="application",
    homepage="https://github.com/nonebot/nonebot2",
    supported_adapters={"~onebot.v11"},
)
