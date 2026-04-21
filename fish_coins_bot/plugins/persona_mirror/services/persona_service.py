from collections.abc import Sequence

from ..config import get_plugin_config
from ..models import PersonaCorrection, PersonaProfileState, PersonaTarget
from ..profile_schema import (
    merge_manual_profile,
    normalize_correction_record,
    normalize_manual_profile,
    parse_basic_info_text,
    parse_correction_text,
    parse_persona_tags_text,
    rebuild_profile_with_overrides,
)


def _normalize_keywords(keywords: list[str] | tuple[str, ...] | None) -> list[str]:
    if not keywords:
        return []

    normalized: list[str] = []
    for keyword in keywords:
        cleaned = str(keyword).strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


async def _refresh_profile_state(target_user_id: str) -> PersonaProfileState | None:
    target = await PersonaTarget.get_or_none(target_user_id=target_user_id)
    state = await PersonaProfileState.get_or_none(target_user_id=target_user_id)
    if target is None or state is None:
        return state

    corrections = await list_correction_dicts(target_user_id)
    state.current_profile_json = rebuild_profile_with_overrides(
        state.current_profile_json,
        manual_inputs=target.manual_profile_json,
        corrections=corrections,
    )
    await state.save()
    return state


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
            manual_profile_json=normalize_manual_profile({}),
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
        if not target.manual_profile_json:
            target.manual_profile_json = normalize_manual_profile({})
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


async def get_manual_profile(target_user_id: str) -> dict:
    target = await PersonaTarget.get_or_none(target_user_id=target_user_id)
    if target is None:
        return normalize_manual_profile({})
    return normalize_manual_profile(target.manual_profile_json)


async def update_manual_basic_info(target_user_id: str, text: str) -> PersonaTarget | None:
    target = await PersonaTarget.get_or_none(target_user_id=target_user_id)
    if target is None:
        return None
    target.manual_profile_json = parse_basic_info_text(text, target.manual_profile_json)
    await target.save()
    await _refresh_profile_state(target_user_id)
    return target


async def update_manual_persona_tags(target_user_id: str, text: str) -> PersonaTarget | None:
    target = await PersonaTarget.get_or_none(target_user_id=target_user_id)
    if target is None:
        return None
    target.manual_profile_json = parse_persona_tags_text(text, target.manual_profile_json)
    await target.save()
    await _refresh_profile_state(target_user_id)
    return target


async def set_manual_profile(target_user_id: str, payload: dict) -> PersonaTarget | None:
    target = await PersonaTarget.get_or_none(target_user_id=target_user_id)
    if target is None:
        return None
    target.manual_profile_json = merge_manual_profile(target.manual_profile_json, payload)
    await target.save()
    await _refresh_profile_state(target_user_id)
    return target


async def list_corrections(target_user_id: str, limit: int = 20) -> Sequence[PersonaCorrection]:
    return await PersonaCorrection.filter(target_user_id=target_user_id).order_by("-updated_at").limit(limit)


async def list_correction_dicts(target_user_id: str, limit: int = 20) -> list[dict[str, str]]:
    records = await list_corrections(target_user_id, limit=limit)
    return [
        normalize_correction_record(
            {
                "scene": item.scene,
                "wrong": item.wrong,
                "correct": item.correct,
            }
        )
        for item in records
    ]


async def add_correction(target_user_id: str, raw_text: str) -> tuple[PersonaCorrection | None, dict[str, str]]:
    target = await PersonaTarget.get_or_none(target_user_id=target_user_id)
    parsed = parse_correction_text(raw_text)
    if target is None:
        return None, parsed

    existing = await PersonaCorrection.get_or_none(
        target_user_id=target_user_id,
        scene=parsed["scene"],
        correct=parsed["correct"],
    )
    if existing is None:
        record = await PersonaCorrection.create(
            target_user_id=target_user_id,
            scene=parsed["scene"],
            wrong=parsed["wrong"],
            correct=parsed["correct"],
        )
    else:
        existing.wrong = parsed["wrong"]
        await existing.save()
        record = existing

    await _refresh_profile_state(target_user_id)
    return record, parsed


async def refresh_profile_state(target_user_id: str) -> PersonaProfileState | None:
    return await _refresh_profile_state(target_user_id)
