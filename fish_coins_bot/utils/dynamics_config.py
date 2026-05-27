import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nonebot.log import logger


CONFIG_PATH = Path(
    os.getenv(
        "DYNAMICS_LIST_PATH",
        Path(__file__).resolve().parents[1] / "plugins" / "bilibili" / "dynamics_list.json",
    )
)


@dataclass(frozen=True)
class DynamicTarget:
    platform: str
    account: str
    group_ids: list[str]
    options: dict[str, Any] = field(default_factory=dict)


def load_dynamics_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        logger.warning(f"[动态配置] 找不到配置文件: {CONFIG_PATH}")
        return {}

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"[动态配置] 读取失败 path={CONFIG_PATH}: {e}")
        return {}

    if not isinstance(data, dict):
        logger.error(f"[动态配置] 顶层必须是 JSON object: {CONFIG_PATH}")
        return {}

    # 兼容旧格式: {"B站UID": ["群号1", "群号2"]}
    if "bilibili" not in data and "x" not in data:
        return {"bilibili": data}

    return data


def load_platform_targets(platform: str) -> dict[str, DynamicTarget]:
    raw = load_dynamics_config().get(platform, {})
    if not isinstance(raw, dict):
        logger.error(f"[动态配置] {platform} 配置必须是 JSON object")
        return {}

    targets: dict[str, DynamicTarget] = {}
    for account, value in raw.items():
        target = _parse_target(platform, str(account), value)
        if target is None:
            continue
        targets[target.account] = target
    return targets


def _parse_target(platform: str, account: str, value: Any) -> DynamicTarget | None:
    options: dict[str, Any] = {}
    if isinstance(value, list):
        group_ids = value
    elif isinstance(value, dict):
        group_ids = (
            value.get("groups")
            or value.get("group_ids")
            or value.get("qq_groups")
            or []
        )
        options = {
            k: v
            for k, v in value.items()
            if k not in {"groups", "group_ids", "qq_groups"}
        }
    else:
        logger.warning(f"[动态配置] 跳过无效目标 platform={platform} account={account}")
        return None

    if not isinstance(group_ids, list):
        logger.warning(f"[动态配置] 群列表必须是 list platform={platform} account={account}")
        return None

    normalized_groups = [str(x).strip() for x in group_ids if str(x).strip()]
    if not normalized_groups:
        logger.warning(f"[动态配置] 目标未配置群 platform={platform} account={account}")
        return None

    normalized_account = account.strip()
    if platform == "x":
        normalized_account = normalized_account.lstrip("@")

    if not normalized_account:
        logger.warning(f"[动态配置] 目标账号为空 platform={platform}")
        return None

    return DynamicTarget(
        platform=platform,
        account=normalized_account,
        group_ids=normalized_groups,
        options=options,
    )


def option_bool(options: dict[str, Any], key: str, default: bool) -> bool:
    value = options.get(key, default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def option_int(options: dict[str, Any], key: str, default: int, minimum: int | None = None) -> int:
    value = options.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(parsed, minimum)
    return parsed
