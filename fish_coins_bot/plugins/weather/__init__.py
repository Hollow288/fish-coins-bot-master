from nonebot import on_command
from nonebot.rule import Rule, to_me
from nonebot.adapters.onebot.v11 import GroupMessageEvent  # 仅适用于 OneBot 适配器
from nonebot.adapters import Message
from nonebot.params import CommandArg

def is_group_chat(event) -> bool:
    return isinstance(event, GroupMessageEvent)

weather = on_command(
    "天气",
    rule=to_me() & Rule(is_group_chat),  # 使用自定义规则
    aliases={"weather", "查天气"},
    priority=10,
    block=True,
)

@weather.handle()
async def handle_function(args: Message = CommandArg()):
    # 提取参数纯文本作为地名，并判断是否有效
    if location := args.extract_plain_text():
        await weather.finish(f"今天{location}的天气是...")
    else:
        await weather.finish("请输入地名")