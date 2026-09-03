from nonebot.plugin import PluginMetadata

from .reply_translate import handle_reply_translate

__all__ = ["handle_reply_translate"]

__plugin_meta__ = PluginMetadata(
    name="翻译插件",
    description="回复图片或文本并发送“翻译”，自动翻译图片或文本内容。",
    usage="回复任意消息发送“翻译”；被回复消息含图片时走图片翻译，否则翻译被回复文本。",
    type="application",
    homepage="https://github.com/nonebot/nonebot2",
    supported_adapters={"~onebot.v11"},
)
