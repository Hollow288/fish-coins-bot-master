from collections.abc import Sequence

from ..config import get_plugin_config
from ..models import PersonaProfileState, PersonaTarget


def _normalize_keywords(keywords: list[str] | tuple[str, ...] | None) -> list[str]:
    if not keywords:
        return []

    normalized: list[str] = []
    for keyword in keywords:
        cleaned = str(keyword).strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


async def bind_target(owner_user_id: str, target_user_id: str, target_name: str | None = None) -> PersonaTarget:
    config = get_plugin_config()
    target = await PersonaTarget.get_or_none(target_user_id=target_user_id)
    if target is None:
        initial_keywords = _normalize_keywords([target_name] if target_name else [])
        target = await PersonaTarget.create(
            owner_user_id=owner_user_id,
            target_user_id=target_user_id,
            target_name=target_name,
            enabled=True,
            auto_reply_enabled=True,
            trigger_keywords_json=initial_keywords,
            summary_batch_size=config.summary_batch_size,
        )
    else:
        target.owner_user_id = owner_user_id
        if target_name:
            target.target_name = target_name
            if not target.trigger_keywords_json:
                target.trigger_keywords_json = _normalize_keywords([target_name])
        target.enabled = True
        if target.summary_batch_size <= 0:
            target.summary_batch_size = config.summary_batch_size
        await target.save()
    return target


async def get_target(target_user_id: str) -> PersonaTarget | None:
    return await PersonaTarget.get_or_none(target_user_id=target_user_id)


async def list_targets() -> Sequence[PersonaTarget]:
    return await PersonaTarget.all().order_by("target_user_id")


async def set_target_enabled(target_user_id: str, enabled: bool) -> PersonaTarget | None:
    target = await PersonaTarget.get_or_none(target_user_id=target_user_id)
    if target is None:
        return None
    target.enabled = enabled
    target.auto_reply_enabled = enabled
    await target.save()
    return target


async def resolve_target(target_hint: str | None) -> PersonaTarget | None:
    if target_hint:
        return await get_target(target_hint)

    targets = await PersonaTarget.filter(enabled=True).order_by("-updated_at")
    if len(targets) == 1:
        return targets[0]
    return None


async def get_profile_state(target_user_id: str) -> PersonaProfileState | None:
    return await PersonaProfileState.get_or_none(target_user_id=target_user_id)



async def set_trigger_keywords(target_user_id: str, keywords: list[str]) -> PersonaTarget | None:
    target = await PersonaTarget.get_or_none(target_user_id=target_user_id)
    if target is None:
        return None
    target.trigger_keywords_json = _normalize_keywords(keywords)
    await target.save()
    return target


def get_effective_trigger_keywords(target: PersonaTarget) -> list[str]:
    keywords = _normalize_keywords(target.trigger_keywords_json or [])
    if target.target_name and target.target_name not in keywords:
        keywords.insert(0, target.target_name)
    return keywords
