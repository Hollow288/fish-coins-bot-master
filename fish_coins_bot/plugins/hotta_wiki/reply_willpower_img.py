import os

from nonebot import on_command
from nonebot.rule import Rule, to_me
from nonebot.adapters.onebot.v11 import GroupMessageEvent  # 仅适用于 OneBot 适配器
from nonebot.adapters import Message
from nonebot.params import CommandArg
from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment

from fish_coins_bot.utils.model_utils import check_willpower_alias


def is_group_chat(event) -> bool:
    return isinstance(event, GroupMessageEvent)

willpower = on_command(
    "意志图鉴",
    rule=to_me() & Rule(is_group_chat),  # 使用自定义规则
    aliases={"意志"},
    priority=10,
    block=True,
)

@willpower.handle()
async def willpower_img_handle_function(args: Message = CommandArg()):
    #
    if willpower_name := args.extract_plain_text():
        willpower_name = check_willpower_alias(willpower_name)

        image_path = Path("/app/screenshots/willpower") / f"{willpower_name}.png"

        # 检查文件是否存在
        if image_path.exists():
            # 发送图片
            image_message = MessageSegment.image(f"file://{image_path}")
            await willpower.finish(image_message)
        else:
            await willpower.finish(f"没有找到意志名为 `{willpower_name}` 的图鉴,快联系作者催他收录吧~")
    else:
        await willpower.finish("指令错误,例如: /意志图鉴 烈烈红莲")