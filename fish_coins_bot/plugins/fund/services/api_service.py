"""基金服务端接口封装。

对接文档见同插件目录下 README.md。所有接口统一返回 {code, msg, data}，
务必先判 code == 200 再读 data；读接口非 200 / 异常一律返回安全空值，由上层兜底；
写接口（add_fund）需要把服务端 msg 透传给用户，原样返回整个响应体。
"""
import httpx
from nonebot.log import logger

from ..config import get_plugin_config

# 添加基金会同步回补历史净值/画像/排名，可能耗时数秒，超时单独放大（README 易错点 5）
_ADD_FUND_TIMEOUT_SECONDS = 30


async def get_fund_list() -> list[dict]:
    """GET /list —— 监控中的基金列表（Fund[]）。失败返回空列表。"""
    config = get_plugin_config()
    url = f"{config.api_base_url}/list"
    try:
        async with httpx.AsyncClient(timeout=config.request_timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            body = response.json()
        if body.get("code") != 200:
            logger.error(f"[fund] 拉取基金列表非 200: {body.get('code')} {body.get('msg')}")
            return []
        data = body.get("data")
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.error(f"[fund] 拉取基金列表失败: {exc}")
        return []


async def get_review(code: str) -> dict | None:
    """GET /{code}/review —— 点评数据包（喂给 AI）。未监控/失败返回 None。"""
    config = get_plugin_config()
    url = f"{config.api_base_url}/{code}/review"
    try:
        async with httpx.AsyncClient(timeout=config.request_timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            body = response.json()
        if body.get("code") != 200:
            logger.error(f"[fund] 拉取 {code} 点评数据非 200: {body.get('code')} {body.get('msg')}")
            return None
        data = body.get("data")
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.error(f"[fund] 拉取 {code} 点评数据失败: {exc}")
        return None


async def add_fund(code: str) -> dict | None:
    """POST / —— 添加基金监控（写接口，带 X-FUND-TOKEN）。

    返回完整响应体 {code, msg, data}：非 200 也原样返回，由上层把 msg 回给用户
    （400 代码无效 / 401 鉴权失败等）。仅网络异常 / 响应不可解析时返回 None。
    """
    config = get_plugin_config()
    try:
        async with httpx.AsyncClient(timeout=_ADD_FUND_TIMEOUT_SECONDS) as client:
            response = await client.post(
                config.api_base_url,
                json={"code": code},
                headers={"X-FUND-TOKEN": config.api_token},
            )
            body = response.json()
        if not isinstance(body, dict):
            logger.error(f"[fund] 添加基金 {code} 响应格式异常: {body!r}")
            return None
        if body.get("code") != 200:
            logger.warning(f"[fund] 添加基金 {code} 非 200: {body.get('code')} {body.get('msg')}")
        return body
    except Exception as exc:
        logger.error(f"[fund] 添加基金 {code} 请求失败: {exc}")
        return None


async def get_trend(code: str, days: int) -> dict | None:
    """GET /{code}/trend?days=N —— 近 N 天净值走势（画曲线用）。失败返回 None。"""
    config = get_plugin_config()
    url = f"{config.api_base_url}/{code}/trend"
    try:
        async with httpx.AsyncClient(timeout=config.request_timeout_seconds) as client:
            response = await client.get(url, params={"days": days})
            response.raise_for_status()
            body = response.json()
        if body.get("code") != 200:
            logger.error(f"[fund] 拉取 {code} 走势非 200: {body.get('code')} {body.get('msg')}")
            return None
        data = body.get("data")
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.error(f"[fund] 拉取 {code} 走势失败: {exc}")
        return None
