"""调用项目通用文本 AI 接口，把基金点评数据包翻译成人话。

复用 fish_coins_bot.utils.ai_client.call_text_api（读 AI_TEXT_URI / AI_TEXT_APIKEY）。
强约束：只依据给定 JSON，不编造、不计算、缺失字段不提，结尾免责声明。
"""
import json

from nonebot.log import logger

from fish_coins_bot.utils.ai_client import call_text_api

_FALLBACK_TEXT = "AI 点评暂不可用，本卡片仅展示数据指标。"

_SYSTEM = (
    "你是基金点评助手。只依据下面给出的 JSON 指标点评，不得编造或自行计算数据，"
    "缺失(未提供)的指标不要提及。用通俗中文，先用一句话给出整体结论，"
    "再分『收益表现 / 风险 / 同类排名 / 基金经理』简要点评，"
    "全文控制在 150 字以内，不要使用 Markdown 符号。"
    "只客观描述数据，不要给出买入/卖出/加仓/减仓/是否值得投资等任何投资建议或操作倾向，"
    "也不要输出『仅供参考』『不构成投资建议』之类的免责声明（结尾不要加这类话）。"
)


def _strip_nulls(review: dict) -> dict:
    """去掉 None 字段，避免把一堆 null 喂给 AI 干扰点评。"""
    cleaned: dict = {}
    for key, value in review.items():
        if value is None:
            continue
        if isinstance(value, list):
            items = [_strip_nulls(item) if isinstance(item, dict) else item for item in value]
            if items:
                cleaned[key] = items
        elif isinstance(value, dict):
            nested = _strip_nulls(value)
            if nested:
                cleaned[key] = nested
        else:
            cleaned[key] = value
    return cleaned


def build_review_prompt(review: dict) -> str:
    payload = json.dumps(_strip_nulls(review), ensure_ascii=False)
    return f"{_SYSTEM}\n\n基金点评数据如下：\n{payload}"


async def review_text(review: dict) -> str:
    """对单只基金生成点评文字；AI 未配置 / 失败时返回兜底文案，绝不抛异常。"""
    code = review.get("fundCode") or "unknown"
    try:
        result = await call_text_api(
            build_review_prompt(review),
            memory_id=f"fund-review-{code}",
            fresh_memory_each_retry=True,
            log_tag="fund",
        )
    except Exception as exc:
        logger.error(f"[fund] {code} AI 点评调用异常: {exc}")
        return _FALLBACK_TEXT
    if not result:
        logger.warning(f"[fund] {code} AI 点评返回空，使用兜底文案。")
        return _FALLBACK_TEXT
    return result.strip()
