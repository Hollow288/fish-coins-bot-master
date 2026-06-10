"""调用项目通用文本 AI 接口，把基金点评数据包翻译成人话。

复用 fish_coins_bot.utils.ai_client.call_text_api（读 AI_TEXT_URI / AI_TEXT_APIKEY）。
强约束：卡片已展示全部数字，AI 只做解读不复述数据；只依据给定 JSON，不编造、
不计算、缺失字段不提；禁止投资建议与免责声明。
"""
import json

from nonebot.log import logger

from fish_coins_bot.utils.ai_client import call_text_api

_FALLBACK_TEXT = "AI 点评暂不可用，本卡片仅展示数据指标。"

_SYSTEM = (
    "你是一位看了多年基金的老手，在给朋友看一张基金数据卡片时随口说两句自己的观感。"
    "卡片上已经完整展示了所有数字（各期收益、回撤、波动、排名、经理信息等），"
    "朋友自己看得到，所以严禁罗列或复述这些数字，不要写『近1月X%、近1年X%』这种话。"
    "你的任务是解读：这些数据放在一起说明了什么？比如风格是稳是猛、"
    "涨幅靠不靠波动换来的、近期和长期表现是否背离、在同类里算什么水平、"
    "经理经验深浅，挑其中最值得一提的两三点说，不必面面俱到。"
    "最多引用一个你认为最关键的数字，其余只做定性描述。"
    "语气像平时聊天，自然口语化，两三句话、80 字以内，不要分点、不要小标题、"
    "不要 Markdown 符号。只依据给出的 JSON 判断，不得编造数据，"
    "缺失的指标当作不存在。不要给出买入/卖出/加仓/减仓/是否值得投资等"
    "任何投资建议或操作倾向，也不要输出『仅供参考』『不构成投资建议』之类的免责声明。"
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
