from nonebot import on_notice, on_command
from nonebot.adapters.onebot.v11 import Bot, Event, PokeNotifyEvent, GroupMessageEvent
from nonebot.rule import Rule, to_me
from nonebot.log import logger
from nonebot import on_message
from nonebot.adapters import Message
from nonebot.params import CommandArg
from pathlib import Path
from nonebot.adapters.onebot.v11 import MessageSegment
import pytz
from datetime import datetime
import json
import random
import re
from fish_coins_bot.database.hotta.gacha_record import GachaRecord
from fish_coins_bot.utils.ai_client import call_text_api
from fish_coins_bot.utils.image_utils import render_gacha_result
from fish_coins_bot.utils.model_utils import update_last_two_results
from fish_coins_bot.plugins.persona_mirror.services.context_service import (
    get_recent_context_texts,
    record_bot_outgoing_message,
)
from fish_coins_bot.plugins.persona_mirror.utils import message_segments_to_list, render_segments_as_text
from fish_coins_bot.plugins.sticker_collector.models import StickerAsset
from fish_coins_bot.plugins.sticker_collector.services.picker_service import (
    get_sticker_segment,
    pick_candidates_for_reply,
)
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


# 用户回复机器人 或 @机器人 时触发；priority 设大一点，作为所有 @ 命令的兜底
# （help_menu 等 priority=10 的命令会先匹配并 block，命中后这里不会跑）
reply_handler_help = on_message(rule=to_me() & Rule(is_group_chat), priority=99, block=True)


_REPLY_FALLBACK = '听不懂,听不懂。@我并发送"帮助"获取指令菜单'


def _format_candidates_block(candidates: list[StickerAsset]) -> str:
    if not candidates:
        return "（暂无候选，本次只能纯文字回复）"
    lines = []
    for c in candidates:
        meaning = (c.sticker_meaning or "").strip() or "(无含义)"
        tag = c.emotion_tag or "其他"
        lines.append(f"- id={c.id} | 情绪={tag} | 含义={meaning}")
    return "\n".join(lines)


def _build_reply_prompt(
    context_lines: list[str],
    bot_original: str,
    user_reply: str,
    candidates: list[StickerAsset],
) -> str:
    context_block = "\n".join(context_lines) if context_lines else "（无）"
    bot_original_block = bot_original if bot_original else "（用户是 @ 你的，没有引用消息）"
    candidates_block = _format_candidates_block(candidates)
    valid_ids = ", ".join(str(c.id) for c in candidates) if candidates else "（无）"
    return (
        '你是幻塔（Tower of Fantasy）QQ 群助手。用户在群里 @ 了你 或 回复了你之前发的一条消息，'
        "请按下面的规则生成一句回复，并以严格 JSON 输出。\n\n"
        "【判断规则】\n"
        "1. 如果用户消息属于游戏数据/功能查询（角色、武器、武器面板、拟态、装备、副本、\n"
        "   抽卡、属性、版本、活动、攻略、掉落、声波、关卡奖励、\"你能查什么\"、\n"
        "   \"能不能问问xxx\"等），不要直接回答内容，text 固定填：\n"
        "   想查幻塔相关的话，@我并发送\"帮助\"获取指令菜单\n"
        "   这种情况 sticker_id 必须为 null（不带表情包）。\n"
        "2. 否则视为闲聊（问候、感谢、调侃、表情、夸赞、玩梗、\"你是谁\"之类的自我介绍\n"
        "   问答），用轻松口语化的语气回一句短话，不超过 30 字。\n"
        "   不要解释自己是 AI，不要装可怜，不要带 markdown 或图片链接。\n"
        "   这种情况下要积极挑选表情包，详见下文。\n\n"
        "【表情包候选】\n"
        "下面是从全局高频里挑出来的候选表情包，每张都标了 id、情绪标签和含义。\n"
        "只要某张表情包的情绪/含义和你想说的话不至于明显违和，就大方配上一张，\n"
        "让回复更生动、更像在群里玩梗。多数闲聊都可以配；\n"
        "只有当所有候选都明显不搭，才把 sticker_id 设为 null。\n"
        f"候选列表（合法 id：{valid_ids}）：\n"
        f"{candidates_block}\n\n"
        "【输出格式】\n"
        "只输出一个 JSON 对象，不要任何前后缀、解释、引号或 markdown 代码块：\n"
        '{"text": "要发的那句话", "sticker_id": <候选 id 之一 或 null>}\n'
        "- text：要发到群里的话本身，不要把表情包含义拼进去。\n"
        "- sticker_id：从上面候选里挑一个 id；不选就填 null。\n\n"
        "【最近群聊上下文（旧 → 新，每行一条 \"用户名: 内容\"）】\n"
        f"{context_block}\n\n"
        "【你之前发的、被用户回复的那条消息（仅在用户是\"回复\"时有内容）】\n"
        f"{bot_original_block}\n\n"
        "【用户这次发给你的内容】\n"
        f"{user_reply or '（空）'}\n"
    )


def _parse_reply_response(raw: str, valid_ids: set[int]) -> tuple[str, int | None]:
    """从 AI 返回里抽出 (text, sticker_id)。解析失败时把整段当作纯文字兜底。"""
    if not raw:
        return "", None
    text_raw = raw.strip()
    cleaned = text_raw
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    payload = None
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                payload = None

    if not isinstance(payload, dict):
        return text_raw, None

    text_val = payload.get("text")
    if not isinstance(text_val, str):
        text_val = "" if text_val is None else str(text_val)
    text_val = text_val.strip()

    sid_val = payload.get("sticker_id")
    sticker_id: int | None = None
    if isinstance(sid_val, bool):
        sticker_id = None
    elif isinstance(sid_val, int):
        sticker_id = sid_val
    elif isinstance(sid_val, str) and sid_val.strip().lstrip("-").isdigit():
        sticker_id = int(sid_val.strip())
    if sticker_id is not None and sticker_id not in valid_ids:
        logger.warning(
            f"hotta_wiki.reply AI 选了非候选 sticker_id={sticker_id}，已丢弃"
        )
        sticker_id = None

    return text_val, sticker_id


@reply_handler_help.handle()
async def handle_reply_help(bot: Bot, event: GroupMessageEvent):
    bot_original = ""
    if event.reply:
        bot_original = (
            render_segments_as_text(message_segments_to_list(event.reply.message))
            or event.reply.message.extract_plain_text()
        )
    user_reply = (
        render_segments_as_text(message_segments_to_list(event.message))
        or event.get_plaintext()
    )

    context_lines = get_recent_context_texts(
        event.group_id,
        limit=12,
        exclude_message_id=str(event.message_id),
    )

    try:
        candidates = await pick_candidates_for_reply(limit=15)
    except Exception as exc:
        logger.error(f"hotta_wiki.reply 表情包候选获取失败: {exc}")
        candidates = []

    prompt = _build_reply_prompt(
        context_lines, bot_original.strip(), user_reply.strip(), candidates
    )

    result = await call_text_api(
        prompt,
        memory_id=f"hotta-reply-{event.group_id}-{event.user_id}",
        fresh_memory_each_retry=True,
        retries=3,
        log_tag="hotta_wiki.reply",
    )

    bot_self_id = str(bot.self_id)
    group_id = event.group_id

    if not result:
        record_bot_outgoing_message(group_id, bot_self_id, _REPLY_FALLBACK)
        await reply_handler_help.finish(_REPLY_FALLBACK)
        return

    valid_ids = {c.id for c in candidates}
    text, sticker_id = _parse_reply_response(result, valid_ids)

    if sticker_id is None:
        out_text = text or _REPLY_FALLBACK
        record_bot_outgoing_message(group_id, bot_self_id, out_text)
        await reply_handler_help.finish(out_text)
        return

    segment = await get_sticker_segment(sticker_id)
    if segment is None:
        out_text = text or _REPLY_FALLBACK
        record_bot_outgoing_message(group_id, bot_self_id, out_text)
        await reply_handler_help.finish(out_text)
        return

    selected = next((c for c in candidates if c.id == sticker_id), None)
    meaning = (selected.sticker_meaning or "").strip() if selected else ""
    sticker_repr = f"[表情包:{meaning}]" if meaning else "[表情包]"

    if text:
        await bot.send(event, text)
        record_bot_outgoing_message(group_id, bot_self_id, f"{text} {sticker_repr}")
    else:
        record_bot_outgoing_message(group_id, bot_self_id, sticker_repr)

    await reply_handler_help.finish(segment)







