from collections import Counter

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent, MessageSegment
from nonebot.params import CommandArg

from .auto_reply import invalidate_target_cache
from .models import PersonaAsset, PersonaMessage
from .services.context_service import get_recent_group_context
from .services.persona_service import (
    bind_target,
    get_effective_trigger_keywords,
    list_targets,
    resolve_target,
    set_target_enabled,
    set_trigger_keywords,
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
        "人设状态\n"
        "人设总结 [QQ号]\n"
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
        lines.append(
            f"{target.target_user_id}"
            f"{f' ({target.target_name})' if target.target_name else ''} | "
            f"{'启用' if target.enabled else '关闭'} | "
            f"消息 {message_count} | "
            f"已总结到 {target.last_summarized_message_id} | "
            f"常用QQ表情 {top_faces} | "
            f"关键词 {'、'.join(get_effective_trigger_keywords(target)[:5]) or '无'}"
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
