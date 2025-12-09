import os

from nonebot import on_command
from nonebot.rule import Rule, to_me
from nonebot.adapters.onebot.v11 import GroupMessageEvent  # 仅适用于 OneBot 适配器
from nonebot.adapters import Message
from nonebot.params import CommandArg
from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment

from fish_coins_bot.utils.model_utils import check_arms_alias


def is_group_chat(event) -> bool:
    return isinstance(event, GroupMessageEvent)

arms = on_command(
    "武器图鉴",
    rule= Rule(is_group_chat),  # 使用自定义规则
    aliases={"武器信息"},
    priority=10,
    block=True,
)

@arms.handle()
async def arms_img_handle_function(args: Message = CommandArg()):
    #
    if arms_name := args.extract_plain_text():
        arms_name = check_arms_alias(arms_name)

        image_path = Path("/app/screenshots/arms") / f"{arms_name}.png"

        # 检查文件是否存在
        if image_path.exists():
            # 发送图片
            image_message = MessageSegment.image(f"file://{image_path}")
            await arms.finish(image_message)
        # else:
        #     await arms.finish(f"没有找到武器名为 `{arms_name}` 的图鉴,快联系作者催他收录吧~")
    # else:
    #     await arms.finish("指令错误,例如: 武器图鉴 静澜")