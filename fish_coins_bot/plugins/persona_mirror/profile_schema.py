from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


PERSONALITY_TAG_RULES: dict[str, str] = {
    "认真负责": "接到任务后会主动确认边界和交付标准，没达到自己认可的完成度前不会轻易说做完了。",
    "差不多就行": "更在意先把事情跑通，遇到细枝末节会倾向于先放一放，优先交可用版本。",
    "甩锅高手": "遇到问题先讲外部条件和他人依赖，责任边界会说得很细，不会先把锅接到自己身上。",
    "背锅侠": "别人把问题推过来时通常先接住再处理，很少第一时间说这不归我，出事时会先道歉再解释。",
    "完美主义": "对关键细节会反复确认，宁可慢一点也要把质量做扎实，别人的方案里小问题也会指出来。",
    "拖延症": "收到任务后不一定马上开干，通常会拖到截止时间临近才集中推进，消息回复也容易延后。",
    "直接": "表达意见时很少绕弯子，赞成或反对都会正面说出来，不会铺太多客套话。",
    "绕弯子": "不想直接否定别人时会先铺垫背景或换个问法，避免把拒绝说得太硬。",
    "话少": "群里大多时候先看别人怎么说，只有被点名或确定有必要时才会开口。",
    "话多": "一旦进入熟悉话题会连续补充细节，解释时不怕多说，会主动把前因后果讲完整。",
    "爱发语音": "遇到一句话说不清的时候会更倾向于发语音，而不是耐心把长段文字打出来。",
    "只读不回": "看到消息后经常先放着，除非被追问或事情逼近，否则不会立刻回复。",
    "已读乱回": "回复不一定紧扣问题本身，常常先接自己在意的点，容易让人觉得答非所问。",
    "秒回强迫症": "看到消息会很快给反馈，即使暂时没结论也会先回一句表示自己已经看到了。",
    "果断": "信息够用时会很快拍板，不喜欢长时间悬而不决，倾向于先定方向再修细节。",
    "反复横跳": "观点容易随着讨论对象和新增信息改变，已经说过的话也可能很快换个说法。",
    "依赖上级": "遇到关键取舍时会优先看上级态度，没有明确背书时不太愿意自己拍板。",
    "强势推进": "认定方向后会直接压节奏，遇到阻力时也会继续推动，不太接受长期卡着不动。",
    "数据驱动": "讨论问题时会优先要数字和事实，没有证据的判断很难让你表态。",
    "全凭感觉": "做判断时更相信经验和直觉，哪怕证据不完整也敢先给一个方向。",
    "情绪稳定": "被催和被质疑时表面上仍能维持平稳语气，不太会在群里直接爆情绪。",
    "玻璃心": "外界否定很容易影响状态，被批评时会明显收紧表达，甚至回避继续讨论。",
    "容易激动": "一旦被戳到在意的问题，语气会明显变冲，回复速度和标点强度都会上来。",
    "冷漠疏离": "会保持明显距离感，回应只给必要信息，不主动延展情绪或照顾对方感受。",
    "表面和气": "即使心里不认同，表面话也会说得比较顺，不会轻易把场面弄僵。",
    "阴阳怪气": "不满时不会直接骂，而是通过反问、挖苦或看似客气的话把刺带出来。",
    "PUA 高手": "安排别人做难事时会包装成成长机会，先给一点肯定，再把压力和责任推过去。",
    "职场政治玩家": "涉及多方利益时不会急着站队，先观察风向，再选择最有利的位置表达态度。",
    "甩锅艺术家": "会提前把责任边界和时间线留痕，真出问题时能迅速把自己摘干净。",
    "向上管理专家": "对上汇报时很会包装亮点和节奏，关键节点会主动刷存在感，让上级先看到你的版本。",
    "爱讲大道理": "遇到具体问题时会先上升到方法论和原则，再回到执行层面。",
    "情绪勒索": "不想接的事情会强调自己的疲惫、委屈或压力，迫使对方先顾及你的状态。",
}

CULTURE_TAG_RULES: dict[str, str] = {
    "字节范": "开口前会先追问 context，没有背景就直接讨论方案会让你打断补充；评价事情时经常先问 impact 和对齐没有。",
    "阿里味": "说问题时喜欢先搭框架，口头里容易带上赋能、抓手、闭环、打法这类词。",
    "腾讯味": "没有数据支撑时不愿轻易下结论，倾向于先做保守判断，用户体验会被放在前面。",
    "华为味": "默认流程和规范不能少，汇报材料会比较讲究，执行时宁可慢一点也要走完整套流程。",
    "百度味": "技术判断会摆在很前面，跨层级和跨角色沟通比较谨慎，不会轻易把底牌全摊开。",
    "美团味": "看重执行结果和细节打磨，觉得事情既然要做就应该抠到位。",
    "第一性原理": "遇到问题会追问本质约束，不太接受别人都这么做的类比，会倾向于砍掉不必要的复杂度。",
    "OKR 狂热者": "讨论工作时会先问目标和可量化结果，不符合当前目标的事容易被你往后排。",
    "大厂流水线": "做事依赖既有 SOP 和证据链，超出流程边界时会先找模板、规范和留痕方式。",
    "创业公司派": "资源有限时会直接做取舍，流程不是第一位，能把事情顶起来更重要。",
}

PERSONALITY_TAGS = tuple(PERSONALITY_TAG_RULES.keys())
CULTURE_TAGS = tuple(CULTURE_TAG_RULES.keys())
ZODIAC_TAGS = (
    "白羊座",
    "金牛座",
    "双子座",
    "巨蟹座",
    "狮子座",
    "处女座",
    "天秤座",
    "天蝎座",
    "射手座",
    "摩羯座",
    "水瓶座",
    "双鱼座",
)
KNOWN_COMPANIES = (
    "字节跳动",
    "字节",
    "阿里巴巴",
    "阿里",
    "腾讯",
    "百度",
    "美团",
    "华为",
    "网易",
    "京东",
    "小米",
    "滴滴",
    "快手",
    "拼多多",
    "蚂蚁",
)
ROLE_HINTS = (
    "后端工程师",
    "前端工程师",
    "算法工程师",
    "测试工程师",
    "客户端工程师",
    "数据工程师",
    "研发工程师",
    "工程师",
    "产品经理",
    "项目经理",
    "技术经理",
    "架构师",
    "设计师",
    "运营",
    "研发",
    "Leader",
    "leader",
)
TAG_CONFLICT_GROUPS = (
    frozenset({"只读不回", "秒回强迫症"}),
    frozenset({"话少", "话多"}),
    frozenset({"直接", "绕弯子"}),
    frozenset({"果断", "反复横跳"}),
    frozenset({"认真负责", "差不多就行"}),
    frozenset({"背锅侠", "甩锅高手", "甩锅艺术家"}),
    frozenset({"数据驱动", "全凭感觉"}),
)

DEFAULT_MANUAL_PROFILE: dict[str, Any] = {
    "company": "",
    "level": "",
    "role": "",
    "gender": "",
    "mbti": "",
    "zodiac": "",
    "personality_tags": [],
    "culture_tags": [],
    "subjective_impression": "",
    "basic_info_text": "",
    "persona_tags_text": "",
}

DEFAULT_EXPRESSION_PROFILE: dict[str, Any] = {
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
    "blackwords": [],
    "formality": "",
    "supporting_evidence": [],
    "insufficient_fields": [],
    "sample_replies": {
        "basic_question": "",
        "progress_push": "",
        "bad_proposal": "",
        "group_at": "",
        "decision_challenge": "",
    },
}

DEFAULT_DECISIONS_LAYER: dict[str, Any] = {
    "priorities": [],
    "push_triggers": [],
    "avoid_triggers": [],
    "disagreement_style": "",
    "challenge_response": "",
    "uncertainty_style": "",
    "sample_phrases": [],
    "supporting_evidence": [],
    "insufficient_fields": [],
}

DEFAULT_INTERPERSONAL_LAYER: dict[str, Any] = {
    "towards_superiors": "",
    "towards_juniors": "",
    "towards_peers": "",
    "under_pressure": "",
    "typical_scenarios": [],
    "supporting_evidence": [],
    "insufficient_fields": [],
}

DEFAULT_BOUNDARIES_LAYER: dict[str, Any] = {
    "dislikes": [],
    "red_lines": [],
    "avoid_topics": [],
    "refusal_style": "",
    "supporting_evidence": [],
    "insufficient_fields": [],
}

DEFAULT_ANALYZER_DELTA: dict[str, Any] = {
    "summary": "",
    "expression": deepcopy(DEFAULT_EXPRESSION_PROFILE),
    "decisions": deepcopy(DEFAULT_DECISIONS_LAYER),
    "interpersonal": deepcopy(DEFAULT_INTERPERSONAL_LAYER),
    "boundaries": deepcopy(DEFAULT_BOUNDARIES_LAYER),
    "inferred_tags": [],
    "conflicts": [],
}

DEFAULT_V2_PROFILE: dict[str, Any] = {
    "version": 2,
    "manual_inputs": deepcopy(DEFAULT_MANUAL_PROFILE),
    "layers": {
        "core_rules": [],
        "identity": {
            "summary": "",
            "company": "",
            "level": "",
            "role": "",
            "gender": "",
            "mbti": "",
            "zodiac": "",
            "subjective_impression": "",
        },
        "expression": deepcopy(DEFAULT_EXPRESSION_PROFILE),
        "decisions": deepcopy(DEFAULT_DECISIONS_LAYER),
        "interpersonal": deepcopy(DEFAULT_INTERPERSONAL_LAYER),
        "boundaries": deepcopy(DEFAULT_BOUNDARIES_LAYER),
    },
    "compiled_reply_profile": {
        "core_rules": [],
        "identity": {},
        "expression": deepcopy(DEFAULT_EXPRESSION_PROFILE),
        "decisions": deepcopy(DEFAULT_DECISIONS_LAYER),
        "interpersonal": deepcopy(DEFAULT_INTERPERSONAL_LAYER),
        "boundaries": deepcopy(DEFAULT_BOUNDARIES_LAYER),
        "active_corrections": [],
        "hard_constraints": [],
    },
    "pending_conflicts": [],
}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        items = [_clean_text(item) for item in value]
    elif isinstance(value, str):
        items = re.split(r"[、,，；;/\n]", value)
        items = [_clean_text(item) for item in items]
    else:
        items = []
    deduped: list[str] = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _merge_text(old: str, new: str) -> str:
    new = _clean_text(new)
    old = _clean_text(old)
    return new or old


def _merge_distinct_text(old: str, new: str) -> str:
    new = _clean_text(new)
    old = _clean_text(old)
    if not new:
        return old
    if not old or old == new:
        return new
    if new in old:
        return old
    if old in new:
        return new
    return f"{old}；{new}"


def _merge_list(new_items: list[str], old_items: list[str], cap: int) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in new_items + old_items:
        if item and item not in seen:
            merged.append(item)
            seen.add(item)
    return merged[:cap]


def normalize_manual_profile(payload: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_MANUAL_PROFILE)
    if not isinstance(payload, dict):
        return merged
    merged["company"] = _clean_text(payload.get("company"))
    merged["level"] = _clean_text(payload.get("level"))
    merged["role"] = _clean_text(payload.get("role"))
    merged["gender"] = _clean_text(payload.get("gender"))
    merged["mbti"] = _clean_text(payload.get("mbti")).upper()
    merged["zodiac"] = _clean_text(payload.get("zodiac"))
    merged["personality_tags"] = _normalize_list(payload.get("personality_tags"))
    merged["culture_tags"] = _normalize_list(payload.get("culture_tags"))
    merged["subjective_impression"] = _clean_text(payload.get("subjective_impression"))
    merged["basic_info_text"] = _clean_text(payload.get("basic_info_text"))
    merged["persona_tags_text"] = _clean_text(payload.get("persona_tags_text"))
    return merged


def merge_manual_profile(
    current_profile: dict[str, Any] | None,
    updates: dict[str, Any] | None,
) -> dict[str, Any]:
    current = normalize_manual_profile(current_profile)
    incoming = normalize_manual_profile(updates)
    merged = deepcopy(current)
    for field in ("company", "level", "role", "gender", "mbti", "zodiac", "basic_info_text", "persona_tags_text"):
        merged[field] = _merge_text(current.get(field, ""), incoming.get(field, ""))
    merged["personality_tags"] = _merge_list(incoming["personality_tags"], current["personality_tags"], 20)
    merged["culture_tags"] = _merge_list(incoming["culture_tags"], current["culture_tags"], 20)
    merged["subjective_impression"] = _merge_distinct_text(
        current["subjective_impression"], incoming["subjective_impression"]
    )
    return merged


def parse_basic_info_text(text: str, current_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    current = normalize_manual_profile(current_profile)
    raw_text = _clean_text(text)
    if not raw_text:
        return current

    updates = deepcopy(DEFAULT_MANUAL_PROFILE)
    updates["basic_info_text"] = raw_text

    company = next((item for item in KNOWN_COMPANIES if item in raw_text), "")
    if company == "字节":
        company = "字节跳动"
    if company == "阿里":
        company = "阿里巴巴"
    updates["company"] = company

    level_match = re.search(r"\b(?:P\d{1,2}|T\d(?:-\d)?|\d-\d|\d{2}(?:-\d{2})?)\b", raw_text, re.I)
    if level_match:
        updates["level"] = level_match.group(0).upper()

    gender_match = re.search(r"(男|女)", raw_text)
    if gender_match:
        updates["gender"] = gender_match.group(1)

    role = ""
    for hint in ROLE_HINTS:
        if hint in raw_text:
            role = hint
            break
    if not role:
        stripped = raw_text
        for item in (company, updates["level"], updates["gender"]):
            if item:
                stripped = stripped.replace(item, " ")
        stripped = _clean_text(stripped)
        if stripped:
            role = stripped
    updates["role"] = role
    return merge_manual_profile(current, updates)


def parse_persona_tags_text(text: str, current_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    current = normalize_manual_profile(current_profile)
    raw_text = _clean_text(text)
    if not raw_text:
        return current

    updates = deepcopy(DEFAULT_MANUAL_PROFILE)
    updates["persona_tags_text"] = raw_text

    mbti_match = re.search(r"\b([IE][NS][TF][JP])\b", raw_text, re.I)
    if mbti_match:
        updates["mbti"] = mbti_match.group(1).upper()

    zodiac = next((item for item in ZODIAC_TAGS if item in raw_text), "")
    updates["zodiac"] = zodiac

    updates["personality_tags"] = [tag for tag in PERSONALITY_TAGS if tag in raw_text]
    updates["culture_tags"] = [tag for tag in CULTURE_TAGS if tag in raw_text]

    residue = raw_text
    for token in [updates["mbti"], updates["zodiac"], *updates["personality_tags"], *updates["culture_tags"]]:
        if token:
            residue = residue.replace(token, " ")
    residue = re.sub(r"[、,，；;]+", " ", residue)
    updates["subjective_impression"] = _clean_text(residue)
    return merge_manual_profile(current, updates)


def normalize_correction_record(payload: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(payload, dict):
        payload = {}
    return {
        "scene": _clean_text(payload.get("scene")) or "通用场景",
        "wrong": _clean_text(payload.get("wrong")) or "现有画像不够像本人",
        "correct": _clean_text(payload.get("correct")) or "按最新纠正执行",
    }


def normalize_correction_records(records: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for record in records or []:
        item = normalize_correction_record(record)
        dedupe_key = (item["scene"], item["correct"])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(item)
    return normalized


def parse_correction_text(text: str) -> dict[str, str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return normalize_correction_record({})

    pattern = re.compile(
        r"^(?P<scene>.*?)(?:他|她|目标)?(?:不会|不太会|不是|不应该)(?P<wrong>.*?)(?:，|,|而是|应该|其实会|其实是|会更像|会先|他会|她会)(?P<correct>.*)$"
    )
    match = pattern.match(cleaned)
    if match:
        scene = _clean_text(match.group("scene")) or "通用场景"
        wrong = _clean_text(match.group("wrong"))
        correct = _clean_text(match.group("correct"))
        return normalize_correction_record(
            {
                "scene": scene,
                "wrong": wrong,
                "correct": correct,
            }
        )

    corrected = cleaned
    for prefix in ("他其实", "她其实", "他应该", "她应该", "其实", "应该"):
        if corrected.startswith(prefix):
            corrected = corrected[len(prefix) :]
            break

    return normalize_correction_record(
        {
            "scene": "通用场景",
            "wrong": "现有画像不够像本人",
            "correct": corrected or cleaned,
        }
    )


def normalize_expression_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_EXPRESSION_PROFILE)
    if not isinstance(profile, dict):
        return merged
    sentence_style = profile.get("sentence_style", {})
    emoji_habits = profile.get("emoji_habits", {})
    sample_replies = profile.get("sample_replies", {})
    merged["tone"] = _normalize_list(profile.get("tone"))
    merged["sentence_style"] = {
        "avg_length": _clean_text(sentence_style.get("avg_length")),
        "typical_length_range": _clean_text(sentence_style.get("typical_length_range")),
        "structure": _clean_text(sentence_style.get("structure")),
        "punctuation": _normalize_list(sentence_style.get("punctuation")),
        "rhythm": _clean_text(sentence_style.get("rhythm")),
        "ending_habits": _normalize_list(sentence_style.get("ending_habits")),
    }
    merged["catchphrases"] = _normalize_list(profile.get("catchphrases"))
    merged["habit_words"] = _normalize_list(profile.get("habit_words"))
    merged["emoji_habits"] = {
        "qq_faces": _normalize_list(emoji_habits.get("qq_faces")),
    }
    merged["response_patterns"] = _normalize_list(profile.get("response_patterns"))
    merged["topic_tendencies"] = _normalize_list(profile.get("topic_tendencies"))
    merged["greeting_farewell"] = _clean_text(profile.get("greeting_farewell"))
    merged["situational_patterns"] = _normalize_list(profile.get("situational_patterns"))
    merged["negative_rules"] = _normalize_list(profile.get("negative_rules"))
    merged["reply_constraints"] = _normalize_list(profile.get("reply_constraints"))
    merged["blackwords"] = _normalize_list(profile.get("blackwords"))
    merged["formality"] = _clean_text(profile.get("formality"))
    merged["supporting_evidence"] = _normalize_list(profile.get("supporting_evidence"))
    merged["insufficient_fields"] = _normalize_list(profile.get("insufficient_fields"))
    merged["sample_replies"] = {
        "basic_question": _clean_text(sample_replies.get("basic_question")),
        "progress_push": _clean_text(sample_replies.get("progress_push")),
        "bad_proposal": _clean_text(sample_replies.get("bad_proposal")),
        "group_at": _clean_text(sample_replies.get("group_at")),
        "decision_challenge": _clean_text(sample_replies.get("decision_challenge")),
    }
    return merged


def normalize_decisions_layer(payload: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_DECISIONS_LAYER)
    if not isinstance(payload, dict):
        return merged
    merged["priorities"] = _normalize_list(payload.get("priorities"))
    merged["push_triggers"] = _normalize_list(payload.get("push_triggers"))
    merged["avoid_triggers"] = _normalize_list(payload.get("avoid_triggers"))
    merged["disagreement_style"] = _clean_text(payload.get("disagreement_style"))
    merged["challenge_response"] = _clean_text(payload.get("challenge_response"))
    merged["uncertainty_style"] = _clean_text(payload.get("uncertainty_style"))
    merged["sample_phrases"] = _normalize_list(payload.get("sample_phrases"))
    merged["supporting_evidence"] = _normalize_list(payload.get("supporting_evidence"))
    merged["insufficient_fields"] = _normalize_list(payload.get("insufficient_fields"))
    return merged


def normalize_interpersonal_layer(payload: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_INTERPERSONAL_LAYER)
    if not isinstance(payload, dict):
        return merged
    merged["towards_superiors"] = _clean_text(payload.get("towards_superiors"))
    merged["towards_juniors"] = _clean_text(payload.get("towards_juniors"))
    merged["towards_peers"] = _clean_text(payload.get("towards_peers"))
    merged["under_pressure"] = _clean_text(payload.get("under_pressure"))
    merged["typical_scenarios"] = _normalize_list(payload.get("typical_scenarios"))
    merged["supporting_evidence"] = _normalize_list(payload.get("supporting_evidence"))
    merged["insufficient_fields"] = _normalize_list(payload.get("insufficient_fields"))
    return merged


def normalize_boundaries_layer(payload: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_BOUNDARIES_LAYER)
    if not isinstance(payload, dict):
        return merged
    merged["dislikes"] = _normalize_list(payload.get("dislikes"))
    merged["red_lines"] = _normalize_list(payload.get("red_lines"))
    merged["avoid_topics"] = _normalize_list(payload.get("avoid_topics"))
    merged["refusal_style"] = _clean_text(payload.get("refusal_style"))
    merged["supporting_evidence"] = _normalize_list(payload.get("supporting_evidence"))
    merged["insufficient_fields"] = _normalize_list(payload.get("insufficient_fields"))
    return merged


def normalize_pending_conflicts(payload: Any) -> list[dict[str, str]]:
    items = payload if isinstance(payload, list) else []
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        if isinstance(item, dict):
            field = _clean_text(item.get("field"))
            manual_value = _clean_text(item.get("manual"))
            inferred_value = _clean_text(item.get("inferred"))
            reason = _clean_text(item.get("reason"))
        else:
            field = ""
            manual_value = ""
            inferred_value = ""
            reason = _clean_text(item)
        dedupe_key = (field, manual_value, inferred_value or reason)
        if not any(dedupe_key) or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(
            {
                "field": field or "persona",
                "manual": manual_value,
                "inferred": inferred_value,
                "reason": reason or "手工输入与模型推断存在冲突",
            }
        )
    return normalized


def normalize_analyzer_delta(payload: dict[str, Any] | None) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_ANALYZER_DELTA)
    if not isinstance(payload, dict):
        return merged
    merged["summary"] = _clean_text(payload.get("summary"))
    merged["expression"] = normalize_expression_profile(payload.get("expression"))
    merged["decisions"] = normalize_decisions_layer(payload.get("decisions"))
    merged["interpersonal"] = normalize_interpersonal_layer(payload.get("interpersonal"))
    merged["boundaries"] = normalize_boundaries_layer(payload.get("boundaries"))
    merged["inferred_tags"] = _normalize_list(payload.get("inferred_tags"))
    merged["conflicts"] = normalize_pending_conflicts(payload.get("conflicts"))
    return merged


def _merge_expression_layers(old_layer: dict[str, Any], new_layer: dict[str, Any]) -> dict[str, Any]:
    old_data = normalize_expression_profile(old_layer)
    new_data = normalize_expression_profile(new_layer)
    merged = deepcopy(new_data)
    merged["tone"] = _merge_list(new_data["tone"], old_data["tone"], 12)
    merged["catchphrases"] = _merge_list(new_data["catchphrases"], old_data["catchphrases"], 20)
    merged["habit_words"] = _merge_list(new_data["habit_words"], old_data["habit_words"], 24)
    merged["response_patterns"] = _merge_list(new_data["response_patterns"], old_data["response_patterns"], 16)
    merged["topic_tendencies"] = _merge_list(new_data["topic_tendencies"], old_data["topic_tendencies"], 16)
    merged["situational_patterns"] = _merge_list(new_data["situational_patterns"], old_data["situational_patterns"], 16)
    merged["negative_rules"] = _merge_list(new_data["negative_rules"], old_data["negative_rules"], 16)
    merged["reply_constraints"] = _merge_list(new_data["reply_constraints"], old_data["reply_constraints"], 16)
    merged["blackwords"] = _merge_list(new_data["blackwords"], old_data["blackwords"], 12)
    merged["supporting_evidence"] = _merge_list(new_data["supporting_evidence"], old_data["supporting_evidence"], 20)
    merged["insufficient_fields"] = _merge_list(new_data["insufficient_fields"], old_data["insufficient_fields"], 16)
    merged["greeting_farewell"] = _merge_text(old_data["greeting_farewell"], new_data["greeting_farewell"])
    merged["formality"] = _merge_text(old_data["formality"], new_data["formality"])
    merged["sentence_style"] = {
        "avg_length": _merge_text(old_data["sentence_style"]["avg_length"], new_data["sentence_style"]["avg_length"]),
        "typical_length_range": _merge_text(
            old_data["sentence_style"]["typical_length_range"],
            new_data["sentence_style"]["typical_length_range"],
        ),
        "structure": _merge_text(old_data["sentence_style"]["structure"], new_data["sentence_style"]["structure"]),
        "punctuation": _merge_list(
            new_data["sentence_style"]["punctuation"],
            old_data["sentence_style"]["punctuation"],
            12,
        ),
        "rhythm": _merge_text(old_data["sentence_style"]["rhythm"], new_data["sentence_style"]["rhythm"]),
        "ending_habits": _merge_list(
            new_data["sentence_style"]["ending_habits"],
            old_data["sentence_style"]["ending_habits"],
            12,
        ),
    }
    merged["emoji_habits"] = {
        "qq_faces": _merge_list(new_data["emoji_habits"]["qq_faces"], old_data["emoji_habits"]["qq_faces"], 10)
    }
    merged["sample_replies"] = {
        key: _merge_text(old_data["sample_replies"][key], new_data["sample_replies"][key])
        for key in old_data["sample_replies"]
    }
    return merged


def _merge_simple_layer(old_layer: dict[str, Any], new_layer: dict[str, Any], default_layer: dict[str, Any]) -> dict[str, Any]:
    old_data = deepcopy(default_layer)
    old_data.update(old_layer or {})
    new_data = deepcopy(default_layer)
    new_data.update(new_layer or {})
    merged = deepcopy(default_layer)
    for key, value in default_layer.items():
        if isinstance(value, list):
            merged[key] = _merge_list(_normalize_list(new_data.get(key)), _normalize_list(old_data.get(key)), 20)
        else:
            merged[key] = _merge_text(_clean_text(old_data.get(key)), _clean_text(new_data.get(key)))
    return merged


def build_core_rules(manual_inputs: dict[str, Any], corrections: list[dict[str, Any]] | None = None) -> list[str]:
    manual = normalize_manual_profile(manual_inputs)
    rules: list[str] = []
    for tag in manual["personality_tags"]:
        rule = PERSONALITY_TAG_RULES.get(tag)
        if rule and rule not in rules:
            rules.append(rule)
    for tag in manual["culture_tags"]:
        rule = CULTURE_TAG_RULES.get(tag)
        if rule and rule not in rules:
            rules.append(rule)
    for correction in normalize_correction_records(corrections):
        rule = f"在{correction['scene']}时，不要{correction['wrong']}；更像本人的做法是{correction['correct']}。"
        if rule not in rules:
            rules.append(rule)
    return rules[:24]


def build_identity_layer(manual_inputs: dict[str, Any]) -> dict[str, Any]:
    manual = normalize_manual_profile(manual_inputs)
    summary_parts = []
    company_role = " ".join(item for item in [manual["company"], manual["level"], manual["role"]] if item)
    if company_role:
        summary_parts.append(company_role)
    if manual["gender"]:
        summary_parts.append(manual["gender"])
    if manual["mbti"]:
        summary_parts.append(f"MBTI {manual['mbti']}")
    if manual["zodiac"]:
        summary_parts.append(manual["zodiac"])
    if manual["subjective_impression"]:
        summary_parts.append(f"印象：{manual['subjective_impression']}")

    return {
        "summary": "；".join(summary_parts),
        "company": manual["company"],
        "level": manual["level"],
        "role": manual["role"],
        "gender": manual["gender"],
        "mbti": manual["mbti"],
        "zodiac": manual["zodiac"],
        "subjective_impression": manual["subjective_impression"],
    }


def _detect_tag_conflicts(manual_inputs: dict[str, Any], inferred_tags: list[str]) -> list[dict[str, str]]:
    manual_tags = set(normalize_manual_profile(manual_inputs)["personality_tags"])
    inferred = set(_normalize_list(inferred_tags))
    conflicts: list[dict[str, str]] = []
    for group in TAG_CONFLICT_GROUPS:
        manual_hit = group & manual_tags
        inferred_hit = group & inferred
        if not manual_hit or not inferred_hit:
            continue
        if manual_hit == inferred_hit:
            continue
        conflicts.append(
            {
                "field": "personality_tags",
                "manual": "、".join(sorted(manual_hit)),
                "inferred": "、".join(sorted(inferred_hit)),
                "reason": "手工标签与样本推断落在同一冲突标签组，已保留手工标签优先。",
            }
        )
    return conflicts


def build_compiled_reply_profile(
    v2_profile: dict[str, Any],
    corrections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized = normalize_v2_profile(v2_profile, corrections=corrections)
    layers = normalized["layers"]
    active_corrections = normalize_correction_records(corrections)
    hard_constraints = _merge_list(
        layers["core_rules"] + layers["expression"]["reply_constraints"],
        [
            f"如果场景是{item['scene']}，不要{item['wrong']}，应该{item['correct']}"
            for item in active_corrections
        ],
        32,
    )
    return {
        "core_rules": layers["core_rules"],
        "identity": deepcopy(layers["identity"]),
        "expression": deepcopy(layers["expression"]),
        "decisions": deepcopy(layers["decisions"]),
        "interpersonal": deepcopy(layers["interpersonal"]),
        "boundaries": deepcopy(layers["boundaries"]),
        "active_corrections": active_corrections,
        "hard_constraints": hard_constraints,
    }


def is_v2_profile(payload: dict[str, Any] | None) -> bool:
    return isinstance(payload, dict) and int(payload.get("version", 0) or 0) >= 2 and "layers" in payload


def migrate_legacy_profile(
    legacy_profile: dict[str, Any] | None,
    manual_inputs: dict[str, Any] | None = None,
    corrections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    migrated = deepcopy(DEFAULT_V2_PROFILE)
    migrated["manual_inputs"] = normalize_manual_profile(manual_inputs)
    migrated["layers"]["identity"] = build_identity_layer(migrated["manual_inputs"])
    migrated["layers"]["expression"] = normalize_expression_profile(legacy_profile)
    migrated["layers"]["core_rules"] = build_core_rules(migrated["manual_inputs"], corrections)
    migrated["compiled_reply_profile"] = build_compiled_reply_profile(migrated, corrections)
    return migrated


def normalize_v2_profile(
    payload: dict[str, Any] | None,
    manual_inputs: dict[str, Any] | None = None,
    corrections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not is_v2_profile(payload):
        return migrate_legacy_profile(payload, manual_inputs=manual_inputs, corrections=corrections)

    merged = deepcopy(DEFAULT_V2_PROFILE)
    source = payload or {}
    normalized_manual = merge_manual_profile(source.get("manual_inputs"), manual_inputs)
    merged["manual_inputs"] = normalized_manual

    layers = source.get("layers") if isinstance(source.get("layers"), dict) else {}
    merged["layers"]["core_rules"] = build_core_rules(normalized_manual, corrections)
    merged["layers"]["identity"] = build_identity_layer(normalized_manual)
    merged["layers"]["expression"] = normalize_expression_profile(layers.get("expression"))
    merged["layers"]["decisions"] = normalize_decisions_layer(layers.get("decisions"))
    merged["layers"]["interpersonal"] = normalize_interpersonal_layer(layers.get("interpersonal"))
    merged["layers"]["boundaries"] = normalize_boundaries_layer(layers.get("boundaries"))
    merged["pending_conflicts"] = normalize_pending_conflicts(source.get("pending_conflicts"))
    merged["compiled_reply_profile"] = build_compiled_reply_profile_raw(merged, corrections)
    return merged


def build_compiled_reply_profile_raw(
    normalized_profile: dict[str, Any],
    corrections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    layers = normalized_profile["layers"]
    active_corrections = normalize_correction_records(corrections)
    hard_constraints = _merge_list(
        [
            *layers["core_rules"],
            *layers["expression"]["reply_constraints"],
            *layers["expression"]["negative_rules"],
        ],
        [
            f"如果场景是{item['scene']}，不要{item['wrong']}，应该{item['correct']}"
            for item in active_corrections
        ],
        36,
    )
    return {
        "core_rules": deepcopy(layers["core_rules"]),
        "identity": deepcopy(layers["identity"]),
        "expression": deepcopy(layers["expression"]),
        "decisions": deepcopy(layers["decisions"]),
        "interpersonal": deepcopy(layers["interpersonal"]),
        "boundaries": deepcopy(layers["boundaries"]),
        "active_corrections": active_corrections,
        "hard_constraints": hard_constraints,
    }


def compose_v2_profile(
    current_profile: dict[str, Any] | None,
    analyzer_delta: dict[str, Any] | None = None,
    builder_profile: dict[str, Any] | None = None,
    manual_inputs: dict[str, Any] | None = None,
    corrections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    current = normalize_v2_profile(current_profile, manual_inputs=manual_inputs, corrections=corrections)
    builder = normalize_v2_profile(builder_profile, manual_inputs=manual_inputs, corrections=corrections)
    delta = normalize_analyzer_delta(analyzer_delta)

    merged = deepcopy(DEFAULT_V2_PROFILE)
    merged["manual_inputs"] = merge_manual_profile(current["manual_inputs"], manual_inputs)
    merged["layers"]["core_rules"] = build_core_rules(merged["manual_inputs"], corrections)
    merged["layers"]["identity"] = build_identity_layer(merged["manual_inputs"])
    merged["layers"]["expression"] = _merge_expression_layers(
        current["layers"]["expression"],
        builder["layers"]["expression"] or delta["expression"],
    )
    if builder["layers"]["expression"] == normalize_expression_profile(None):
        merged["layers"]["expression"] = _merge_expression_layers(current["layers"]["expression"], delta["expression"])

    merged["layers"]["decisions"] = _merge_simple_layer(
        current["layers"]["decisions"],
        builder["layers"]["decisions"] or delta["decisions"],
        DEFAULT_DECISIONS_LAYER,
    )
    if builder["layers"]["decisions"] == normalize_decisions_layer(None):
        merged["layers"]["decisions"] = _merge_simple_layer(
            current["layers"]["decisions"], delta["decisions"], DEFAULT_DECISIONS_LAYER
        )

    merged["layers"]["interpersonal"] = _merge_simple_layer(
        current["layers"]["interpersonal"],
        builder["layers"]["interpersonal"] or delta["interpersonal"],
        DEFAULT_INTERPERSONAL_LAYER,
    )
    if builder["layers"]["interpersonal"] == normalize_interpersonal_layer(None):
        merged["layers"]["interpersonal"] = _merge_simple_layer(
            current["layers"]["interpersonal"], delta["interpersonal"], DEFAULT_INTERPERSONAL_LAYER
        )

    merged["layers"]["boundaries"] = _merge_simple_layer(
        current["layers"]["boundaries"],
        builder["layers"]["boundaries"] or delta["boundaries"],
        DEFAULT_BOUNDARIES_LAYER,
    )
    if builder["layers"]["boundaries"] == normalize_boundaries_layer(None):
        merged["layers"]["boundaries"] = _merge_simple_layer(
            current["layers"]["boundaries"], delta["boundaries"], DEFAULT_BOUNDARIES_LAYER
        )

    pending_conflicts = (
        current.get("pending_conflicts", [])
        + delta.get("conflicts", [])
        + builder.get("pending_conflicts", [])
        + _detect_tag_conflicts(merged["manual_inputs"], delta.get("inferred_tags", []))
    )
    merged["pending_conflicts"] = normalize_pending_conflicts(pending_conflicts)
    merged["compiled_reply_profile"] = build_compiled_reply_profile_raw(merged, corrections)
    return merged


def rebuild_profile_with_overrides(
    current_profile: dict[str, Any] | None,
    manual_inputs: dict[str, Any] | None = None,
    corrections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized = normalize_v2_profile(current_profile, manual_inputs=manual_inputs, corrections=corrections)
    normalized["layers"]["core_rules"] = build_core_rules(normalized["manual_inputs"], corrections)
    normalized["layers"]["identity"] = build_identity_layer(normalized["manual_inputs"])
    normalized["compiled_reply_profile"] = build_compiled_reply_profile_raw(normalized, corrections)
    return normalized
