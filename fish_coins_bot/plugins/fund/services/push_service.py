"""每日基金速览推送编排：拉列表 → 逐只取 review → 渲染简洁长图 → 发群。

失败（取不到列表 / 渲染失败 / 整体异常）时私聊管理员（复用 ADMIN_ID）。
单只基金、单个群的失败都被隔离，不影响其余。
详细点评图的取数（collect_detail_items）也放在这里，供「基金走势」指令复用。
"""
from nonebot import get_bot
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.log import logger

from fish_coins_bot.database.bilibili.dynamics.models import DynamicsHistory

from ..config import get_plugin_config
from .ai_service import review_text
from .api_service import get_fund_list, get_review, get_trend
from .render_service import render_summary

# 复用通用去重表 dynamics_history：platform=fund, uid=基金代码, id_str=净值日期(asOf)。
# 同一只基金的同一净值日期只推一次——非交易日 / QDII 滞后导致净值日期不前进时，
# 就不会连续两天重复播报同一份旧净值。
_DEDUP_PLATFORM = "fund"


async def _notify_admins(bot, text: str) -> None:
    config = get_plugin_config()
    if not config.admin_ids:
        return
    for admin_id in config.admin_ids:
        try:
            await bot.send_private_msg(user_id=int(admin_id), message=f"⚠️ 基金推送：{text}")
        except Exception as exc:
            logger.error(f"[fund] 通知管理员 {admin_id} 失败: {exc}")


async def collect_detail_items(codes: list[str], config) -> list[dict]:
    """对给定基金代码逐只取 review + trend + AI 点评，返回 [{review, trend, ai_text}]。

    单只失败跳过不报错，供「基金走势」指令配合 render_report 使用。
    """
    items: list[dict] = []
    for code in codes:
        review = await get_review(code)
        if not review:
            logger.warning(f"[fund] {code} 点评数据为空，跳过该基金。")
            continue
        trend = await get_trend(code, config.trend_days)
        ai_text = await review_text(review) if config.ai_enabled else ""
        items.append({"review": review, "trend": trend, "ai_text": ai_text})
    return items


async def _collect_summary_reviews() -> list[dict]:
    """速览图数据流：/list 全部监控基金 → 逐只 /review（不取走势、不调 AI）。"""
    funds = await get_fund_list()
    if not funds:
        raise RuntimeError("未取到任何监控基金（/list 为空或请求失败）")

    reviews: list[dict] = []
    for fund in funds:
        code = str(fund.get("fundCode") or "").strip()
        if not code or fund.get("enabled") == 0:
            continue
        review = await get_review(code)
        if not review:
            logger.warning(f"[fund] {code} 点评数据为空，跳过该基金。")
            continue
        reviews.append(review)
    return reviews


def _review_dedup_key(review: dict) -> tuple[str, str] | None:
    """取去重键 (基金代码, 净值日期 asOf)。任一缺失返回 None（无法判重）。"""
    code = str(review.get("fundCode") or "").strip()
    as_of = str(review.get("asOf") or "").strip()
    if not code or not as_of:
        return None
    return code, as_of


async def _filter_unpushed(reviews: list[dict]) -> list[dict]:
    """只保留「该基金的该净值日期」还没推送过的，即含新数据的基金。

    asOf 缺失的基金无法判重（多为取数异常），跳过不推，避免每天重复播报脏数据。
    """
    fresh: list[dict] = []
    for review in reviews:
        key = _review_dedup_key(review)
        if key is None:
            logger.warning(
                f"[fund] {review.get('fundCode')} 缺少净值日期 asOf，无法判重，跳过本次。"
            )
            continue
        code, as_of = key
        if await DynamicsHistory.exists(platform=_DEDUP_PLATFORM, uid=code, id_str=as_of):
            continue
        fresh.append(review)
    return fresh


async def _mark_pushed(reviews: list[dict]) -> None:
    """把本次成功推送的 (基金, 净值日期) 落库，下次同一净值日期不再发。"""
    for review in reviews:
        key = _review_dedup_key(review)
        if key is None:
            continue
        code, as_of = key
        try:
            if not await DynamicsHistory.exists(
                platform=_DEDUP_PLATFORM, uid=code, id_str=as_of
            ):
                await DynamicsHistory.create(
                    platform=_DEDUP_PLATFORM, uid=code, id_str=as_of
                )
        except Exception as exc:
            logger.warning(f"[fund] 记录已推送失败 {code} {as_of}: {exc}")


async def run_daily_push() -> None:
    config = get_plugin_config()
    if not config.push_enabled:
        logger.info("[fund] 推送已关闭（FUND_PUSH_ENABLED=false），跳过。")
        return

    try:
        bot = get_bot()
    except Exception as exc:
        logger.error(f"[fund] 无可用 bot 连接，放弃本次推送: {exc}")
        return

    try:
        reviews = await _collect_summary_reviews()
        if not reviews:
            await _notify_admins(bot, "本次没有可推送的基金数据（全部取数失败）。")
            return

        fresh = await _filter_unpushed(reviews)
        if not fresh:
            logger.info(
                f"[fund] 监控的 {len(reviews)} 只基金最新净值日期均已推送过，"
                "本次无新数据，跳过（非交易日属正常）。"
            )
            return

        image_bytes = await render_summary(fresh)
        if not image_bytes:
            await _notify_admins(bot, "渲染基金速览图失败，请检查 playwright / 模板。")
            return

        if not config.group_ids:
            logger.warning("[fund] 未配置 FUND_PUSH_GROUP_IDS，已生成图片但无群可发。")
            await _notify_admins(bot, "已生成基金速览图，但未配置推送群（FUND_PUSH_GROUP_IDS）。")
            return

        message = MessageSegment.image(image_bytes)
        sent = 0
        for group_id in config.group_ids:
            try:
                await bot.send_group_msg(group_id=int(group_id), message=message)
                sent += 1
            except Exception as exc:
                logger.error(f"[fund] 发送群消息失败 group={group_id}: {exc}")

        # 至少发出一个群才落库去重，全失败则保留待下次重试，不会漏推。
        if sent:
            await _mark_pushed(fresh)
        logger.success(
            f"[fund] 基金每日速览推送完成：{len(fresh)} 只新数据基金"
            f"（共监控 {len(reviews)} 只），发往 {sent} 个群。"
        )
    except Exception as exc:
        logger.error(f"[fund] 每日推送任务异常: {exc}")
        await _notify_admins(bot, f"每日推送任务异常：{exc}")
