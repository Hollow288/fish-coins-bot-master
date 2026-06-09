"""每日基金点评推送编排：拉列表 → 逐只取数 + AI 点评 → 渲染长图 → 发群。

失败（取不到列表 / 渲染失败 / 整体异常）时私聊管理员（复用 ADMIN_ID）。
单只基金、单个群的失败都被隔离，不影响其余。
"""
from nonebot import get_bot
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.log import logger

from ..config import get_plugin_config
from .ai_service import review_text
from .api_service import get_fund_list, get_review, get_trend
from .render_service import render_report


async def _notify_admins(bot, text: str) -> None:
    config = get_plugin_config()
    if not config.admin_ids:
        return
    for admin_id in config.admin_ids:
        try:
            await bot.send_private_msg(user_id=int(admin_id), message=f"⚠️ 基金推送：{text}")
        except Exception as exc:
            logger.error(f"[fund] 通知管理员 {admin_id} 失败: {exc}")


async def _collect_items(config) -> list[dict]:
    """拉取每只监控基金的 review + trend + AI 点评，返回可渲染条目列表。"""
    funds = await get_fund_list()
    if not funds:
        raise RuntimeError("未取到任何监控基金（/list 为空或请求失败）")

    items: list[dict] = []
    for fund in funds:
        code = str(fund.get("fundCode") or "").strip()
        if not code or fund.get("enabled") == 0:
            continue
        review = await get_review(code)
        if not review:
            logger.warning(f"[fund] {code} 点评数据为空，跳过该基金。")
            continue
        trend = await get_trend(code, config.trend_days)
        ai_text = await review_text(review) if config.ai_enabled else ""
        items.append({"review": review, "trend": trend, "ai_text": ai_text})
    return items


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
        items = await _collect_items(config)
        if not items:
            await _notify_admins(bot, "本次没有可推送的基金数据（全部取数失败）。")
            return

        image_bytes = await render_report(items)
        if not image_bytes:
            await _notify_admins(bot, "渲染基金长图失败，请检查 playwright / 模板。")
            return

        if not config.group_ids:
            logger.warning("[fund] 未配置 FUND_PUSH_GROUP_IDS，已生成图片但无群可发。")
            await _notify_admins(bot, "已生成基金长图，但未配置推送群（FUND_PUSH_GROUP_IDS）。")
            return

        message = MessageSegment.image(image_bytes)
        sent = 0
        for group_id in config.group_ids:
            try:
                await bot.send_group_msg(group_id=int(group_id), message=message)
                sent += 1
            except Exception as exc:
                logger.error(f"[fund] 发送群消息失败 group={group_id}: {exc}")
        logger.success(f"[fund] 基金每日点评推送完成：{len(items)} 只基金，发往 {sent} 个群。")
    except Exception as exc:
        logger.error(f"[fund] 每日推送任务异常: {exc}")
        await _notify_admins(bot, f"每日推送任务异常：{exc}")
