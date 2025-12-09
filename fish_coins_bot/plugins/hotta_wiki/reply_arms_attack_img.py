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

arms_attack = on_command(
    "武器详情",
    rule= Rule(is_group_chat),  # 使用自定义规则
    aliases={"武器攻击","武器模组图鉴","模组图鉴","攻击模组图鉴","攻击图鉴","武器模组"},
    priority=10,
    block=True,
)

@arms_attack.handle()
async def arms_attack_img_handle_function(args: Message = CommandArg()):
    #
    if arms_attack_name := args.extract_plain_text():
        arms_attack_name = check_arms_alias(arms_attack_name)

        image_path = Path("/app/screenshots/arms-attack") / f"{arms_attack_name}.png"

        # 检查文件是否存在
        if image_path.exists():
            # 发送图片
            image_message = MessageSegment.image(f"file://{image_path}")
            await arms_attack.finish(image_message)
        # else:
            # await arms_attack.finish(f"没有找到武器名为 `{arms_attack_name}` 的详情图鉴,快联系作者催他收录吧~")
    # else:
        # await arms_attack.finish("指令错误,例如: 武器详情 静澜")