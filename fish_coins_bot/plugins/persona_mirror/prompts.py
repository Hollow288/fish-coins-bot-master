import json
from typing import Any

from .utils import FACE_MEANINGS, render_face_id_with_hint


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
        "usage_ratio": "",
        "position_preference": [],
        "standalone_use": "",
        "scene_usage": [],
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
        "3. emoji_habits 必须根据 incremental_stats 中的表情数据认真填写所有子字段：\n"
        f"   - qq_faces: 最常用的表情 ID 字符串，按使用频次降序，最多 8 个；\n"
        f"   - usage_ratio: 根据 face_usage_ratio 选择{_LQ}很高{_RQ}（>=0.4）/{_LQ}较高{_RQ}（0.2-0.4）/"
        f"{_LQ}中等{_RQ}（0.1-0.2）/{_LQ}较低{_RQ}（0.03-0.1）/{_LQ}极少{_RQ}（<0.03）；\n"
        f"   - position_preference: 列出常见位置，如{_LQ}句尾{_RQ}、{_LQ}独立成条{_RQ}、{_LQ}夹在文中{_RQ}；\n"
        f"   - standalone_use: 是否常单发表情（参考 standalone_face_ratio），写一句话；\n"
        f"   - scene_usage: 列出{_LQ}什么情绪/场景下用哪个 ID{_RQ}，例如{_LQ}笑场用 178{_RQ}、{_LQ}无奈用 34{_RQ}。\n"
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


_USAGE_RATIO_KEYWORDS_HIGH = ("很高", "高", "经常", "频繁")
_USAGE_RATIO_KEYWORDS_MID = ("中等", "适中", "时不时")
_USAGE_RATIO_KEYWORDS_LOW = ("较低", "极少", "很少", "不太", "不常")


def _build_face_usage_hint(profile: dict[str, Any], top_face_ids: list[str]) -> str:
    """把画像中的表情习惯翻译成自然语言指引，避免 AI 默认不发表情。"""
    emoji_habits = profile.get("emoji_habits", {}) or {}
    usage_ratio = str(emoji_habits.get("usage_ratio", "")).strip()
    position_preference = emoji_habits.get("position_preference") or []
    standalone_use = str(emoji_habits.get("standalone_use", "")).strip()
    scene_usage = emoji_habits.get("scene_usage") or []

    lines: list[str] = []

    # 频率指引
    if not usage_ratio:
        if top_face_ids:
            lines.append("目标会用 QQ 表情，请按口语聊天的习惯自然地穿插表情，不要刻意省略。")
    elif any(kw in usage_ratio for kw in _USAGE_RATIO_KEYWORDS_HIGH):
        lines.append(
            f"目标用表情频率{usage_ratio}，几乎每两三条就有一个表情，"
            "本次回复请大概率带上表情；如果是连发多条，至少有一条带表情。"
        )
    elif any(kw in usage_ratio for kw in _USAGE_RATIO_KEYWORDS_MID):
        lines.append(
            f"目标用表情频率{usage_ratio}，本次回复约 1/3 概率带表情；"
            "回复内容偏情绪化（如开心/无奈/调侃）时优先加表情。"
        )
    elif any(kw in usage_ratio for kw in _USAGE_RATIO_KEYWORDS_LOW):
        lines.append(
            f"目标用表情频率{usage_ratio}，本次回复绝大多数情况不带表情；"
            "只在情绪表达强烈时才考虑加表情。"
        )
    else:
        lines.append(f"目标用表情频率：{usage_ratio}，按这个比例自然使用表情。")

    # 位置指引
    if position_preference:
        positions_text = "、".join(str(p) for p in position_preference if str(p).strip())
        if positions_text:
            lines.append(f"目标使用表情的位置偏好：{positions_text}，请遵循这个位置习惯。")

    # 独立成条
    if standalone_use:
        lines.append(f"关于纯表情消息：{standalone_use}。")

    # 场景映射
    if scene_usage:
        examples = "；".join(str(item) for item in scene_usage[:6] if str(item).strip())
        if examples:
            lines.append(f"场景对应的表情用法：{examples}。")

    if not lines:
        return ""
    return "\n".join(f"   {line}" for line in lines)


def _build_face_glossary(
    top_face_ids: list[str],
    emoji_habits: dict[str, Any],
    face_usage_stats: list[dict[str, Any]] | None = None,
) -> list[str]:
    """生成表情 ID -> 语义的对照表，附带相对占比信息（若有）。"""
    selected: list[str] = []
    seen: set[str] = set()
    share_lookup: dict[str, float] = {}
    count_lookup: dict[str, int] = {}

    if face_usage_stats:
        for item in face_usage_stats:
            fid = str(item.get("id", "")).strip()
            if not fid:
                continue
            if fid not in seen:
                selected.append(fid)
                seen.add(fid)
            try:
                share_lookup[fid] = float(item.get("share", 0) or 0)
            except (TypeError, ValueError):
                share_lookup[fid] = 0.0
            try:
                count_lookup[fid] = int(item.get("count", 0) or 0)
            except (TypeError, ValueError):
                count_lookup[fid] = 0

    for fid in top_face_ids:
        fid_str = str(fid).strip()
        if fid_str and fid_str not in seen:
            selected.append(fid_str)
            seen.add(fid_str)

    profile_faces = emoji_habits.get("qq_faces") or []
    for fid in profile_faces:
        fid_str = str(fid).strip()
        if fid_str and fid_str not in seen:
            selected.append(fid_str)
            seen.add(fid_str)

    glossary: list[str] = []
    for fid in selected:
        meaning = FACE_MEANINGS.get(fid, "未知含义")
        share = share_lookup.get(fid)
        count = count_lookup.get(fid)
        suffix = ""
        if share and share > 0:
            suffix = f"（约占 {share * 100:.0f}%, 累计 {count} 次）"
        glossary.append(f"[face:{fid}] = {meaning}{suffix}")
    return glossary


def build_speak_prompt(
    target_identity: dict[str, Any],
    profile: dict[str, Any],
    intent_text: str,
    recent_chat_messages: list[dict[str, Any]],
    similar_messages: list[str],
    top_face_ids: list[str],
    conversation_snippets: list[dict[str, Any]] | None = None,
    trigger_reason: dict[str, Any] | None = None,
    face_usage_stats: list[dict[str, Any]] | None = None,
) -> str:
    trigger_payload = trigger_reason or {}
    length_hint = _build_length_hint(profile)

    # 根据触发类型生成场景提示
    scene_hint = _build_scene_hint(trigger_payload)

    # 表情使用指引（从画像里翻译出来）
    emoji_habits = profile.get("emoji_habits", {}) or {}
    face_usage_hint = _build_face_usage_hint(profile, top_face_ids)
    face_usage_block = ""
    if face_usage_hint:
        face_usage_block = "9. 表情使用要求（必须遵守）:\n" + face_usage_hint + "\n"

    # 表情语义对照表
    face_glossary = _build_face_glossary(top_face_ids, emoji_habits, face_usage_stats)
    face_glossary_block = (
        "表情语义对照（你要根据语义选择，不能乱用 ID；括号里是该表情在目标全部历史表情使用中的占比）:\n"
        + "\n".join(face_glossary)
        if face_glossary
        else "表情语义对照: 暂无目标常用表情，可以不带表情。"
    )

    # 历史样本里的表情对 AI 来说是 [face:N] 形式，配上语义提示更直观
    top_faces_with_meaning = [render_face_id_with_hint(fid) for fid in top_face_ids]

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
        "关于表情的输出方式（重要）:\n"
        f"- 在 reply 文本中可以直接内联 QQ 表情，写法是 [face:数字ID]，比如{_LQ}笑死[face:178]{_RQ}。\n"
        f"- 表情可以放在句首、句中、句尾，也可以独占一条消息（用换行分隔即可）。\n"
        f"- 一条消息里可以出现多个表情，按目标的真实习惯来。\n"
        f"- face_id 字段仅作为旧版兼容，可以留空；推荐全部在 reply 里内联。\n"
        f"- 历史样本里的 [face:178/笑哭] 等写法是给你看的语义提示，你输出时只写 [face:178] 即可。\n\n"
        "约束:\n"
        f"1. {length_hint}。\n"
        "2. 风格要像熟人群聊随口接话，不要写成客服或公文。\n"
        "3. 不要输出任何图片素材、表情包或自定义贴纸相关内容，只能用 QQ 默认表情的 [face:数字] 形式。\n"
        f"4. 仔细看下面的{_LQ}历史原话风格参考{_RQ}，你的 reply 必须在语气、句式、标点、用词习惯上"
        "尽量接近这些真实发言的风格，但不要照抄内容。\n"
        "5. 特别注意画像中的 ending_habits 和 punctuation，"
        "句尾风格要和目标保持一致（比如目标从不加句号你也不要加）。\n"
        "6. 重点参考下面的「目标历史对话片段」，这些片段展示了目标在类似场景下怎么接话。\n"
        "   观察目标的接话节奏：他是一条消息说完，还是习惯连发好几条短消息。\n"
        "   如果片段中 target_replies 有多条，说明目标习惯连发，你的 reply 也应该用换行分成多条短句。\n"
        "   如果片段中有 reply_to，说明目标在回应某条具体消息，参考他回应的方式和语气。\n"
        "7. 选用表情时务必结合下方「表情语义对照」，挑情绪/场景匹配的 ID，绝不能随便填 ID。\n"
        "8. 不要把所有句子塞同一个表情，按目标真实的位置和频率习惯使用。\n"
        f"{face_usage_block}"
        f"{scene_hint}\n\n"
        f"目标身份信息:\n{json.dumps(target_identity, ensure_ascii=False, indent=2)}\n\n"
        f"当前触发信息:\n{json.dumps(trigger_payload, ensure_ascii=False, indent=2)}\n\n"
        f"最近群聊上下文:\n{json.dumps(recent_chat_messages, ensure_ascii=False, indent=2)}\n\n"
        f"人物画像:\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
        "历史原话风格参考（仅供模仿风格，不要照抄内容）:\n"
        f"{json.dumps(similar_messages, ensure_ascii=False, indent=2)}\n\n"
        f"目标历史对话片段（展示他在类似场景下怎么接话，重点参考）:\n"
        f"{json.dumps(conversation_snippets or [], ensure_ascii=False, indent=2)}\n\n"
        f"常用 QQ 表情（带语义）:\n{json.dumps(top_faces_with_meaning, ensure_ascii=False)}\n\n"
        f"{face_glossary_block}\n\n"
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
