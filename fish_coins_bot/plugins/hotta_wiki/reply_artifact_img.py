import os

from nonebot import on_command
from nonebot.rule import Rule, to_me
from nonebot.adapters.onebot.v11 import GroupMessageEvent  # 仅适用于 OneBot 适配器
from nonebot.adapters import Message
from nonebot.params import CommandArg
from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment

from fish_coins_bot.utils.model_utils import check_artifact_alias


def is_group_chat(event) -> bool:
    return isinstance(event, GroupMessageEvent)

artifact = on_command(
    "源器图鉴",
    rule= Rule(is_group_chat),  # 使用自定义规则
    aliases={"源器"},
    priority=10,
    block=True,
)

@artifact.handle()
async def artifact_img_handle_function(args: Message = CommandArg()):
    #
    if artifact_name := args.extract_plain_text():
        artifact_name = check_artifact_alias(artifact_name)

        image_path = Path("/app/screenshots/artifact") / f"{artifact_name}.png"

        # 检查文件是否存在
        if image_path.exists():
            # 发送图片
            image_message = MessageSegment.image(f"file://{image_path}")
            await artifact.finish(image_message)
        # else:
        #     await artifact.finish(f"没有找到源器名为 `{artifact_name}` 的图鉴,快联系作者催他收录吧~")
    # else:
    #     await artifact.finish("指令错误,例如: 源器图鉴 阻断装置")