from nonebot import require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_apscheduler")

from . import collector as collector  # noqa: F401
from . import scheduler as scheduler  # noqa: F401

__plugin_meta__ = PluginMetadata(
    name="sticker_collector",
    description="全局采集所有群聊/私聊表情包，上传 MinIO 去重，并定时调用 AI 识别含义。",
    usage="无指令交互，自动运行；通过 .env 中 STICKER_* 配置控制。",
    type="application",
    homepage="https://github.com/nonebot/nonebot2",
    supported_adapters={"~onebot.v11"},
)
