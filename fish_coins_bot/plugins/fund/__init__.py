from nonebot import require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_apscheduler")

from . import commands as commands  # noqa: F401
from . import scheduler as scheduler  # noqa: F401

__plugin_meta__ = PluginMetadata(
    name="fund",
    description="每天定时推送监控基金的速览长图；支持 添加基金/删除基金/基金走势 指令查看个人基金详情。",
    usage=(
        "添加基金 270042：绑定基金并开始监控；"
        "删除基金 270042：解除绑定；"
        "基金走势：生成个人绑定基金的详细点评长图（走势曲线 + AI 点评）。"
        "定时速览的目标群由 dynamics_list.json 的 fund 数组配置，"
        "其他参数通过 .env 中 FUND_* 配置控制。"
    ),
    type="application",
    homepage="https://github.com/nonebot/nonebot2",
    supported_adapters={"~onebot.v11"},
)
