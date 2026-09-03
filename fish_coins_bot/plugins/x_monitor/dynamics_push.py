import os
import re
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from nonebot import get_bot, require
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.log import logger

from fish_coins_bot.database.bilibili.dynamics.models import DynamicsHistory
from fish_coins_bot.utils.dynamics_config import (
    DynamicTarget,
    load_platform_targets,
    option_bool,
    option_int,
)
from fish_coins_bot.utils.image_utils import screenshot_x_tweet_by_id
from fish_coins_bot.utils.push_alert import (
    AUTH,
    BEIJING_TZ,
    CONFIG,
    RATE_LIMIT_COOLDOWN,
    SCREENSHOT_EMPTY,
    UNKNOWN,
    WAF,
    PushFailure,
    report_failure,
    report_success,
)

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

try:
    from twscrape import API
except ImportError as e:
    API = None
    TWSCRAPE_IMPORT_ERROR = e
else:
    TWSCRAPE_IMPORT_ERROR = None


PLATFORM = "x"
DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_FETCH_LIMIT = 5
DEFAULT_MAX_AGE_SECONDS = 12 * 60

_api: Any | None = None
_account_synced = False
_user_cache: dict[str, tuple[int, str]] = {}


async def _classify_x_failure(e: Exception) -> tuple[str, str]:
    """把 twscrape 抓取异常分类为 (类别, 细节), 供报警标注。

    NoAccountError 不能直接当登录失效: 单账号被限流锁 15 分钟时池子同样为空,
    需进一步查账号池区分「冷却中(自愈)」和「真被标记失效(需换 Cookie)」。
    """
    msg = str(e).lower()
    name = type(e).__name__.lower()
    if "noaccount" in name or "no account" in msg or "no accounts" in msg:
        return await _classify_no_account(e)
    if "rate" in msg or "429" in msg or "too many" in msg:
        return WAF, str(e)
    return UNKNOWN, str(e)


async def _classify_no_account(e: Exception) -> tuple[str, str]:
    """NoAccountError 细分: 限流冷却 / 登录失效 / 账号池为空。"""
    if _api is None:
        return AUTH, str(e)

    try:
        accounts = await _api.pool.get_all()
    except Exception as pool_err:  # 查询失败就退回原始消息, 不让报警链路再抛
        logger.warning(f"[X 推送] 查询账号池失败: {pool_err}")
        return AUTH, str(e)

    if not accounts:
        return CONFIG, "twscrape 账号池为空, 请检查 X_AUTH_TOKEN / X_CT0"

    active = [a for a in accounts if getattr(a, "active", False)]
    if not active:
        # 全部被 twscrape 标记 inactive → 真·登录失效/封号, 不会自愈
        err = next((a.error_msg for a in accounts if getattr(a, "error_msg", None)), "")
        detail = "账号已被标记失效, 需重新获取 Cookie 并重启 bot"
        if err:
            detail += f"; twscrape: {err}"
        return AUTH, detail

    # 有 active 账号却拿不到 → 被 queue 级限流锁住, 到期自动恢复
    match = re.search(r"queue\s+(\S+)", str(e))
    queue = match.group(1) if match else None
    unlock_times = []
    for account in active:
        locks = getattr(account, "locks", None) or {}
        lock_until = locks.get(queue) if queue else None
        if lock_until is None and locks:
            lock_until = max(locks.values())
        if isinstance(lock_until, datetime):
            unlock_times.append(lock_until)

    if unlock_times:
        unlock_at = min(unlock_times).astimezone(BEIJING_TZ)
        minutes = max(0, int((min(unlock_times) - datetime.now(timezone.utc)).total_seconds() // 60))
        detail = f"预计 {unlock_at.strftime('%H:%M:%S')} (约 {minutes} 分钟后) 解锁, 无需处理"
    else:
        detail = "账号被临时锁定, 通常 15 分钟内自动解锁, 无需处理"
    return RATE_LIMIT_COOLDOWN, detail


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int, minimum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    if minimum is not None:
        value = max(value, minimum)
    return value


def _tws_db_file() -> str:
    raw = os.getenv("X_TWSCRAPE_DB", "").strip()
    if raw:
        return raw

    tmp_dir = os.getenv("TMPDIR") or os.getenv("TEMP") or "/tmp"
    return str(Path(tmp_dir) / "x_twscrape_accounts.db")


def _env_cookie_value(env_name: str, cookie_name: str) -> str:
    value = os.getenv(env_name, "").strip()
    prefix = f"{cookie_name}="
    if value.startswith(prefix):
        value = value[len(prefix):].strip()
    return value


def _load_x_cookie_text() -> str:
    auth_token = _env_cookie_value("X_AUTH_TOKEN", "auth_token")
    ct0 = _env_cookie_value("X_CT0", "ct0")
    twid = _env_cookie_value("X_TWID", "twid")

    if not auth_token or not ct0:
        return ""

    parts = [("auth_token", auth_token), ("ct0", ct0), ("twid", twid)]
    return "; ".join(f"{name}={value}" for name, value in parts if value)


async def _get_api():
    global _api
    if API is None:
        raise RuntimeError(f"未安装 twscrape: {TWSCRAPE_IMPORT_ERROR}")

    if _api is None:
        _api = API(_tws_db_file(), raise_when_no_account=True)

    await _ensure_tws_account(_api)
    return _api


async def _ensure_tws_account(api) -> None:
    global _account_synced
    if _account_synced:
        return

    cookies = _load_x_cookie_text()
    account_name = "x_cookie"
    if cookies:
        existing = await api.pool.get_account(account_name)
        if existing is not None:
            await api.pool.delete_accounts(account_name)

        await api.pool.add_account_cookies(account_name, cookies)
        _account_synced = True
        logger.info(f"[X 推送] 已导入 twscrape Cookie 账号: {account_name}")
        return

    accounts = await api.pool.get_all()
    has_active = any(getattr(account, "active", False) for account in accounts)
    if has_active:
        _account_synced = True
        return

    logger.warning("[X 推送] 未配置 X_AUTH_TOKEN / X_CT0，且 twscrape 无可用账号")


@scheduler.scheduled_job(
    "interval",
    seconds=_env_int("X_DYNAMICS_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS, minimum=30),
    id="x_dynamics_push",
)
async def x_dynamics_push():
    targets = load_platform_targets(PLATFORM)
    if not targets:
        return

    try:
        api = await _get_api()
    except Exception as e:
        logger.error(f"[X 推送] 初始化 twscrape 失败: {e}")
        if "未安装 twscrape" in str(e):
            category, detail = CONFIG, str(e)
        else:
            category, detail = await _classify_x_failure(e)
        await report_failure("x_fetch", category, detail)
        return

    bot = get_bot()
    for target in targets.values():
        try:
            await _handle_one_target(api, bot, target)
        except Exception as e:
            logger.error(f"[X 推送] 处理账号失败 account={target.account}: {e}")


async def _handle_one_target(api, bot, target: DynamicTarget) -> None:
    try:
        user_id, username = await _resolve_target_user(api, target)
    except Exception as e:
        logger.error(f"[X 推送] 解析用户失败 account={target.account}: {e}")
        category, detail = await _classify_x_failure(e)
        await report_failure("x_fetch", category, detail)
        return
    if not user_id:
        return

    include_replies = option_bool(
        target.options,
        "include_replies",
        _env_bool("X_INCLUDE_REPLIES", False),
    )
    include_retweets = option_bool(
        target.options,
        "include_retweets",
        _env_bool("X_INCLUDE_RETWEETS", False),
    )
    limit = option_int(
        target.options,
        "limit",
        _env_int("X_FETCH_LIMIT", DEFAULT_FETCH_LIMIT, minimum=1),
        minimum=1,
    )

    try:
        tweets = await _fetch_tweets(api, user_id, include_replies, limit)
    except Exception as e:
        logger.error(f"[X 推送] 拉取推文失败 account={target.account}: {e}")
        category, detail = await _classify_x_failure(e)
        await report_failure("x_fetch", category, detail)
        return

    await report_success("x_fetch")

    if not tweets:
        return

    tweets.sort(key=lambda tweet: _tweet_ts(tweet))
    for tweet in tweets:
        if not include_replies and getattr(tweet, "inReplyToTweetId", None):
            continue
        if not include_retweets and getattr(tweet, "retweetedTweet", None) is not None:
            continue
        await _handle_one_tweet(bot, target, str(user_id), username, tweet)


async def _resolve_target_user(api, target: DynamicTarget) -> tuple[int | None, str]:
    username = str(target.options.get("username") or target.account).lstrip("@")
    user_id_raw = target.options.get("user_id")
    if user_id_raw:
        try:
            return int(user_id_raw), username
        except (TypeError, ValueError):
            logger.warning(f"[X 推送] user_id 配置无效 account={target.account}: {user_id_raw}")

    cache_key = username.lower()
    cached = _user_cache.get(cache_key)
    if cached is not None:
        return cached

    user = await api.user_by_login(username)
    if user is None:
        logger.warning(f"[X 推送] 找不到用户 @{username}")
        return None, username

    resolved = (int(user.id), str(user.username))
    _user_cache[cache_key] = resolved
    return resolved


async def _fetch_tweets(api, user_id: int, include_replies: bool, limit: int) -> list:
    tweets = []
    source = api.user_tweets_and_replies if include_replies else api.user_tweets
    async for tweet in source(user_id, limit=limit):
        tweets.append(tweet)
    return tweets


async def _handle_one_tweet(
    bot,
    target: DynamicTarget,
    user_id: str,
    username: str,
    tweet,
) -> None:
    tweet_id = str(tweet.id)
    if await DynamicsHistory.exists(platform=PLATFORM, uid=user_id, id_str=tweet_id):
        return

    max_age_seconds = option_int(
        target.options,
        "max_age_seconds",
        _env_int("X_DYNAMIC_MAX_AGE_SECONDS", DEFAULT_MAX_AGE_SECONDS, minimum=0),
        minimum=0,
    )
    if max_age_seconds and int(time.time()) - _tweet_ts(tweet) >= max_age_seconds:
        await DynamicsHistory.create(platform=PLATFORM, uid=user_id, id_str=tweet_id)
        return

    shot_failure: tuple[str, str] | None = None
    try:
        image = await screenshot_x_tweet_by_id(username, tweet_id)
    except PushFailure as e:
        logger.error(f"[X 推送] 截图失败 [{e.category}] tweet_id={tweet_id}: {e.detail}")
        image = None
        shot_failure = (e.category, e.detail)

    message = None
    if image is not None:
        await report_success("x_shot")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        message = MessageSegment.image(buffer)
    else:
        if shot_failure is None:
            shot_failure = (SCREENSHOT_EMPTY, f"tweet_id={tweet_id}")
        # 截图失败照常上报 x_shot 健康度, 但仍按 send_text_fallback 尝试用文字把消息发出去
        await report_failure("x_shot", shot_failure[0], shot_failure[1])
        if option_bool(
            target.options,
            "send_text_fallback",
            _env_bool("X_SEND_TEXT_FALLBACK", True),
        ):
            message = _format_tweet_message(username, tweet)
        else:
            logger.warning(f"[X 推送] 截图失败，跳过 tweet_id={tweet_id}")
            return

    for group_id in target.group_ids:
        try:
            await bot.send_group_msg(group_id=int(group_id), message=message)
        except Exception as e:
            logger.error(f"[X 推送] 发送群消息失败 group={group_id} tweet_id={tweet_id}: {e}")

    await DynamicsHistory.create(platform=PLATFORM, uid=user_id, id_str=tweet_id)


def _tweet_ts(tweet) -> int:
    dt = getattr(tweet, "date", None)
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    return 0


def _format_tweet_message(username: str, tweet) -> str:
    tweet_id = str(tweet.id)
    url = getattr(tweet, "url", None) or f"https://x.com/{username}/status/{tweet_id}"
    text = " ".join(str(getattr(tweet, "rawContent", "") or "").split())
    if len(text) > 500:
        text = text[:497] + "..."
    return f"X 新推文 @{username}\n{text}\n{url}"
