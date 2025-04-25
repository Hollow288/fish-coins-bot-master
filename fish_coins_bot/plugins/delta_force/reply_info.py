from nonebot import on_notice, on_command
from nonebot.adapters.onebot.v11 import Bot, Event, PokeNotifyEvent, GroupMessageEvent
from nonebot.rule import Rule, to_me
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageSegment
from io import BytesIO
from fish_coins_bot.utils.image_utils import make_delta_force_room, make_delta_force_produce


def is_group_chat(event) -> bool:
    return isinstance(event, GroupMessageEvent)

reply_room = on_command(
    "密码房密码",
    rule=Rule(is_group_chat),
    aliases={"密码房", "三角洲密码房", "三角洲密码", "三角洲钥匙房","鼠鼠行动密码房","密码","今日密码"},
    priority=10,
    block=True,
)

@reply_room.handle()
async def reply_room_handle_function(args: Message = CommandArg()):

    room_image = await make_delta_force_room()
    # 检查文件是否存在
    if room_image is None:
        # 发送图片
        await reply_room.finish("哇哦,出错了~")
    else:
        buffer = BytesIO()
        room_image.save(buffer, format="PNG")
        buffer.seek(0)
        await reply_room.finish(MessageSegment.image(buffer))



reply_produce = on_command(
    "特勤处",
    rule=Rule(is_group_chat),
    aliases={"特勤处制作", "三角洲特勤处", "今天做什么", "三角洲特勤","鼠鼠行动做什么"},
    priority=10,
    block=True,
)

@reply_produce.handle()
async def reply_produce_handle_function(args: Message = CommandArg()):

    produce_image = await make_delta_force_produce()
    # 检查文件是否存在
    if produce_image is None:
        # 发送图片
        await reply_room.finish("哇哦,出错了~")
    else:
        buffer = BytesIO()
        produce_image.save(buffer, format="PNG")
        buffer.seek(0)
        await reply_produce.finish(MessageSegment.image(buffer))