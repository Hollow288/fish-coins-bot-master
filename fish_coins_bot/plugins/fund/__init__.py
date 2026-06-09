from nonebot import require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_apscheduler")

from . import scheduler as scheduler  # noqa: F401

__plugin_meta__ = PluginMetadata(
    name="fund",
    description="每天定时拉取监控基金的涨跌/风险数据，调用 AI 点评，渲染成长图推送到群。",
    usage="无指令交互，自动运行；通过 .env 中 FUND_* 配置控制推送时间、目标群、基金服务地址等。",
    type="application",
    homepage="https://github.com/nonebot/nonebot2",
    supported_adapters={"~onebot.v11"},
)
