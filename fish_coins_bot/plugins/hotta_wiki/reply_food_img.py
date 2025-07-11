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

food = on_command(
    "食物图鉴",
    rule= Rule(is_group_chat),  # 使用自定义规则
    aliases={"食谱","食材图鉴","食材","烹饪图鉴","食物"},
    priority=10,
    block=True,
)

@food.handle()
async def food_img_handle_function(args: Message = CommandArg()):
    #
    if food_name := args.extract_plain_text():

        image_path = Path("/app/screenshots/food") / f"{food_name}.png"

        # 检查文件是否存在
        if image_path.exists():
            # 发送图片
            image_message = MessageSegment.image(f"file://{image_path}")
            await food.finish(image_message)
        else:
            await food.finish(f"没有找到食物名为 `{food_name}` 的图鉴,快联系作者催他收录吧~")
    else:
        await food.finish("指令错误,例如: 食物图鉴 滋滋烤肉")