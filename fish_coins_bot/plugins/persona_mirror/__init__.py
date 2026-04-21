from nonebot import require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_apscheduler")

from . import auto_reply as auto_reply  # noqa: F401
from . import collector as collector  # noqa: F401
from . import commands as commands  # noqa: F401
from . import scheduler as scheduler  # noqa: F401

__plugin_meta__ = PluginMetadata(
    name="persona_mirror",
    description="Collect target user's messages, summarize habits, and generate replies in that style.",
    usage=(
        "指令:\n"
        "  人设绑定 <QQ号> [备注名]\n"
        "  人设开启 <QQ号>\n"
        "  人设关闭 <QQ号>\n"
        "  人设关键词 <QQ号> <关键词1> [关键词2] ...\n"
        "  人设看关键词 [QQ号]\n"
        "  人设资料 <QQ号> <一句话基本信息>\n"
        "  人设标签 <QQ号> <一句话性格描述>\n"
        "  人设看资料 [QQ号]\n"
        "  人设纠正 <QQ号> <自然语言纠正>\n"
        "  人设看画像 [QQ号]\n"
        "  人设状态\n"
        "  人设总结 [QQ号]\n"
        "  学他说话 [QQ号] <想表达的话>"
    ),
    type="application",
    homepage="https://github.com/nonebot/nonebot2",
    supported_adapters={"~onebot.v11"},
)
