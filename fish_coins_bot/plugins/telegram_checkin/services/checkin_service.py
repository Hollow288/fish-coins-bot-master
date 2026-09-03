import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo

from nonebot.log import logger
from telethon.errors import FloodWaitError

from fish_coins_bot.database.bilibili.dynamics.models import DynamicsHistory

from ..config import get_plugin_config
from ..models import TelegramCheckinBinding
from .telegram_client import get_telegram_client

_HISTORY_PLATFORM = "telegram_checkin"
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_binding_locks: dict[int, asyncio.Lock] = {}
_conversation_locks: dict[str, asyncio.Lock] = {}
_sent_in_process: set[tuple[int, str]] = set()


class CheckinStatus(str, Enum):
    SENT = "sent"
    ALREADY_DONE = "already_done"
    FAILED = "failed"


@dataclass(slots=True)
class CheckinResult:
    binding_id: int
    account_name: str
    target_bot: str
    command: str
    status: CheckinStatus
    reply_text: str | None = None
    detail: str | None = None


def _get_lock(container: dict, key) -> asyncio.Lock:
    lock = container.get(key)
    if lock is None:
        lock = asyncio.Lock()
        container[key] = lock
    return lock


def _today_string() -> str:
    return datetime.now(_SHANGHAI_TZ).date().isoformat()


def _display_account_name(binding: TelegramCheckinBinding) -> str:
    return binding.tg_account_name.strip() or f"TG账号#{binding.id}"


def _plain_reply_text(message) -> str:
    text = (getattr(message, "raw_text", None) or "").strip()
    return text or "[收到非文本回复]"


async def _was_sent_today(binding_id: int, today: str) -> bool:
    key = (binding_id, today)
    if key in _sent_in_process:
        return True
    return await DynamicsHistory.exists(
        platform=_HISTORY_PLATFORM,
        uid=str(binding_id),
        id_str=today,
    )


async def _mark_sent(binding_id: int, today: str) -> str | None:
    """发送成功后立即记历史；写库失败时保留进程内去重并返回警告。"""

    key = (binding_id, today)
    _sent_in_process.add(key)
    try:
        if not await DynamicsHistory.exists(
            platform=_HISTORY_PLATFORM,
            uid=str(binding_id),
            id_str=today,
        ):
            await DynamicsHistory.create(
                platform=_HISTORY_PLATFORM,
                uid=str(binding_id),
                id_str=today,
            )
    except Exception as exc:
        logger.error(
            f"[telegram_checkin] 绑定 {binding_id} 已发送但写入签到历史失败: {exc}"
        )
        return "指令已发送，但签到历史写入失败"
    return None


async def checkin(binding: TelegramCheckinBinding) -> CheckinResult:
    """执行单条绑定；消息发送成功即记为当天已签到，回复内容只做展示。"""

    account_name = _display_account_name(binding)
    target_bot = binding.target_bot.strip()
    command = binding.checkin_command or ""
    today = _today_string()
    binding_lock = _get_lock(_binding_locks, binding.id)

    async with binding_lock:
        try:
            if await _was_sent_today(binding.id, today):
                return CheckinResult(
                    binding_id=binding.id,
                    account_name=account_name,
                    target_bot=target_bot,
                    command=command,
                    status=CheckinStatus.ALREADY_DONE,
                    detail="今天已经发送过签到指令，本次未重复发送",
                )
        except Exception as exc:
            logger.error(
                f"[telegram_checkin] 绑定 {binding.id} 查询签到历史失败: {exc}"
            )
            return CheckinResult(
                binding_id=binding.id,
                account_name=account_name,
                target_bot=target_bot,
                command=command,
                status=CheckinStatus.FAILED,
                detail=f"查询签到历史失败：{exc}",
            )

        if not target_bot:
            return CheckinResult(
                binding_id=binding.id,
                account_name=account_name,
                target_bot="[未配置]",
                command=command,
                status=CheckinStatus.FAILED,
                detail="目标机器人为空",
            )
        if not command.strip():
            return CheckinResult(
                binding_id=binding.id,
                account_name=account_name,
                target_bot=target_bot,
                command="[未配置]",
                status=CheckinStatus.FAILED,
                detail="签到指令为空",
            )

        sent = False
        history_warning: str | None = None
        try:
            client, client_key = await get_telegram_client(binding)
            entity = await client.get_entity(target_bot)
            if not getattr(entity, "bot", False):
                raise ValueError(f"目标 {target_bot} 不是 Telegram 机器人")

            conversation_key = f"{client_key}:{getattr(entity, 'id', target_bot)}"
            conversation_lock = _get_lock(_conversation_locks, conversation_key)
            async with conversation_lock:
                config = get_plugin_config()
                async with client.conversation(
                    entity,
                    timeout=config.reply_timeout_seconds,
                ) as conversation:
                    await conversation.send_message(command)
                    sent = True
                    history_warning = await _mark_sent(binding.id, today)

                    try:
                        response = await conversation.get_response()
                        reply_text = _plain_reply_text(response)
                        detail = history_warning
                    except asyncio.TimeoutError:
                        reply_text = None
                        detail = "指令已发送，但等待回复超时"
                        if history_warning:
                            detail = f"{detail}；{history_warning}"
                    except Exception as exc:
                        logger.warning(
                            f"[telegram_checkin] 绑定 {binding.id} 获取机器人回复失败: {exc}"
                        )
                        reply_text = None
                        detail = f"指令已发送，但获取回复失败：{exc}"
                        if history_warning:
                            detail = f"{detail}；{history_warning}"

                    return CheckinResult(
                        binding_id=binding.id,
                        account_name=account_name,
                        target_bot=target_bot,
                        command=command,
                        status=CheckinStatus.SENT,
                        reply_text=reply_text,
                        detail=detail,
                    )
        except FloodWaitError as exc:
            detail = f"Telegram 触发限流，请等待约 {exc.seconds} 秒后再试"
            if sent:
                if history_warning:
                    detail = f"指令已发送；{detail}；{history_warning}"
                else:
                    detail = f"指令已发送；{detail}"
                return CheckinResult(
                    binding_id=binding.id,
                    account_name=account_name,
                    target_bot=target_bot,
                    command=command,
                    status=CheckinStatus.SENT,
                    detail=detail,
                )
        except Exception as exc:
            if sent:
                logger.warning(
                    f"[telegram_checkin] 绑定 {binding.id} 已发送，后续处理异常: {exc}"
                )
                detail = f"指令已发送，但后续处理异常：{exc}"
                if history_warning:
                    detail = f"{detail}；{history_warning}"
                return CheckinResult(
                    binding_id=binding.id,
                    account_name=account_name,
                    target_bot=target_bot,
                    command=command,
                    status=CheckinStatus.SENT,
                    detail=detail,
                )
            logger.error(f"[telegram_checkin] 绑定 {binding.id} 签到失败: {exc}")
            detail = str(exc) or exc.__class__.__name__

        return CheckinResult(
            binding_id=binding.id,
            account_name=account_name,
            target_bot=target_bot,
            command=command,
            status=CheckinStatus.FAILED,
            detail=detail,
        )


async def checkin_bindings(
    bindings: list[TelegramCheckinBinding],
) -> list[CheckinResult]:
    """顺序执行多条任务，降低同一 Telegram 账号短时间批量发消息的风险。"""

    results: list[CheckinResult] = []
    interval = get_plugin_config().task_interval_seconds
    for index, binding in enumerate(bindings):
        results.append(await checkin(binding))
        if interval and index < len(bindings) - 1:
            await asyncio.sleep(interval)
    return results


def _shorten(text: str, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1]}…"


def _append_multiline(lines: list[str], label: str, value: str) -> None:
    value_lines = value.splitlines() or [""]
    lines.append(f"   {label}：{value_lines[0]}")
    indent = " " * (len(label) * 2 + 4)
    lines.extend(f"{indent}{line}" for line in value_lines[1:])


def format_checkin_results(results: list[CheckinResult], *, automatic: bool) -> str:
    """将同一 QQ 的多条签到结果合并为一条清晰的文本消息。"""

    sent_count = sum(item.status is CheckinStatus.SENT for item in results)
    skipped_count = sum(item.status is CheckinStatus.ALREADY_DONE for item in results)
    failed_count = sum(item.status is CheckinStatus.FAILED for item in results)
    title = "TG 自动签到结果" if automatic else "TG 签到结果"
    lines = [
        f"{title}（共 {len(results)} 项：已发送 {sent_count}，已跳过 {skipped_count}，失败 {failed_count}）"
    ]

    status_labels = {
        CheckinStatus.SENT: "已发送",
        CheckinStatus.ALREADY_DONE: "今日已签到，已跳过",
        CheckinStatus.FAILED: "失败",
    }
    for index, result in enumerate(results, start=1):
        lines.append("")
        lines.append(f"{index}. {result.account_name} → {result.target_bot}")
        lines.append(f"   状态：{status_labels[result.status]}")
        _append_multiline(lines, "指令", _shorten(result.command, 200))
        if result.reply_text:
            _append_multiline(lines, "机器人回复", _shorten(result.reply_text, 1500))
        if result.detail:
            _append_multiline(lines, "说明", _shorten(result.detail, 500))

    return "\n".join(lines)
