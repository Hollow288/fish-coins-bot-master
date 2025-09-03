from nonebot import on_notice, on_command
from nonebot.adapters.onebot.v11 import Bot, Event, PokeNotifyEvent, GroupMessageEvent
from nonebot.rule import Rule, to_me
from nonebot.log import logger
from nonebot.adapters import Message
from nonebot.params import CommandArg
from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment
import pytz
from datetime import datetime
import json
import random
from fish_coins_bot.database.hotta.gacha_record import GachaRecord
from fish_coins_bot.utils.image_utils import render_gacha_result
from fish_coins_bot.utils.model_utils import update_last_two_results
from io import BytesIO

def is_poke_me(event: Event) -> bool:
    return isinstance(event, PokeNotifyEvent) and event.target_id == event.self_id and event.group_id is not None

poke_me = on_notice(rule=Rule(is_poke_me))

@poke_me.handle()
async def handle_poke_event(bot: Bot, event: PokeNotifyEvent):
    user_id = event.user_id
    group_id = event.group_id

    tz = pytz.timezone('Asia/Shanghai')
    utc8_time = datetime.now(tz)
    hour = utc8_time.hour

    if 5 <= hour < 11:
        greeting = "早上好"
    elif 11 <= hour < 13:
        greeting = "中午好"
    elif 13 <= hour < 18:
        greeting = "下午好"
    else:
        greeting = "晚上好"

    # 发送回复消息
    await bot.send_group_msg(group_id=group_id, message=f"授权者{greeting},@我并发送\"帮助\"获取指令菜单哦✨")



def is_group_chat(event) -> bool:
    return isinstance(event, GroupMessageEvent)

help_menu = on_command(
    "帮助",
    rule=to_me() & Rule(is_group_chat),
    aliases={"help", "菜单"},
    priority=10,
    block=True,
)

@help_menu.handle()
async def help_menu_handle_function(args: Message = CommandArg()):
    image_path = Path("/app/screenshots/common") / "wiki-help.png"

    # 检查文件是否存在
    if image_path.exists():
        # 发送图片
        image_message = MessageSegment.image(f"file://{image_path}")
        await help_menu.finish(image_message)
    else:
        await help_menu.finish("哇哦,图片找不到了~")


gacha = on_command(
    "塔塔抽卡",
    rule= Rule(is_group_chat),  # 使用自定义规则
    aliases={"幻塔抽卡","幻塔十连","塔塔十连"},
    priority=10,
    block=True,
)


@gacha.handle()
async def gacha_handle_function(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):

    # 获取发送者的 QQ 号
    user_id = event.sender.user_id
    # 发送者的抽卡记录
    gacha_record = await GachaRecord.filter(user_id=user_id).first()

    if gacha_record:
        # 判断是否为今天
        now = datetime.now()
        last_time = gacha_record.update_time

        if last_time and last_time.date() == now.date():
            # 如果是今天已经抽过了
            await gacha.send(MessageSegment.at(user_id) + " 今天已经抽过了哦✨")
            return


    if not gacha_record:
        gacha_record = await GachaRecord.create(
            user_id=user_id,
            ssr_gacha_count = 0,
            sr_gacha_count = 0,
            gacha_total = 0,
            ssr_total = 0,
            update_time = datetime.now()
        )


    #开始实际的逻辑处理
    with open(Path(__file__).parent / 'gacha_config.json', 'r', encoding='utf-8') as f:
        gacha_config = json.load(f)

    ssr_probability = gacha_config.get("settings", {}).get("ssr_probability", 0)
    sr_probability = gacha_config.get("settings", {}).get("sr_probability", 0)
    up_characters = gacha_config.get("settings", {}).get("up_characters", '')
    ssr_list = gacha_config.get("banner", {}).get("SSR", [])
    sr_list = gacha_config.get("banner", {}).get("SR", [])
    r_list = gacha_config.get("banner", {}).get("R", [])
    characters_config = gacha_config.get("characters_config", {})

    #记录基本属性,SR累计次数,中歪记录
    # 80SSR循环内累计次数
    ssr_gacha_count = gacha_record.ssr_gacha_count
    # 10SR循环内累计次数
    sr_gacha_count = gacha_record.sr_gacha_count
    # 最近两次SSR中歪记录
    last_two_ssr_up_results = gacha_record.last_two_ssr_up_results
    # 用户总累计抽卡次数
    gacha_total = gacha_record.gacha_total
    # 用户总累计出SSR次数
    ssr_total = gacha_record.ssr_total

    results = []  # 存储抽卡结果，最终传给画图方法的数组

    for _ in range(10):
        rand = random.random()  # [0.0, 1.0) 的随机小数

        # 本次SR概率 这里官方只说明每次概率为1% 但是似乎并不是每次都是1%
        if sr_gacha_count == 8:
            this_sr_probability = 0.34
        elif sr_gacha_count == 9:
            this_sr_probability = 0.67
        else:
            this_sr_probability = sr_probability  # 原本的默认概率

        if rand < ssr_probability or ssr_gacha_count >= 79:

            if last_two_ssr_up_results == '歪歪':
                # 连续两次没中UP，这次必中UP
                character_name = up_characters
                last_two_ssr_up_results = '歪中'
            elif last_two_ssr_up_results == '中中':
                # 连续两次都中UP，这次必中歪（非UP）
                # 去掉up角色再抽
                character_name = random.choice(ssr_list)
                last_two_ssr_up_results = '中歪'
            else:
                # 50% 概率中UP
                if random.random() < 0.5:
                    character_name = up_characters
                    this_result = "中"
                else:
                    character_name = random.choice(ssr_list)
                    this_result = "歪"

                last_two_ssr_up_results = update_last_two_results(last_two_ssr_up_results, this_result)

            config = characters_config.get(character_name, characters_config.get("默认"))
            # 加入抽卡结果
            results.append({
                "name": character_name,
                "quality": "SSR",
                "characters_x": config.get("characters_x"),
                "characters_y": config.get("characters_y"),
                "name_x": config.get("name_x"),
                "name_y": config.get("name_y"),
            })

            ssr_gacha_count = 0  # 重置SSR累计次数
            sr_gacha_count = 0  # 重置SR累计次数
            ssr_total += 1

        elif rand < this_sr_probability + ssr_probability or sr_gacha_count >= 9:
            # 出 SR
            character_name = random.choice(sr_list)
            config = characters_config.get(character_name, characters_config.get("默认"))
            # 加入抽卡结果
            results.append({
                "name": character_name,
                "quality": "SR",
                "characters_x": config.get("characters_x"),
                "characters_y": config.get("characters_y"),
                "name_x": config.get("name_x"),
                "name_y": config.get("name_y"),
            })
            sr_gacha_count = 0  # 重置SR累计次数
            ssr_gacha_count += 1
        else:
            # 出 R
            character_name = random.choice(r_list)
            config = characters_config.get(character_name, characters_config.get("默认"))
            # 加入抽卡结果
            results.append({
                "name": character_name,
                "quality": "R",
                "characters_x": config.get("characters_x"),
                "characters_y": config.get("characters_y"),
                "name_x": config.get("name_x"),
                "name_y": config.get("name_y"),
            })
            sr_gacha_count += 1
            ssr_gacha_count += 1

        gacha_total += 1  # 总抽卡数 +1

    # 保存本次十连结果
    gacha_record.ssr_gacha_count = ssr_gacha_count
    gacha_record.sr_gacha_count = sr_gacha_count
    gacha_record.ssr_total = ssr_total
    gacha_record.gacha_total = gacha_total
    gacha_record.last_two_ssr_up_results = last_two_ssr_up_results
    gacha_record.update_time = datetime.now()
    await gacha_record.save()

    # 将数组传给制图方法

    gacha_img = render_gacha_result(results)

    buf = BytesIO()
    gacha_img.save(buf, format="PNG")
    buf.seek(0)

    # 构建消息并发送：艾特用户 + 图片
    await bot.send(
        event,
        MessageSegment.at(user_id) + MessageSegment.image(buf)
    )











