import json
import random
from collections import Counter
from typing import Any, Callable

from ..config import get_plugin_config
from ..models import PersonaAsset, PersonaMessage, PersonaProfileSnapshot, PersonaProfileState, PersonaTarget
from ..profile_schema import (
    DEFAULT_V2_PROFILE,
    build_compiled_reply_profile,
    compose_v2_profile,
    normalize_analyzer_delta,
    normalize_manual_profile,
    normalize_v2_profile,
)
from ..prompts import build_analyzer_prompt, build_builder_prompt, build_speak_prompt
from ..utils import render_segments_as_text, safe_json_loads, similarity_score, top_items
from .ai_client import call_text_model
from .persona_service import get_effective_trigger_keywords, list_correction_dicts


def _build_incremental_stats(messages: list[PersonaMessage]) -> dict[str, Any]:
    non_empty_texts = [message.plain_text for message in messages if message.plain_text]
    feature_list = [message.feature_json or {} for message in messages]
    text_lengths = [int(feature.get("text_length", 0)) for feature in feature_list]
    face_counter: Counter[str] = Counter()
    seed_phrase_counter: Counter[str] = Counter()
    modal_counter: Counter[str] = Counter()
    punctuation_counter: Counter[str] = Counter()
    content_word_counter: Counter[str] = Counter()
    bigram_counter: Counter[str] = Counter()
    ending_counter: Counter[str] = Counter()
    question_count = 0
    exclamation_count = 0

    for feature in feature_list:
        face_counter.update(str(item) for item in feature.get("face_ids", []))
        seed_phrase_counter.update(str(item) for item in feature.get("seed_phrase_hits", feature.get("phrase_hits", [])))
        modal_counter.update(str(item) for item in feature.get("modal_words", []))
        punctuation_counter.update(
            {str(key): int(value) for key, value in (feature.get("punctuation") or {}).items()}
        )
        content_word_counter.update(str(item) for item in feature.get("content_words", []))
        bigram_counter.update(str(item) for item in feature.get("bigrams", []))
        ending = feature.get("ending_char", "")
        if ending:
            ending_counter[ending] += 1
        question_count += 1 if feature.get("has_question") else 0
        exclamation_count += 1 if feature.get("has_exclamation") else 0

    sample_count = len(messages)
    avg_length = round(sum(text_lengths) / sample_count, 2) if sample_count else 0
    sorted_lengths = sorted(length for length in text_lengths if length > 0)
    if sorted_lengths:
        p10 = sorted_lengths[max(0, len(sorted_lengths) // 10)]
        p90 = sorted_lengths[min(len(sorted_lengths) - 1, len(sorted_lengths) * 9 // 10)]
        length_range = f"{p10}-{p90}"
    else:
        length_range = ""

    return {
        "sample_count": sample_count,
        "non_empty_text_count": len(non_empty_texts),
        "average_text_length": avg_length,
        "typical_length_range": length_range,
        "question_ratio": round(question_count / sample_count, 3) if sample_count else 0,
        "exclamation_ratio": round(exclamation_count / sample_count, 3) if sample_count else 0,
        "top_face_ids": top_items(face_counter, 5),
        "top_seed_phrases": top_items(seed_phrase_counter, 8),
        "top_modal_words": top_items(modal_counter, 8),
        "top_punctuation": top_items(punctuation_counter, 6),
        "top_content_words": top_items(content_word_counter, 15),
        "top_bigrams": top_items(bigram_counter, 10),
        "top_ending_chars": top_items(ending_counter, 5),
    }


def _build_context_samples(messages: list[PersonaMessage], max_samples: int = 8) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for msg in messages:
        context = msg.context_json
        if not context or not msg.plain_text:
            continue
        sample: dict[str, Any] = {
            "context": context,
            "target_said": msg.plain_text,
            "scene_type": msg.scene_type,
        }
        if msg.reply_to_text:
            sample["reply_to"] = {
                "user_name": msg.reply_to_user_name or "",
                "text": msg.reply_to_text,
            }
        samples.append(sample)
        if len(samples) >= max_samples:
            break
    return samples


def _build_json_retry_prompt(prompt: str) -> str:
    return (
        f"{prompt}\n\n"
        "补充要求：\n"
        "1. 只输出一个合法 JSON 对象。\n"
        "2. 不要输出 ```json、解释、说明、前后缀。\n"
        "3. 所有字段都必须与上面的模板兼容。"
    )


async def _call_json_model(
    prompt: str,
    memory_prefix: str,
    validator: Callable[[dict[str, Any]], bool],
    max_attempts: int = 2,
) -> tuple[dict[str, Any] | None, str | None]:
    current_prompt = prompt
    last_raw_response: str | None = None

    for _attempt in range(max_attempts):
        raw_response = await call_text_model(current_prompt, memory_prefix=memory_prefix)
        if raw_response is None:
            continue

        last_raw_response = raw_response
        parsed = safe_json_loads(raw_response)
        if parsed is not None and validator(parsed):
            return parsed, raw_response

        current_prompt = _build_json_retry_prompt(prompt)

    return None, last_raw_response


async def summarize_target(target: PersonaTarget, force: bool = False) -> tuple[bool, str]:
    config = get_plugin_config()
    pending_query = PersonaMessage.filter(
        target_user_id=target.target_user_id,
        id__gt=target.last_summarized_message_id,
    ).order_by("id")

    pending_count = await pending_query.count()
    if pending_count == 0:
        return False, "没有新增消息。"

    batch_limit = max(target.summary_batch_size, config.summary_batch_size)
    if not force and pending_count < batch_limit:
        return False, f"新增消息 {pending_count} 条，未达到阈值 {batch_limit}。"

    limit = min(max(batch_limit * 3, config.summary_sample_size), pending_count) if force else batch_limit
    messages = await pending_query.limit(limit)
    if not messages:
        return False, "没有可总结的消息。"

    current_state = await PersonaProfileState.get_or_none(target_user_id=target.target_user_id)
    corrections = await list_correction_dicts(target.target_user_id)
    manual_inputs = normalize_manual_profile(target.manual_profile_json)
    current_profile = normalize_v2_profile(
        current_state.current_profile_json if current_state else DEFAULT_V2_PROFILE,
        manual_inputs=manual_inputs,
        corrections=corrections,
    )
    stats = _build_incremental_stats(messages)
    sample_messages = [
        rendered
        for message in messages
        if (rendered := render_segments_as_text(message.raw_segments_json))
    ][: config.summary_sample_size]
    context_samples = _build_context_samples(messages)

    analyzer_prompt = build_analyzer_prompt(
        current_profile=current_profile,
        incremental_stats=stats,
        sample_messages=sample_messages,
        manual_inputs=manual_inputs,
        context_samples=context_samples if context_samples else None,
    )
    analyzer_json, analyzer_raw = await _call_json_model(
        analyzer_prompt,
        memory_prefix=f"persona-analyzer-{target.target_user_id}",
        validator=lambda payload: isinstance(payload, dict),
    )
    if analyzer_raw is None or analyzer_json is None:
        return False, "AI 人格分析结果不是合法 JSON。"

    normalized_delta = normalize_analyzer_delta(analyzer_json)
    builder_prompt = build_builder_prompt(
        current_profile=current_profile,
        manual_inputs=manual_inputs,
        corrections=corrections,
        analyzer_delta=normalized_delta,
    )
    builder_json, builder_raw = await _call_json_model(
        builder_prompt,
        memory_prefix=f"persona-builder-{target.target_user_id}",
        validator=lambda payload: isinstance(payload, dict),
    )

    normalized_profile = compose_v2_profile(
        current_profile=current_profile,
        analyzer_delta=normalized_delta,
        builder_profile=builder_json,
        manual_inputs=manual_inputs,
        corrections=corrections,
    )

    prompt_text = json.dumps(
        {
            "analyzer_prompt": analyzer_prompt,
            "builder_prompt": builder_prompt,
        },
        ensure_ascii=False,
    )
    raw_response = json.dumps(
        {
            "analyzer_raw": analyzer_raw,
            "builder_raw": builder_raw or "",
        },
        ensure_ascii=False,
    )
    snapshot = await PersonaProfileSnapshot.create(
        target_user_id=target.target_user_id,
        summary_type="manual" if force else "incremental",
        source_message_count=len(messages),
        start_message_id=messages[0].id,
        end_message_id=messages[-1].id,
        summary_json=normalized_profile,
        prompt_text=prompt_text,
        raw_response=raw_response,
    )

    total_message_count = await PersonaMessage.filter(target_user_id=target.target_user_id).count()
    if current_state is None:
        await PersonaProfileState.create(
            target_user_id=target.target_user_id,
            current_profile_json=normalized_profile,
            latest_snapshot_id=snapshot.id,
            last_summary_message_id=messages[-1].id,
            last_summary_at=snapshot.created_at,
            total_message_count=total_message_count,
        )
    else:
        current_state.current_profile_json = normalized_profile
        current_state.latest_snapshot_id = snapshot.id
        current_state.last_summary_message_id = messages[-1].id
        current_state.last_summary_at = snapshot.created_at
        current_state.total_message_count = total_message_count
        await current_state.save()

    target.last_summarized_message_id = messages[-1].id
    await target.save()

    conflict_count = len(normalized_profile.get("pending_conflicts", []))
    detail = f"已总结 {len(messages)} 条消息，最新快照 ID: {snapshot.id}"
    if conflict_count:
        detail += f"，待确认冲突 {conflict_count} 条"
    return True, detail


async def _fetch_candidate_messages(
    target_user_id: str,
    recent_limit: int = 200,
    history_sample: int = 100,
) -> list[PersonaMessage]:
    recent_messages = await (
        PersonaMessage.filter(target_user_id=target_user_id)
        .order_by("-id")
        .limit(recent_limit)
    )

    total_count = await PersonaMessage.filter(target_user_id=target_user_id).count()
    if total_count <= recent_limit:
        return [msg for msg in recent_messages if msg.plain_text]

    recent_ids = {msg.id for msg in recent_messages}
    oldest_recent_id = min(recent_ids) if recent_ids else 0
    older_messages = await (
        PersonaMessage.filter(target_user_id=target_user_id, id__lt=oldest_recent_id)
        .order_by("-id")
        .limit(history_sample * 3)
    )
    older_with_text = [msg for msg in older_messages if msg.plain_text]
    if len(older_with_text) > history_sample:
        older_with_text = random.sample(older_with_text, history_sample)

    return [msg for msg in recent_messages if msg.plain_text] + older_with_text


def _infer_scene_type_from_trigger(trigger_reason: dict[str, Any] | None) -> str | None:
    if not trigger_reason:
        return None
    if trigger_reason.get("at_target_user"):
        return "被@后回应"
    if trigger_reason.get("reply_to_target_user"):
        return "回复他人"
    if trigger_reason.get("matched_keywords"):
        return "被提及后回应"
    return None


async def _fetch_conversation_snippets(
    target_user_id: str,
    search_query: str,
    current_scene_type: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    messages = await (
        PersonaMessage.filter(target_user_id=target_user_id)
        .order_by("-id")
        .limit(300)
    )
    messages = list(reversed(messages))

    raw_snippets: list[dict[str, Any]] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if not msg.context_json or msg.is_continuation:
            i += 1
            continue

        target_replies = [msg.plain_text] if msg.plain_text else []
        j = i + 1
        while j < len(messages) and messages[j].is_continuation and messages[j].target_user_id == target_user_id:
            if messages[j].plain_text:
                target_replies.append(messages[j].plain_text)
            j += 1

        if target_replies:
            snippet: dict[str, Any] = {
                "context": msg.context_json,
                "target_replies": target_replies,
                "scene_type": msg.scene_type,
            }
            if msg.reply_to_text:
                snippet["reply_to"] = {
                    "user_name": msg.reply_to_user_name or "",
                    "text": msg.reply_to_text,
                }
            raw_snippets.append(snippet)
        i = j

    if not raw_snippets:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for snippet in raw_snippets:
        score = 0.0
        if current_scene_type and snippet["scene_type"] == current_scene_type:
            score += 1.0
        if search_query:
            combined_reply = " ".join(snippet["target_replies"])
            score += similarity_score(search_query, combined_reply) * 0.5
            context_text = " ".join(c.get("text", "") for c in snippet["context"])
            score += similarity_score(search_query, context_text) * 0.3
        scored.append((score, snippet))

    scored.sort(key=lambda item: item[0], reverse=True)
    top_snippets = [snippet for _, snippet in scored[:limit]]
    if len(scored) > limit:
        remaining = [snippet for _, snippet in scored[limit:]]
        top_snippets.extend(random.sample(remaining, min(2, len(remaining))))
    return top_snippets[:limit]


async def generate_reply(
    target: PersonaTarget,
    intent_text: str,
    recent_chat_messages: list[dict[str, Any]] | None = None,
    trigger_reason: dict[str, Any] | None = None,
) -> dict[str, str]:
    config = get_plugin_config()
    profile_state = await PersonaProfileState.get_or_none(target_user_id=target.target_user_id)
    if profile_state is None or not profile_state.current_profile_json:
        raise RuntimeError("目标还没有画像，请先执行一次【人设总结】。")

    corrections = await list_correction_dicts(target.target_user_id)
    normalized_profile = normalize_v2_profile(
        profile_state.current_profile_json,
        manual_inputs=target.manual_profile_json,
        corrections=corrections,
    )
    compiled_reply_profile = build_compiled_reply_profile(normalized_profile, corrections=corrections)

    target_aliases = get_effective_trigger_keywords(target)
    target_identity = {
        "target_user_id": target.target_user_id,
        "display_name": target.target_name or "",
        "aliases": target_aliases,
    }

    search_query = intent_text
    if not search_query and recent_chat_messages:
        search_query = " ".join(msg["text"] for msg in recent_chat_messages[-3:] if msg.get("text"))

    candidate_messages = await _fetch_candidate_messages(target.target_user_id)
    if search_query and candidate_messages:
        scored_messages = sorted(
            candidate_messages,
            key=lambda item: similarity_score(search_query, item.plain_text or ""),
            reverse=True,
        )
    else:
        scored_messages = candidate_messages

    similar_messages = [
        rendered
        for message in scored_messages[: config.speak_sample_size]
        if (rendered := render_segments_as_text(message.raw_segments_json))
    ]
    if not similar_messages:
        similar_messages = [
            rendered
            for message in candidate_messages[: config.speak_sample_size]
            if (rendered := render_segments_as_text(message.raw_segments_json))
        ]

    face_assets = await PersonaAsset.filter(
        target_user_id=target.target_user_id,
        asset_type="face",
    ).order_by("-used_count").limit(5)
    top_face_ids = [asset.face_id for asset in face_assets if asset.face_id]

    current_scene_type = _infer_scene_type_from_trigger(trigger_reason)
    conversation_snippets = await _fetch_conversation_snippets(
        target_user_id=target.target_user_id,
        search_query=search_query,
        current_scene_type=current_scene_type,
        limit=5,
    )

    prompt = build_speak_prompt(
        target_identity=target_identity,
        compiled_reply_profile=compiled_reply_profile,
        intent_text=intent_text,
        recent_chat_messages=recent_chat_messages or [],
        similar_messages=similar_messages,
        top_face_ids=top_face_ids,
        conversation_snippets=conversation_snippets,
        trigger_reason=trigger_reason,
    )
    result, raw_response = await _call_json_model(
        prompt,
        memory_prefix=f"persona-speak-{target.target_user_id}",
        validator=lambda payload: bool(str(payload.get("reply", "")).strip()),
    )
    if raw_response is None:
        raise RuntimeError("AI 模仿接口调用失败。")
    if result is None:
        raise RuntimeError("AI 模仿结果不是合法 JSON。")

    reply = str(result.get("reply", "")).strip()
    face_id = str(result.get("face_id", "")).strip()
    if not reply:
        raise RuntimeError("AI 没有生成有效回复。")

    return {
        "reply": reply,
        "face_id": face_id,
    }
