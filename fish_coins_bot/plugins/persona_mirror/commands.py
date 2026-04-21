from collections import Counter

from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageEvent, MessageSegment
from nonebot.params import CommandArg

from .auto_reply import invalidate_target_cache
from .config import get_auto_reply_cooldown, set_auto_reply_cooldown
from .models import PersonaAsset, PersonaMessage
from .profile_schema import normalize_manual_profile, normalize_v2_profile
from .services.context_service import get_recent_group_context
from .services.persona_service import (
    add_correction,
    bind_target,
    get_effective_trigger_keywords,
    get_manual_profile,
    get_profile_state,
    list_correction_dicts,
    list_targets,
    refresh_profile_state,
    resolve_target,
    set_target_enabled,
    set_trigger_keywords,
    update_manual_basic_info,
    update_manual_persona_tags,
)
from .services.summarizer_service import generate_reply, summarize_target


def _is_admin(event: MessageEvent) -> bool:
    from .config import get_plugin_config

    config = get_plugin_config()
    if not config.admin_ids:
        return True
    return str(event.user_id) in config.admin_ids


def _parse_args(args: Message) -> list[str]:
    text = args.extract_plain_text().strip()
    return text.split() if text else []


def _parse_text_arg(args: Message) -> str:
    return args.extract_plain_text().strip()


def _render_manual_profile(profile: dict) -> str:
    manual = normalize_manual_profile(profile)
    lines = [
        f"公司/职级/职位: {' '.join(item for item in [manual['company'], manual['level'], manual['role']] if item) or '未填写'}",
        f"性别: {manual['gender'] or '未填写'}",
        f"MBTI/星座: {' '.join(item for item in [manual['mbti'], manual['zodiac']] if item) or '未填写'}",
        f"个性标签: {'、'.join(manual['personality_tags']) or '无'}",
        f"企业文化标签: {'、'.join(manual['culture_tags']) or '无'}",
        f"主观印象: {manual['subjective_impression'] or '无'}",
    ]
    return "\n".join(lines)


def _render_profile_summary(profile: dict) -> str:
    normalized = normalize_v2_profile(profile)
    layers = normalized["layers"]
    conflicts = normalized.get("pending_conflicts", [])
    lines = [
        f"核心规则: {len(layers['core_rules'])} 条",
        f"身份: {layers['identity'].get('summary') or '无'}",
        f"表达层: 口头禅 {len(layers['expression']['catchphrases'])} 条，回应模式 {len(layers['expression']['response_patterns'])} 条",
        f"决策层: 优先级 {len(layers['decisions']['priorities'])} 条，推进触发 {len(layers['decisions']['push_triggers'])} 条",
        f"人际层: 场景 {len(layers['interpersonal']['typical_scenarios'])} 条",
        f"边界层: 不喜欢 {len(layers['boundaries']['dislikes'])} 条，红线 {len(layers['boundaries']['red_lines'])} 条",
        f"待确认冲突: {len(conflicts)} 条",
    ]
    if conflicts:
        lines.append(
            "冲突预览: "
            + " | ".join(
                f"{item['field']} 手工={item['manual']} / 推断={item['inferred']}"
                for item in conflicts[:3]
            )
        )
    return "\n".join(lines)


async def _require_admin(event: MessageEvent, matcher) -> bool:
    if _is_admin(event):
        return True
    await matcher.finish("仅管理员可用。")
    return False


async def _resolve_target_or_finish(target_hint: str | None, matcher):
    target = await resolve_target(target_hint)
    if target is not None:
        return target
    if target_hint:
        await matcher.finish("没有找到这个目标。")
    await matcher.finish("当前无法确定目标，请传入 QQ 号，或者先只保留一个启用中的目标。")
    return None


persona_help = on_command("人设帮助", aliases={"persona帮助"}, priority=10, block=True)
persona_bind_cmd = on_command("人设绑定", aliases={"persona_bind"}, priority=10, block=True)
persona_enable_cmd = on_command("人设开启", aliases={"persona_on"}, priority=10, block=True)
persona_disable_cmd = on_command("人设关闭", aliases={"persona_off"}, priority=10, block=True)
persona_keywords_cmd = on_command("人设关键词", aliases={"persona_keywords"}, priority=10, block=True)
persona_show_keywords_cmd = on_command("人设看关键词", aliases={"persona_show_keywords"}, priority=10, block=True)
persona_status_cmd = on_command("人设状态", aliases={"persona_status"}, priority=10, block=True)
persona_summary_cmd = on_command("人设总结", aliases={"persona_summary"}, priority=10, block=True)
persona_manual_info_cmd = on_command("人设资料", aliases={"persona_manual_info"}, priority=10, block=True)
persona_manual_tags_cmd = on_command("人设标签", aliases={"persona_manual_tags"}, priority=10, block=True)
persona_show_manual_cmd = on_command("人设看资料", aliases={"persona_show_manual"}, priority=10, block=True)
persona_correct_cmd = on_command("人设纠正", aliases={"persona_correct"}, priority=10, block=True)
persona_show_profile_cmd = on_command("人设看画像", aliases={"persona_show_profile"}, priority=10, block=True)
persona_cooldown_cmd = on_command("模仿冷却", aliases={"persona_cooldown"}, priority=10, block=True)
persona_speak_cmd = on_command("学他说话", aliases={"persona_speak"}, priority=10, block=True)


@persona_help.handle()
async def handle_persona_help() -> None:
    help_text = (
        "人设插件指令:\n"
        "人设绑定 <QQ号> [备注名]\n"
        "人设开启 <QQ号>\n"
        "人设关闭 <QQ号>\n"
        "人设关键词 <QQ号> <关键词1> [关键词2] ...\n"
        "人设看关键词 [QQ号]\n"
        "人设资料 <QQ号> <一句话基本信息>\n"
        "人设标签 <QQ号> <一句话性格描述>\n"
        "人设看资料 [QQ号]\n"
        "人设纠正 <QQ号> <自然语言纠正>\n"
        "人设看画像 [QQ号]\n"
        "人设状态\n"
        "人设总结 [QQ号]\n"
        "模仿冷却 [秒数] — 查看/设置自动回复冷却\n"
        "学他说话 [QQ号] <想表达的话>"
    )
    await persona_help.finish(help_text)


@persona_bind_cmd.handle()
async def handle_persona_bind(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_bind_cmd):
        return

    parts = _parse_args(args)
    if not parts:
        await persona_bind_cmd.finish("用法: 人设绑定 <QQ号> [备注名]")

    target_user_id = parts[0]
    target_name = " ".join(parts[1:]) if len(parts) > 1 else None
    target = await bind_target(str(event.user_id), target_user_id, target_name)
    invalidate_target_cache()
    await persona_bind_cmd.finish(
        f"已绑定目标 {target.target_user_id}"
        + (f" ({target.target_name})" if target.target_name else "")
        + f"，已自动开启采集和自动回复，总结阈值 {target.summary_batch_size} 条。"
    )


@persona_enable_cmd.handle()
async def handle_persona_enable(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_enable_cmd):
        return

    parts = _parse_args(args)
    if not parts:
        await persona_enable_cmd.finish("用法: 人设开启 <QQ号>")

    target = await set_target_enabled(parts[0], True)
    if target is None:
        await persona_enable_cmd.finish("没有找到这个目标。")
    invalidate_target_cache()
    await persona_enable_cmd.finish(f"已开启 {target.target_user_id} 的采集和自动回复。")


@persona_disable_cmd.handle()
async def handle_persona_disable(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_disable_cmd):
        return

    parts = _parse_args(args)
    if not parts:
        await persona_disable_cmd.finish("用法: 人设关闭 <QQ号>")

    target = await set_target_enabled(parts[0], False)
    if target is None:
        await persona_disable_cmd.finish("没有找到这个目标。")
    invalidate_target_cache()
    await persona_disable_cmd.finish(f"已关闭 {target.target_user_id} 的采集和自动回复。")


@persona_keywords_cmd.handle()
async def handle_persona_keywords(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_keywords_cmd):
        return

    parts = _parse_args(args)
    if len(parts) < 2:
        await persona_keywords_cmd.finish("用法: 人设关键词 <QQ号> <关键词1> [关键词2] ...")

    target_user_id = parts[0]
    keywords = parts[1:]
    target = await set_trigger_keywords(target_user_id, keywords)
    if target is None:
        await persona_keywords_cmd.finish("没有找到这个目标。")
    invalidate_target_cache()

    effective_keywords = get_effective_trigger_keywords(target)
    await persona_keywords_cmd.finish(
        f"{target.target_user_id} 的触发关键词已更新: "
        + ("、".join(effective_keywords) if effective_keywords else "无")
    )


@persona_show_keywords_cmd.handle()
async def handle_persona_show_keywords(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_show_keywords_cmd):
        return

    parts = _parse_args(args)
    target_hint = parts[0] if parts else None
    target = await _resolve_target_or_finish(target_hint, persona_show_keywords_cmd)
    if target is None:
        return

    effective_keywords = get_effective_trigger_keywords(target)
    await persona_show_keywords_cmd.finish(
        f"{target.target_user_id} 的触发关键词: " + ("、".join(effective_keywords) if effective_keywords else "无")
    )


@persona_manual_info_cmd.handle()
async def handle_persona_manual_info(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_manual_info_cmd):
        return

    text = _parse_text_arg(args)
    if not text:
        await persona_manual_info_cmd.finish("用法: 人设资料 <QQ号> <一句话基本信息>")

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await persona_manual_info_cmd.finish("用法: 人设资料 <QQ号> <一句话基本信息>")

    target = await update_manual_basic_info(parts[0], parts[1])
    if target is None:
        await persona_manual_info_cmd.finish("没有找到这个目标。")
    await persona_manual_info_cmd.finish(
        f"{target.target_user_id} 的手工资料已更新:\n{_render_manual_profile(target.manual_profile_json)}"
    )


@persona_manual_tags_cmd.handle()
async def handle_persona_manual_tags(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_manual_tags_cmd):
        return

    text = _parse_text_arg(args)
    if not text:
        await persona_manual_tags_cmd.finish("用法: 人设标签 <QQ号> <一句话性格描述>")

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await persona_manual_tags_cmd.finish("用法: 人设标签 <QQ号> <一句话性格描述>")

    target = await update_manual_persona_tags(parts[0], parts[1])
    if target is None:
        await persona_manual_tags_cmd.finish("没有找到这个目标。")
    await persona_manual_tags_cmd.finish(
        f"{target.target_user_id} 的手工标签已更新:\n{_render_manual_profile(target.manual_profile_json)}"
    )


@persona_show_manual_cmd.handle()
async def handle_persona_show_manual(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_show_manual_cmd):
        return

    parts = _parse_args(args)
    target_hint = parts[0] if parts else None
    target = await _resolve_target_or_finish(target_hint, persona_show_manual_cmd)
    if target is None:
        return

    manual_profile = await get_manual_profile(target.target_user_id)
    await persona_show_manual_cmd.finish(
        f"{target.target_user_id} 的手工资料:\n{_render_manual_profile(manual_profile)}"
    )


@persona_correct_cmd.handle()
async def handle_persona_correct(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_correct_cmd):
        return

    text = _parse_text_arg(args)
    if not text:
        await persona_correct_cmd.finish("用法: 人设纠正 <QQ号> <自然语言纠正>")

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await persona_correct_cmd.finish("用法: 人设纠正 <QQ号> <自然语言纠正>")

    record, parsed = await add_correction(parts[0], parts[1])
    if record is None:
        await persona_correct_cmd.finish("没有找到这个目标。")

    await persona_correct_cmd.finish(
        f"已写入纠正规则:\n场景: {parsed['scene']}\n不像本人: {parsed['wrong']}\n更像本人: {parsed['correct']}"
    )


@persona_show_profile_cmd.handle()
async def handle_persona_show_profile(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_show_profile_cmd):
        return

    parts = _parse_args(args)
    target_hint = parts[0] if parts else None
    target = await _resolve_target_or_finish(target_hint, persona_show_profile_cmd)
    if target is None:
        return

    state = await refresh_profile_state(target.target_user_id)
    if state is None or not state.current_profile_json:
        await persona_show_profile_cmd.finish("这个目标还没有画像，请先执行一次人设总结。")

    corrections = await list_correction_dicts(target.target_user_id)
    correction_line = "、".join(f"{item['scene']} -> {item['correct']}" for item in corrections[:3]) or "无"
    await persona_show_profile_cmd.finish(
        f"{target.target_user_id} 的 v2 画像摘要:\n"
        f"{_render_profile_summary(state.current_profile_json)}\n"
        f"近期纠偏: {correction_line}"
    )


@persona_status_cmd.handle()
async def handle_persona_status(event: MessageEvent) -> None:
    if not await _require_admin(event, persona_status_cmd):
        return

    targets = await list_targets()
    if not targets:
        await persona_status_cmd.finish("当前还没有绑定任何目标。")

    lines = []
    for target in targets:
        message_count = await PersonaMessage.filter(target_user_id=target.target_user_id).count()
        face_assets = await PersonaAsset.filter(
            target_user_id=target.target_user_id,
            asset_type="face",
        ).order_by("-used_count").limit(3)
        face_counter = Counter({asset.face_id: asset.used_count for asset in face_assets if asset.face_id})
        top_faces = ", ".join(face_counter.keys()) if face_counter else "无"
        state = await get_profile_state(target.target_user_id)
        conflicts = 0
        if state and state.current_profile_json:
            conflicts = len(normalize_v2_profile(state.current_profile_json).get("pending_conflicts", []))
        manual_profile = normalize_manual_profile(target.manual_profile_json)
        tag_preview = "、".join((manual_profile["personality_tags"] + manual_profile["culture_tags"])[:3]) or "无"
        lines.append(
            f"{target.target_user_id}"
            f"{f' ({target.target_name})' if target.target_name else ''} | "
            f"{'启用' if target.enabled else '关闭'} | "
            f"消息 {message_count} | "
            f"已总结到 {target.last_summarized_message_id} | "
            f"常用QQ表情 {top_faces} | "
            f"关键词 {'、'.join(get_effective_trigger_keywords(target)[:5]) or '无'} | "
            f"手工标签 {tag_preview} | "
            f"冲突 {conflicts}"
        )

    await persona_status_cmd.finish("\n".join(lines))


@persona_summary_cmd.handle()
async def handle_persona_summary(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_summary_cmd):
        return

    parts = _parse_args(args)
    target_hint = parts[0] if parts else None
    target = await _resolve_target_or_finish(target_hint, persona_summary_cmd)
    if target is None:
        return

    success, detail = await summarize_target(target, force=True)
    if not success:
        await persona_summary_cmd.finish(detail)
    await persona_summary_cmd.finish(detail)


@persona_cooldown_cmd.handle()
async def handle_persona_cooldown(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_cooldown_cmd):
        return

    parts = _parse_args(args)
    if not parts:
        current = get_auto_reply_cooldown()
        await persona_cooldown_cmd.finish(f"当前模仿冷却时间: {current} 秒")

    try:
        seconds = int(parts[0])
    except ValueError:
        await persona_cooldown_cmd.finish("请输入一个整数秒数，例如: 模仿冷却 20")
        return

    set_auto_reply_cooldown(seconds)
    await persona_cooldown_cmd.finish(f"模仿冷却时间已设置为 {get_auto_reply_cooldown()} 秒")


@persona_speak_cmd.handle()
async def handle_persona_speak(event: MessageEvent, args: Message = CommandArg()) -> None:
    if not await _require_admin(event, persona_speak_cmd):
        return

    parts = _parse_args(args)
    if not parts:
        await persona_speak_cmd.finish("用法: 学他说话 [QQ号] <想表达的话>")

    target_hint = None
    intent_text = ""
    if len(parts) >= 2 and parts[0].isdigit():
        target_hint = parts[0]
        intent_text = " ".join(parts[1:]).strip()
    else:
        intent_text = " ".join(parts).strip()

    if not intent_text:
        await persona_speak_cmd.finish("请补充你想表达的内容。")

    target = await _resolve_target_or_finish(target_hint, persona_speak_cmd)
    if target is None:
        return

    try:
        recent_chat_messages: list[dict] = []
        trigger_reason = {
            "source": "manual_command",
            "trigger_user_id": str(event.user_id),
            "trigger_user_name": event.sender.card or event.sender.nickname or str(event.user_id),
        }
        if isinstance(event, GroupMessageEvent):
            recent_chat_messages = get_recent_group_context(
                group_id=event.group_id,
                target_user_id=target.target_user_id,
                target_aliases=get_effective_trigger_keywords(target),
                exclude_message_id=str(event.message_id),
            )
            trigger_reason["group_id"] = str(event.group_id)

        result = await generate_reply(
            target,
            intent_text,
            recent_chat_messages=recent_chat_messages,
            trigger_reason=trigger_reason,
        )
    except Exception as exc:
        await persona_speak_cmd.finish(str(exc))
        return

    message = Message(result["reply"])
    face_id = result.get("face_id", "")
    if face_id.isdigit():
        message += MessageSegment.face(int(face_id))
    await persona_speak_cmd.finish(message)
