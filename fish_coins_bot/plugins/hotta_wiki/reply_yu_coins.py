from nonebot import on_command
from nonebot.rule import Rule, to_me
from nonebot.adapters.onebot.v11 import GroupMessageEvent  # 仅适用于 OneBot 适配器
from nonebot.adapters import Message
from nonebot.params import CommandArg
from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment
from datetime import datetime, timedelta
from tortoise.expressions import Q

from fish_coins_bot.database.hotta.yu_coins import YuCoinsTaskWeekly, YuCoinsTaskWeeklyDetail
from fish_coins_bot.utils.model_utils import extract_yu_coins_type_id
from fish_coins_bot.utils.yu_coins_utils import select_or_add_this_weekly_yu_coins_weekly_id


def is_group_chat(event) -> bool:
    return isinstance(event, GroupMessageEvent)


yu_coins_type = on_command(
    "域币任务汇总",
    rule=to_me() & Rule(is_group_chat),  # 使用自定义规则
    aliases={"域币汇总", "每周域币任务汇总"},
    priority=10,
    block=True,
)


@yu_coins_type.handle()
async def yu_coins_type_img_handle_function(args: Message = CommandArg()):
    image_path = Path("/app/screenshots/yu-coins") / "yu-coins-task-type.png"

    # 检查文件是否存在
    if image_path.exists():
        # 发送图片
        image_message = MessageSegment.image(f"file://{image_path}")
        await yu_coins_type.finish(image_message)
    else:
        await yu_coins_type.finish("哇哦,图片找不到了~")


yu_coins_weekly = on_command(
    "本周域币任务",
    rule=to_me() & Rule(is_group_chat),  # 使用自定义规则
    aliases={"本周域币", "本周域币任务汇总"},
    priority=10,
    block=True,
)


@yu_coins_weekly.handle()
async def yu_coins_weekly_img_handle_function(args: Message = CommandArg()):
    image_path = Path("/app/screenshots/yu-coins") / "yu-coins-task-weekly.png"

    # 检查文件是否存在
    if image_path.exists():
        # 发送图片
        image_message = MessageSegment.image(f"file://{image_path}")
        await yu_coins_weekly.finish(image_message)
    else:
        await yu_coins_weekly.finish("哇哦,图片找不到了~")


add_yu_coins_weekly = on_command(
    "添加域币任务",
    rule=to_me() & Rule(is_group_chat),  # 使用自定义规则
    aliases={"添加域币", "添加任务"},
    priority=10,
    block=True,
)


@add_yu_coins_weekly.handle()
async def add_yu_coins_weekly_handle_function(event: GroupMessageEvent, args: Message = CommandArg()):
    if task_ids := args.extract_plain_text():

        user_id = event.sender.user_id  # 获取发送者的 QQ 号
        nickname = event.sender.nickname  # 获取发送者在群里的昵称

        # 需要添加到的本周域币任务主表ID
        task_weekly_id = await select_or_add_this_weekly_yu_coins_weekly_id()

        numbers = await extract_yu_coins_type_id(task_ids)


        for task_type_id in numbers:
            weekly_detail = await YuCoinsTaskWeeklyDetail.filter(del_flag="0", task_weekly_id=task_weekly_id,
                                                                  task_type_id=task_type_id).first()
            if not weekly_detail:
                await YuCoinsTaskWeeklyDetail.create(
                    task_weekly_id=task_weekly_id,
                    task_type_id=task_type_id,
                    task_weekly_contributors=f"{nickname}({user_id})",
                    del_flag="0"
                )
            else:
                weekly_detail.task_weekly_contributors = weekly_detail.task_weekly_contributors + f"、{nickname}({user_id})"
                await weekly_detail.save()
        await add_yu_coins_weekly.send("成功添加本周域币任务,使用'/刷新域币任务'更新记录,感谢贡献！")
    else:
        await add_yu_coins_weekly.finish("指令错误,例如: /添加域币任务 1 2 11 20 ")
