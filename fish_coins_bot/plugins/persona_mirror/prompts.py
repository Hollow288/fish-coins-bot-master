import json
from copy import deepcopy
from typing import Any

from .profile_schema import DEFAULT_ANALYZER_DELTA, DEFAULT_EXPRESSION_PROFILE, DEFAULT_V2_PROFILE


DEFAULT_PROFILE = deepcopy(DEFAULT_EXPRESSION_PROFILE)
DEFAULT_V2_PERSONA = deepcopy(DEFAULT_V2_PROFILE)

_LQ = "\u201c"
_RQ = "\u201d"


def build_analyzer_prompt(
    current_profile: dict[str, Any],
    incremental_stats: dict[str, Any],
    sample_messages: list[str],
    manual_inputs: dict[str, Any],
    context_samples: list[dict[str, Any]] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "current_profile": current_profile or DEFAULT_V2_PERSONA,
        "manual_inputs": manual_inputs,
        "incremental_stats": incremental_stats,
        "sample_messages": sample_messages,
    }
    if context_samples:
        payload["context_samples"] = context_samples

    context_instruction = ""
    if context_samples:
        context_instruction = (
            "6. context_samples 里给了目标发言前的群聊上下文、场景类型和可能的 reply_to 信息。\n"
            "   要据此判断这个人被@、被催、被调侃、被质疑时分别怎么回应。\n"
        )

    return (
        f"你是{_LQ}人格提取分析器{_RQ}。\n"
        "目标是从新增聊天样本中提取人格 delta，而不是直接输出最终画像。\n"
        "要同时分析表达风格、决策方式、人际行为、边界与雷区。\n"
        "手工标签优先级高于样本推断；如果冲突，必须把冲突写进 conflicts。\n"
        "不要总结具体事件，只总结可以长期复用的行为规律。\n"
        "输出必须是 JSON，不能附带解释。\n\n"
        "JSON 模板:\n"
        f"{json.dumps(DEFAULT_ANALYZER_DELTA, ensure_ascii=False, indent=2)}\n\n"
        "要求:\n"
        "1. expression 继续关注口头禅、句式、标点、QQ 表情、历史示例回复。\n"
        "2. decisions 要提取优先级、推进触发、回避触发、反对方式、被质疑时的反应。\n"
        "3. interpersonal 要覆盖对上、对下、对平级、压力下四个方向。\n"
        "4. boundaries 要写清楚不喜欢什么、红线、回避话题、拒绝方式。\n"
        "5. inferred_tags 只填你从样本中能稳定推断出来的标签，不要瞎猜。\n"
        f"{context_instruction}"
        "7. 如果证据不足，把字段名写到对应层的 insufficient_fields。\n"
        "8. conflicts 中每条都写 field/manual/inferred/reason，供后续编译层处理。\n"
        "9. 若样本中出现典型原话，可写到 supporting_evidence 或 sample_replies。\n\n"
        "输入数据:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_builder_prompt(
    current_profile: dict[str, Any],
    manual_inputs: dict[str, Any],
    corrections: list[dict[str, Any]],
    analyzer_delta: dict[str, Any],
) -> str:
    payload = {
        "current_profile": current_profile or DEFAULT_V2_PERSONA,
        "manual_inputs": manual_inputs,
        "corrections": corrections,
        "analyzer_delta": analyzer_delta,
    }
    return (
        f"你是{_LQ}人格画像编译器{_RQ}。\n"
        "把当前画像、手工输入、correction 纠偏和本次增量分析合成一个 v2 人格画像。\n"
        "优先级必须严格遵守: manual_inputs > corrections > existing stable profile > analyzer_delta。\n"
        "core_rules 只能来自手工标签和 correction，不允许根据样本臆造新的硬规则。\n"
        "输出必须是 JSON，结构必须兼容下面模板，不能附带解释。\n\n"
        "JSON 模板:\n"
        f"{json.dumps(DEFAULT_V2_PERSONA, ensure_ascii=False, indent=2)}\n\n"
        "要求:\n"
        "1. layers.identity 直接根据 manual_inputs 生成，没有手工信息时才保留已有内容。\n"
        "2. layers.expression/decisions/interpersonal/boundaries 可以吸收 analyzer_delta 的新信息。\n"
        "3. pending_conflicts 保留所有需要管理员后续确认的冲突。\n"
        "4. compiled_reply_profile 要能直接给回复模型使用，必须体现决策、人际、边界层约束。\n"
        "5. correction 要在 active_corrections / hard_constraints 中可见，并对回复有硬约束效果。\n\n"
        "输入数据:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _build_length_hint(compiled_reply_profile: dict[str, Any]) -> str:
    expression = compiled_reply_profile.get("expression", {})
    style = expression.get("sentence_style", {})
    length_range = str(style.get("typical_length_range", "")).strip()
    avg_length = str(style.get("avg_length", "")).strip()

    if length_range and "-" in length_range:
        return f"reply 长度应该在 {length_range} 个字左右，尽量贴近真实发言长度"
    if avg_length.isdigit():
        avg = int(avg_length)
        return f"reply 长度尽量控制在 {max(2, avg - 8)} 到 {avg + 12} 个字"
    return "reply 保持口语化，长度控制在 8 到 35 个字"


def _build_scene_hint(trigger_payload: dict[str, Any], compiled_reply_profile: dict[str, Any]) -> str:
    hints: list[str] = []
    if trigger_payload.get("at_target_user"):
        hints.append("当前是被直接@到的场景，回复应该像被点名后的自然反应")
    if trigger_payload.get("reply_to_target_user"):
        hints.append("当前是接续目标自己上一条消息的话题，回复要延续上下文")
    if trigger_payload.get("matched_keywords") and not trigger_payload.get("at_target_user"):
        hints.append("群友在聊到目标本人，回复应像听到自己被提及时的自然插话")

    corrections = compiled_reply_profile.get("active_corrections", [])
    if corrections:
        hints.append("如果 correction 中有匹配当前场景的规则，优先遵守 correction")

    return "；".join(hints)


def build_speak_prompt(
    target_identity: dict[str, Any],
    compiled_reply_profile: dict[str, Any],
    intent_text: str,
    recent_chat_messages: list[dict[str, Any]],
    similar_messages: list[str],
    top_face_ids: list[str],
    conversation_snippets: list[dict[str, Any]] | None = None,
    trigger_reason: dict[str, Any] | None = None,
) -> str:
    trigger_payload = trigger_reason or {}
    scene_hint = _build_scene_hint(trigger_payload, compiled_reply_profile)
    length_hint = _build_length_hint(compiled_reply_profile)
    return (
        f"你现在的任务是{_LQ}在群聊里代替目标说一句像他的话{_RQ}。\n"
        "你不是只模仿字面语气，还要模仿他的判断方式、人际姿态和边界感。\n"
        "只模仿风格，不要编造目标的私人事实。\n"
        "输出必须是 JSON，不能有解释文字。\n\n"
        "输出格式:\n"
        "{\n"
        '  "reply": "",\n'
        '  "face_id": ""\n'
        "}\n\n"
        "约束:\n"
        f"1. {length_hint}。\n"
        "2. 风格要像熟人群聊里的随口接话，不要写成客服、公文或旁白。\n"
        "3. 如果不适合用 QQ 表情，face_id 返回空字符串。\n"
        "4. 不要输出任何图片素材或自定义表情包相关内容。\n"
        "5. 优先遵守 compiled_reply_profile.hard_constraints 和 active_corrections。\n"
        "6. 如果这个人按画像应该不接这类话题，也要用他的方式拒绝、转移或简短带过，而不是硬接。\n"
        "7. 如果历史片段显示他习惯连发多条短消息，可以用换行模拟连发。\n"
        f"8. 触发场景提示: {scene_hint or '无特别场景提示'}。\n\n"
        f"目标身份信息:\n{json.dumps(target_identity, ensure_ascii=False, indent=2)}\n\n"
        f"当前触发信息:\n{json.dumps(trigger_payload, ensure_ascii=False, indent=2)}\n\n"
        f"最近群聊上下文:\n{json.dumps(recent_chat_messages, ensure_ascii=False, indent=2)}\n\n"
        f"编译后回复画像:\n{json.dumps(compiled_reply_profile, ensure_ascii=False, indent=2)}\n\n"
        "历史原话风格参考（仅供模仿风格，不要照抄内容）:\n"
        f"{json.dumps(similar_messages, ensure_ascii=False, indent=2)}\n\n"
        "目标历史对话片段（重点参考类似场景下的处理方式）:\n"
        f"{json.dumps(conversation_snippets or [], ensure_ascii=False, indent=2)}\n\n"
        f"常用 QQ 表情 ID:\n{json.dumps(top_face_ids, ensure_ascii=False)}\n\n"
        f"这次显性意图 explicit_intent:\n{intent_text}"
    )


def build_summary_prompt(
    current_profile: dict[str, Any],
    incremental_stats: dict[str, Any],
    sample_messages: list[str],
    context_samples: list[dict[str, Any]] | None = None,
    manual_inputs: dict[str, Any] | None = None,
) -> str:
    return build_analyzer_prompt(
        current_profile=current_profile,
        incremental_stats=incremental_stats,
        sample_messages=sample_messages,
        manual_inputs=manual_inputs or {},
        context_samples=context_samples,
    )
