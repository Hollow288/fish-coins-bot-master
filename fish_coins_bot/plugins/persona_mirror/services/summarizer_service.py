import random
from collections import Counter
from typing import Any, Callable

from ..config import get_plugin_config
from ..models import PersonaAsset, PersonaMessage, PersonaProfileSnapshot, PersonaProfileState, PersonaTarget
from ..prompts import DEFAULT_PROFILE, build_speak_prompt, build_summary_prompt
from ..utils import render_segments_as_text, safe_json_loads, similarity_score, top_items
from .ai_client import call_text_model
from .persona_service import get_effective_trigger_keywords


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str) and value.strip():
        items = [value.strip()]
    else:
        items = []

    deduplicated: list[str] = []
    for item in items:
        if item not in deduplicated:
            deduplicated.append(item)
    return deduplicated


def _normalize_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "tone": [],
        "sentence_style": {
            "avg_length": "",
            "typical_length_range": "",
            "structure": "",
            "punctuation": [],
            "rhythm": "",
            "ending_habits": [],
        },
        "catchphrases": [],
        "habit_words": [],
        "emoji_habits": {
            "qq_faces": [],
        },
        "response_patterns": [],
        "topic_tendencies": [],
        "greeting_farewell": "",
        "situational_patterns": [],
        "negative_rules": [],
        "reply_constraints": [],
    }
    if not isinstance(profile, dict):
        return merged

    sentence_style = profile.get("sentence_style", {})
    emoji_habits = profile.get("emoji_habits", {})

    merged["tone"] = _normalize_list(profile.get("tone"))
    merged["sentence_style"] = {
        "avg_length": str(sentence_style.get("avg_length", "")).strip(),
        "typical_length_range": str(sentence_style.get("typical_length_range", "")).strip(),
        "structure": str(sentence_style.get("structure", "")).strip(),
        "punctuation": _normalize_list(sentence_style.get("punctuation")),
        "rhythm": str(sentence_style.get("rhythm", "")).strip(),
        "ending_habits": _normalize_list(sentence_style.get("ending_habits")),
    }
    merged["catchphrases"] = _normalize_list(profile.get("catchphrases"))
    merged["habit_words"] = _normalize_list(profile.get("habit_words"))
    merged["emoji_habits"] = {
        "qq_faces": _normalize_list(emoji_habits.get("qq_faces")),
    }
    merged["response_patterns"] = _normalize_list(profile.get("response_patterns"))
    merged["topic_tendencies"] = _normalize_list(profile.get("topic_tendencies"))
    merged["greeting_farewell"] = str(profile.get("greeting_farewell", "")).strip()
    merged["situational_patterns"] = _normalize_list(profile.get("situational_patterns"))
    merged["negative_rules"] = _normalize_list(profile.get("negative_rules"))
    merged["reply_constraints"] = _normalize_list(profile.get("reply_constraints"))
    return merged


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

    # 计算长度范围
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
    """从消息中提取有上下文的样本，用于画像总结时理解场景。"""
    samples: list[dict[str, Any]] = []
    for msg in messages:
        feature = msg.feature_json or {}
        context_before = feature.get("context_before")
        if context_before and msg.plain_text:
            samples.append({
                "context_before": context_before,
                "target_said": msg.plain_text,
            })
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

    if force:
        limit = min(max(batch_limit * 3, config.summary_sample_size), pending_count)
    else:
        limit = batch_limit

    messages = await pending_query.limit(limit)
    if not messages:
        return False, "没有可总结的消息。"

    current_state = await PersonaProfileState.get_or_none(target_user_id=target.target_user_id)
    current_profile = current_state.current_profile_json if current_state else DEFAULT_PROFILE
    stats = _build_incremental_stats(messages)
    sample_messages = [
        render_segments_as_text(message.raw_segments_json)
        for message in messages
        if render_segments_as_text(message.raw_segments_json)
    ][: config.summary_sample_size]

    # 提取有上下文的样本
    context_samples = _build_context_samples(messages)

    prompt = build_summary_prompt(
        current_profile=_normalize_profile(current_profile),
        incremental_stats=stats,
        sample_messages=sample_messages,
        context_samples=context_samples if context_samples else None,
    )
    summary_json, raw_response = await _call_json_model(
        prompt,
        memory_prefix=f"persona-summary-{target.target_user_id}",
        validator=lambda payload: isinstance(payload, dict),
    )
    if raw_response is None:
        return False, "AI 总结接口调用失败。"
    if summary_json is None:
        return False, "AI 总结结果不是合法 JSON。"

    normalized_profile = _normalize_profile(summary_json)
    snapshot = await PersonaProfileSnapshot.create(
        target_user_id=target.target_user_id,
        summary_type="manual" if force else "incremental",
        source_message_count=len(messages),
        start_message_id=messages[0].id,
        end_message_id=messages[-1].id,
        summary_json=normalized_profile,
        prompt_text=prompt,
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

    return True, f"已总结 {len(messages)} 条消息，最新快照 ID: {snapshot.id}"


async def _fetch_candidate_messages(
    target_user_id: str,
    recent_limit: int = 200,
    history_sample: int = 100,
) -> list[PersonaMessage]:
    """获取候选消息池：最近 N 条 + 随机历史采样，覆盖更广的表达模式。"""
    recent_messages = await (
        PersonaMessage.filter(target_user_id=target_user_id)
        .order_by("-id")
        .limit(recent_limit)
    )

    total_count = await PersonaMessage.filter(target_user_id=target_user_id).count()
    if total_count <= recent_limit:
        return [msg for msg in recent_messages if msg.plain_text]

    # 从更早的历史中随机采样
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

    all_candidates = [msg for msg in recent_messages if msg.plain_text] + older_with_text
    return all_candidates


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

    target_aliases = get_effective_trigger_keywords(target)
    target_identity = {
        "target_user_id": target.target_user_id,
        "display_name": target.target_name or "",
        "aliases": target_aliases,
    }

    # 当 intent_text 为空时，用最近群聊上下文构造检索 query
    search_query = intent_text
    if not search_query and recent_chat_messages:
        search_query = " ".join(
            msg["text"] for msg in recent_chat_messages[-3:] if msg.get("text")
        )

    # 从扩大的候选池中检索相似消息
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
        render_segments_as_text(message.raw_segments_json)
        for message in scored_messages[: config.speak_sample_size]
        if render_segments_as_text(message.raw_segments_json)
    ]
    if not similar_messages:
        similar_messages = [
            render_segments_as_text(message.raw_segments_json)
            for message in candidate_messages[: config.speak_sample_size]
            if render_segments_as_text(message.raw_segments_json)
        ]

    face_assets = await PersonaAsset.filter(
        target_user_id=target.target_user_id,
        asset_type="face",
    ).order_by("-used_count").limit(5)
    top_face_ids = [asset.face_id for asset in face_assets if asset.face_id]

    prompt = build_speak_prompt(
        target_identity=target_identity,
        profile=_normalize_profile(profile_state.current_profile_json),
        intent_text=intent_text,
        recent_chat_messages=recent_chat_messages or [],
        similar_messages=similar_messages,
        top_face_ids=top_face_ids,
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
