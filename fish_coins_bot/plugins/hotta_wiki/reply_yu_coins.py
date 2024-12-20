from nonebot import on_command
from nonebot.rule import Rule
from nonebot.adapters.onebot.v11 import GroupMessageEvent  # 仅适用于 OneBot 适配器
from nonebot.adapters import Message
from nonebot.params import CommandArg
from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment

from fish_coins_bot.database.hotta.yu_coins import YuCoinsTaskWeeklyDetail
from fish_coins_bot.utils.image_utils import flushed_yu_nuo_weekly_images
from fish_coins_bot.utils.model_utils import extract_yu_coins_type_id
from fish_coins_bot.utils.yu_coins_utils import select_or_add_this_weekly_yu_coins_weekly_id


def is_group_chat(event) -> bool:
    return isinstance(event, GroupMessageEvent)



yu_coins_type = on_command(
    "域币任务汇总",
    rule= Rule(is_group_chat),  # 使用自定义规则
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
    rule= Rule(is_group_chat),  # 使用自定义规则
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
    rule= Rule(is_group_chat),  # 使用自定义规则
    aliases={"添加域币"},
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
            weekly_detail = await YuCoinsTaskWeeklyDetail.filter(task_weekly_id=task_weekly_id,
                                                                  task_type_id=task_type_id).first()
            if not weekly_detail:
                await YuCoinsTaskWeeklyDetail.create(
                    task_weekly_id=task_weekly_id,
                    task_type_id=task_type_id,
                    task_weekly_contributors=f"{nickname}({user_id})",
                    del_flag="0"
                )
                continue
            else:
                if str(user_id) in weekly_detail.task_weekly_contributors:
                    if weekly_detail.del_flag == "0":
                        # 如果用户已经存在且未被删除，则跳过
                        continue
                    else:
                        # 如果用户存在但已删除，恢复该任务并更新
                        weekly_detail.del_flag = "0"
                        # 如果没有该用户，则将用户加入到贡献者列表
                        if str(user_id) not in weekly_detail.task_weekly_contributors:
                            weekly_detail.task_weekly_contributors += f"、{nickname}({user_id})"
                else:
                    # 如果该用户还没有贡献过，加入到 task_weekly_contributors 中
                    weekly_detail.task_weekly_contributors += f"、{nickname}({user_id})"
                    weekly_detail.del_flag = "0"
            # 保存更新后的记录
            await weekly_detail.save()
        await add_yu_coins_weekly.send("成功添加本周域币任务☀️\n使用'/刷新域币任务'指令以更新记录,感谢贡献！")
    else:
        await add_yu_coins_weekly.finish("指令错误,例如: /添加域币任务 1 2 11 20 ")


flushed_yu_coins_weekly = on_command(
    "刷新域币任务",
    rule= Rule(is_group_chat),  # 使用自定义规则
    aliases={"刷新本周域币", "刷新域币"},
    priority=10,
    block=True,
)

@flushed_yu_coins_weekly.handle()
async def flushed_yu_coins_weekly_handle_function(args: Message = CommandArg()):
    return await flushed_yu_nuo_weekly_images(flushed_yu_coins_weekly,"域币")

delete_yu_coins_weekly = on_command(
    "删除域币任务",
    rule= Rule(is_group_chat),  # 使用自定义规则
    aliases={"删除域币"},
    priority=10,
    block=True,
)

@delete_yu_coins_weekly.handle()
async def delete_yu_coins_weekly_handle_function(event: GroupMessageEvent, args: Message = CommandArg()):
    if task_ids := args.extract_plain_text():

        # 需要删除的本周域币明细ID
        numbers = await extract_yu_coins_type_id(task_ids)

        for weekly_detail_id in numbers:
            weekly_detail = await YuCoinsTaskWeeklyDetail.filter(weekly_detail_id=weekly_detail_id).first()
            if not weekly_detail:
                continue
            else:
                weekly_detail.del_flag = "1"
            # 保存更新后的记录
            await weekly_detail.save()
        await add_yu_coins_weekly.send("成功删除本周域币任务☀️\n使用'/刷新域币任务'指令以更新记录,感谢贡献！")
    else:
        await add_yu_coins_weekly.finish("指令错误,例如: /删除域币任务 1 2 11 20 ")