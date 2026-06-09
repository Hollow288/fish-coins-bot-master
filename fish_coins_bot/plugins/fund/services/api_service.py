"""基金服务端只读接口封装。

对接文档见同插件目录下 README.md。所有接口统一返回 {code, msg, data}，
务必先判 code == 200 再读 data；非 200 / 异常一律返回安全空值，由上层兜底。
"""
import httpx
from nonebot.log import logger

from ..config import get_plugin_config


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
