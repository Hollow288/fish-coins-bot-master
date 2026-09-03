"""动态推送故障报警 (B 站 / X 共用)。

bilibili/dynamics_push.py 和 x_monitor/dynamics_push.py 都是定时跑的推送任务,
风控 / 登录态失效 / 截图失败时, 旧逻辑只 logger.error 然后静默返回, 没人会及时发现。
本模块负责: 故障分类 + 连续失败计数 + 在连续失败达到阈值时私信管理员 (复用 ADMIN_ID)。

设计要点:
- 精确可判定的失败 (主要是风控) 由调用方 raise PushFailure 带出原因; 模糊失败仍返回 None,
  上层归类为 SCREENSHOT_EMPTY。
- 同一健康项 (scope) 连续失败达到阈值才报一次, 恢复后清零并补发「已恢复」, 避免每分钟刷屏。
- 任何报警自身的异常都只 logger, 绝不抛回推送主循环。

已知局限:
- scope 是「平台×阶段」级, 不细分到具体 UP/账号; 多目标里只有一个持续失败、其余正常时,
  成功会清零计数而可能不报。整体风控 (全部失败) 能正常累计触发。
- bot 自身离线时报警私信也发不出 (属另一层监控)。
- 计数为进程内状态, bot 重启后清零。
"""

import os
from datetime import datetime, timedelta, timezone

from nonebot import get_bot
from nonebot.log import logger

from fish_coins_bot.utils.admin_utils import parse_admin_ids


# 容器系统时区是 UTC, 报警时间戳曾经差 8 小时; 不全局设 TZ (避免影响其他功能),
# 只在报警展示层显式用东八区。北京时间无夏令时, 固定偏移即可。
BEIJING_TZ = timezone(timedelta(hours=8))


# 故障类别 (value 即发给管理员时的中文展示名)
WAF = "风控"
AUTH = "登录态失效"
RATE_LIMIT_COOLDOWN = "限流冷却中 (到期自动恢复)"
CONFIG = "配置缺失"
NETWORK = "网络/HTTP 异常"
SCREENSHOT_EMPTY = "截图失败 (疑似风控或页面改版)"
UNKNOWN = "未知错误"


# scope -> 中文平台名, 用于报警消息
_SCOPE_NAMES = {
    "bili_feed": "B 站动态拉取",
    "bili_shot": "B 站动态截图",
    "x_fetch": "X 推文拉取",
    "x_shot": "X 推文截图",
}


class PushFailure(Exception):
    """推送链路上可精确判定的失败 (主要是风控)。

    由截图函数 / 拉取函数命中明确失败信号时抛出, 上层推送任务 catch 后交给
    report_failure 分类报警。category 取本模块的类别常量, detail 为可读细节。
    """

    def __init__(self, category: str, detail: str = ""):
        super().__init__(detail or category)
        self.category = category
        self.detail = detail


# 进程内健康状态: scope -> {"fails": 连续失败次数, "alerted": 是否已就当前故障报过警}
_state: dict[str, dict] = {}


def _enabled() -> bool:
    raw = os.getenv("DYNAMICS_ALERT_ENABLED", "true").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _threshold() -> int:
    try:
        value = int(os.getenv("DYNAMICS_ALERT_FAIL_THRESHOLD", "3"))
    except ValueError:
        value = 3
    return max(value, 1)


def _scope_name(scope: str) -> str:
    return _SCOPE_NAMES.get(scope, scope)


async def report_failure(scope: str, category: str, detail: str = "") -> None:
    """记录一次失败; 同一 scope 连续失败达到阈值时私信管理员 (只报一次, 直到恢复)。"""
    if not _enabled():
        return
    try:
        st = _state.setdefault(scope, {"fails": 0, "alerted": False})
        st["fails"] += 1

        if st["fails"] >= _threshold() and not st["alerted"]:
            st["alerted"] = True
            now = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
            reason = category if not detail else f"{category} ({detail})"
            text = (
                "⚠️ 动态推送异常\n"
                f"平台: {_scope_name(scope)}\n"
                f"原因: {reason}\n"
                f"已连续失败 {st['fails']} 次\n"
                f"时间: {now}"
            )
            await _notify_admins(text)
    except Exception as e:
        logger.error(f"[动态报警] report_failure 异常 scope={scope}: {e}")


async def report_success(scope: str) -> None:
    """记录一次成功; 若此前已就该 scope 报过警, 补发一条「已恢复」并清零。"""
    if not _enabled():
        return
    try:
        st = _state.get(scope)
        if not st:
            return
        if st.get("alerted"):
            text = (
                f"✅ 动态推送已恢复 — {_scope_name(scope)}"
                f"（此前连续失败 {st['fails']} 次）"
            )
            await _notify_admins(text)
        _state[scope] = {"fails": 0, "alerted": False}
    except Exception as e:
        logger.error(f"[动态报警] report_success 异常 scope={scope}: {e}")


async def _notify_admins(text: str) -> None:
    admin_ids = parse_admin_ids(os.getenv("ADMIN_ID"))
    if not admin_ids:
        logger.warning(f"[动态报警] 未配置 ADMIN_ID, 报警未送达: {text!r}")
        return

    try:
        bot = get_bot()
    except Exception as e:
        logger.error(f"[动态报警] 取 bot 失败 (可能未连接), 报警未送达: {e}")
        return

    for admin_id in admin_ids:
        try:
            await bot.send_private_msg(user_id=int(admin_id), message=text)
        except Exception as e:
            logger.error(f"[动态报警] 发送给管理员 {admin_id} 失败: {e}")
