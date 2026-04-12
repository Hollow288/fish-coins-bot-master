import json
from typing import Any


DEFAULT_PROFILE = {
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

# 中文弯引号，避免和 Python 字符串定界符冲突
_LQ = "\u201c"  # "
_RQ = "\u201d"  # "


def build_summary_prompt(
    current_profile: dict[str, Any],
    incremental_stats: dict[str, Any],
    sample_messages: list[str],
    context_samples: list[dict[str, Any]] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "current_profile": current_profile or DEFAULT_PROFILE,
        "incremental_stats": incremental_stats,
        "sample_messages": sample_messages,
    }
    if context_samples:
        payload["context_samples"] = context_samples

    context_instruction = ""
    if context_samples:
        context_instruction = (
            "5. context_samples 里包含了目标部分发言的前后群聊上下文和场景分类，\n"
            "   每个样本包括: context（发言前的群聊记录，带发言者信息）、target_said（目标说的话）、\n"
            "   scene_type（场景类型，如被@后回应、回复他人、被提及后回应、连续发言、主动发言）、\n"
            "   reply_to（如果是回复别人的消息，记录了被回复的内容和对方名字）。\n"
            "   据此重点分析：目标在不同场景下的回应风格差异，更新 response_patterns 和 situational_patterns。\n"
            "   特别注意目标被提问、被@、被调侃时分别是怎么回应的。\n"
        )

    return (
        f"你是{_LQ}聊天风格画像分析器{_RQ}。\n"
        f"任务是根据历史画像和新增聊天样本，输出一个{_LQ}更完整、更稳定{_RQ}的人设画像。\n"
        "只总结表达习惯，不总结具体事件，不要猜测没有证据的性格或经历。\n"
        "输出必须是 JSON，对象结构必须与下面模板兼容，不能附带解释文字。\n\n"
        "JSON 模板:\n"
        f"{json.dumps(DEFAULT_PROFILE, ensure_ascii=False, indent=2)}\n\n"
        "要求:\n"
        "1. catchphrases 只保留目标真正反复使用的表达，不要填入通用网络流行语。\n"
        "   habit_words 保留高频用词和语气词组合。\n"
        f"2. negative_rules 写清楚不要模仿成什么样（例如{_LQ}不用书面语{_RQ}、{_LQ}不用敬语{_RQ}）。\n"
        "3. emoji_habits.qq_faces 只保留最常见的表情ID字符串。\n"
        "4. reply_constraints 写成生成回复时必须遵守的简短约束。\n"
        f"{context_instruction}"
        f"6. sentence_style.avg_length 填数字（如{_LQ}12{_RQ}），typical_length_range 填范围（如{_LQ}3-20{_RQ}）。\n"
        f"   ending_habits 填这个人句尾常见的收尾方式（如{_LQ}~{_RQ}、{_LQ}哈哈{_RQ}、{_LQ}。{_RQ}、不加标点等）。\n"
        "7. response_patterns 描述他在不同场景下的回应习惯：\n"
        f"   例如{_LQ}被问问题时直接给答案不啰嗦{_RQ}、{_LQ}被调侃时会反怼{_RQ}、{_LQ}附和别人时说'确实'{_RQ}。\n"
        "8. topic_tendencies 描述他倾向于聊什么、回避什么。\n"
        "9. greeting_farewell 描述他打招呼和告别的方式，如果样本中没有则留空。\n"
        "10. 仔细观察样本中的标点使用习惯：是否省略句号、是否连用问号、是否喜欢用省略号等。\n\n"
        "输入数据:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _build_length_hint(profile: dict[str, Any]) -> str:
    """根据画像中的长度信息动态生成回复长度约束。"""
    style = profile.get("sentence_style", {})
    length_range = str(style.get("typical_length_range", "")).strip()
    avg_length = str(style.get("avg_length", "")).strip()

    if length_range and "-" in length_range:
        return f"reply 长度应该在 {length_range} 个字左右，与目标的真实发言长度保持一致"

    if avg_length and avg_length.isdigit():
        avg = int(avg_length)
        min_len = max(2, avg - 8)
        max_len = avg + 12
        return f"reply 长度控制在 {min_len} 到 {max_len} 个字左右"

    return "reply 保持口语化，长度控制在 8 到 35 个字"


def build_speak_prompt(
    target_identity: dict[str, Any],
    profile: dict[str, Any],
    intent_text: str,
    recent_chat_messages: list[dict[str, Any]],
    similar_messages: list[str],
    top_face_ids: list[str],
    conversation_snippets: list[dict[str, Any]] | None = None,
    trigger_reason: dict[str, Any] | None = None,
) -> str:
    trigger_payload = trigger_reason or {}
    length_hint = _build_length_hint(profile)

    # 根据触发类型生成场景提示
    scene_hint = _build_scene_hint(trigger_payload)

    return (
        f"你现在的任务是{_LQ}在群聊里代替目标说一句像他的话{_RQ}。\n"
        "只模仿语气、句式、口头禅和表情习惯，不要编造私人事实。\n"
        "你必须结合最近群聊上下文来判断大家在聊什么，避免脱离话题乱说。\n"
        "最近群聊上下文里，is_target_user=true 的消息就是目标本人说的话。\n"
        "aliases 是大家对目标的称呼、外号或名字，群友提到这些词，通常是在叫他或讨论他。\n"
        "如果 explicit_intent 为空，要主要依据 recent_chat_messages 判断应该接什么话。\n"
        "输出必须是 JSON，不能有解释文字。\n\n"
        "输出格式:\n"
        "{\n"
        '  "reply": "",\n'
        '  "face_id": ""\n'
        "}\n\n"
        "约束:\n"
        f"1. {length_hint}。\n"
        "2. 风格要像熟人群聊随口接话，不要写成客服或公文。\n"
        "3. 如果不适合用 QQ 表情，face_id 返回空字符串。\n"
        "4. 不要输出任何图片素材或自定义表情包相关内容。\n"
        f"5. 仔细看下面的{_LQ}历史原话风格参考{_RQ}，你的 reply 必须在语气、句式、标点、用词习惯上"
        "尽量接近这些真实发言的风格，但不要照抄内容。\n"
        "6. 特别注意画像中的 ending_habits 和 punctuation，"
        "句尾风格要和目标保持一致（比如目标从不加句号你也不要加）。\n"
        "7. 重点参考下面的「目标历史对话片段」，这些片段展示了目标在类似场景下怎么接话。\n"
        "   观察目标的接话节奏：他是一条消息说完，还是习惯连发好几条短消息。\n"
        "   如果片段中 target_replies 有多条，说明目标习惯连发，你的 reply 也应该用换行分成多条短句。\n"
        "   如果片段中有 reply_to，说明目标在回应某条具体消息，参考他回应的方式和语气。\n"
        f"{scene_hint}\n\n"
        f"目标身份信息:\n{json.dumps(target_identity, ensure_ascii=False, indent=2)}\n\n"
        f"当前触发信息:\n{json.dumps(trigger_payload, ensure_ascii=False, indent=2)}\n\n"
        f"最近群聊上下文:\n{json.dumps(recent_chat_messages, ensure_ascii=False, indent=2)}\n\n"
        f"人物画像:\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
        "历史原话风格参考（仅供模仿风格，不要照抄内容）:\n"
        f"{json.dumps(similar_messages, ensure_ascii=False, indent=2)}\n\n"
        f"目标历史对话片段（展示他在类似场景下怎么接话，重点参考）:\n"
        f"{json.dumps(conversation_snippets or [], ensure_ascii=False, indent=2)}\n\n"
        f"常用 QQ 表情 ID:\n{json.dumps(top_face_ids, ensure_ascii=False)}\n\n"
        f"这次显性意图 explicit_intent:\n{intent_text}"
    )


def _build_scene_hint(trigger_payload: dict[str, Any]) -> str:
    """根据触发信息生成场景提示，帮助 AI 选择合适的回复策略。"""
    hints: list[str] = []
    if trigger_payload.get("at_target_user"):
        hints.append("有人直接@了目标，回复应像被叫到名字后的自然反应")
    if trigger_payload.get("reply_to_target_user"):
        hints.append("有人在回复目标之前说的话，回复应该延续之前的话题")
    if trigger_payload.get("matched_keywords") and not trigger_payload.get("at_target_user"):
        hints.append("群友在聊天中提到了目标的名字/外号，回复应像听到有人谈论自己时的自然插话")

    if not hints:
        return ""
    return "8. 触发场景提示: " + "；".join(hints) + "。"
