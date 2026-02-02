import os
import asyncio

from dotenv import load_dotenv
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot import  on_command
from nonebot.rule import Rule, to_me
from nonebot.adapters import Message
from nonebot.params import CommandArg

from fish_coins_bot.utils.downloads import task_workflow

load_dotenv()


ADMIN_ID = os.getenv("ADMIN_ID")

def is_private_chat(event) -> bool:
    return isinstance(event, PrivateMessageEvent)

download_video = on_command(
    "下载视频",
    rule=Rule(is_private_chat),
    aliases={"视频"},
    priority=10,
    block=True,
)


@download_video.handle()
async def reply_download_video_handle(bot: Bot, event: PrivateMessageEvent, args: Message = CommandArg()):
    user_id = str(event.sender.user_id)
    if str(user_id) == str(ADMIN_ID):
        if message := args.extract_plain_text():
            asyncio.create_task(
                asyncio.to_thread(task_workflow, message)
            )
            await download_video.send("🎬 已在后台开始下载")
        else:
            await download_video.send("请携带视频地址")