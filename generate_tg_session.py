"""交互式登录 Telegram 个人号并生成可写入数据库的 StringSession。"""

import asyncio
import getpass
import os

from dotenv import load_dotenv
from telethon import TelegramClient, utils
from telethon.sessions import StringSession


load_dotenv()


def _get_proxy() -> tuple[str, str, int] | None:
    """读取生成 Session 时使用的本地代理；设置为 direct 可禁用。"""

    proxy_type = os.getenv("TG_SESSION_PROXY_TYPE", "http").strip().lower()
    if proxy_type in {"", "direct", "none", "off"}:
        return None
    if proxy_type not in {"http", "socks4", "socks5"}:
        raise ValueError(
            "TG_SESSION_PROXY_TYPE 仅支持 http、socks4、socks5 或 direct"
        )

    proxy_host = os.getenv("TG_SESSION_PROXY_HOST", "127.0.0.1").strip()
    if not proxy_host:
        raise ValueError("TG_SESSION_PROXY_HOST 不能为空")

    proxy_port_value = os.getenv("TG_SESSION_PROXY_PORT", "7890").strip()
    try:
        proxy_port = int(proxy_port_value)
    except ValueError as exc:
        raise ValueError("TG_SESSION_PROXY_PORT 必须是数字") from exc
    if not 1 <= proxy_port <= 65535:
        raise ValueError("TG_SESSION_PROXY_PORT 必须在 1~65535 之间")

    return proxy_type, proxy_host, proxy_port


def _read_api_id() -> int:
    while True:
        value = input("Telegram API ID: ").strip()
        try:
            return int(value)
        except ValueError:
            print("API ID 必须是数字，请重新输入。")


def _read_required(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("此项不能为空，请重新输入。")


def _read_password() -> str:
    return getpass.getpass("Telegram 两步验证密码: ")


async def generate_session() -> None:
    print("此工具只用于首次登录并生成 Telethon StringSession。")
    print("验证码和两步验证密码不会保存。\n")

    proxy = _get_proxy()
    if proxy is None:
        print("Telegram 连接方式：直连\n")
    else:
        proxy_type, proxy_host, proxy_port = proxy
        print(
            f"Telegram 连接代理：{proxy_type}://{proxy_host}:{proxy_port}\n"
        )

    api_id = _read_api_id()
    api_hash = _read_required("Telegram API Hash: ")
    phone = _read_required("手机号（国际格式，例如 +8613812345678）: ")

    client = TelegramClient(
        StringSession(),
        api_id,
        api_hash,
        proxy=proxy,
    )
    try:
        await client.start(
            phone=phone,
            code_callback=lambda: input("Telegram 验证码: ").strip(),
            password=_read_password,
        )
        me = await client.get_me()
        session_value = client.session.save()
        if not session_value:
            raise RuntimeError("登录成功但没有生成 StringSession")

        print("\n登录成功。")
        print(f"Telegram 用户: {utils.get_display_name(me)} (ID: {me.id})")
        print("请将下面完整内容写入 telegram_checkin_binding.tg_session：")
        print("\n----- StringSession 开始 -----")
        print(session_value)
        print("----- StringSession 结束 -----")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(generate_session())
    except KeyboardInterrupt:
        print("\n已取消。")
    except Exception as exc:
        print(f"\n登录失败：{exc}")
        raise SystemExit(1) from exc
