import os

from nonebot import on_command
from nonebot.rule import Rule, to_me
from nonebot.adapters.onebot.v11 import GroupMessageEvent  # 仅适用于 OneBot 适配器
from nonebot.adapters import Message
from nonebot.params import CommandArg
from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment


def is_group_chat(event) -> bool:
    return isinstance(event, GroupMessageEvent)

fashion = on_command(
    "时装图鉴",
    rule= Rule(is_group_chat),  # 使用自定义规则
    aliases={"时装"},
    priority=10,
    block=True,
)

@fashion.handle()
async def fashion_img_handle_function(args: Message = CommandArg()):
    #
    if fashion_name := args.extract_plain_text():

        image_path = Path("/app/screenshots/fashion") / f"{fashion_name}.png"

        # 检查文件是否存在
        if image_path.exists():
            # 发送图片
            image_message = MessageSegment.image(f"file://{image_path}")
            await fashion.finish(image_message)
        # else:
            # await fashion.finish(f"没有找到时装名为 `{fashion_name}` 的图鉴,快联系作者催他收录吧~")
    # else:
    #     await fashion.finish("指令错误,例如: 时装图鉴 锦龙吟")