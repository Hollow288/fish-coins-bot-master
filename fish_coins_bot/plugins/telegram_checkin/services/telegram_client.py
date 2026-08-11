import asyncio
import hashlib

from nonebot.log import logger
from telethon import TelegramClient
from telethon.sessions import StringSession

from ..models import TelegramCheckinBinding


class TelegramSessionInvalidError(RuntimeError):
    """数据库中的 Telegram Session 无效或已失效。"""


_clients: dict[str, TelegramClient] = {}
_client_locks: dict[str, asyncio.Lock] = {}


def _client_key(binding: TelegramCheckinBinding) -> str:
    value = (
        f"{binding.tg_api_id}\0{binding.tg_api_hash}\0{binding.tg_session}"
    ).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _get_lock(key: str) -> asyncio.Lock:
    lock = _client_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _client_locks[key] = lock
    return lock


async def get_telegram_client(
    binding: TelegramCheckinBinding,
) -> tuple[TelegramClient, str]:
    """按凭证复用已连接的 Telethon 客户端。"""

    key = _client_key(binding)
    async with _get_lock(key):
        client = _clients.get(key)
        if client is None:
            session_value = binding.tg_session.strip()
            if not session_value:
                raise TelegramSessionInvalidError("TG Session 为空")
            try:
                session = StringSession(session_value)
            except Exception as exc:
                raise TelegramSessionInvalidError("TG Session 格式无效") from exc

            client = TelegramClient(
                session,
                int(binding.tg_api_id),
                binding.tg_api_hash.strip(),
            )
            _clients[key] = client

        if not client.is_connected():
            await client.connect()
        if not await client.is_user_authorized():
            raise TelegramSessionInvalidError(
                "TG Session 未登录或已失效，请重新生成 Session"
            )
        return client, key


async def disconnect_all_clients() -> None:
    """NoneBot 关闭时断开所有 Telegram 连接。"""

    clients = list(_clients.values())
    _clients.clear()
    for client in clients:
        try:
            if client.is_connected():
                await client.disconnect()
        except Exception as exc:
            logger.warning(f"[telegram_checkin] 断开 Telegram 客户端失败: {exc}")
