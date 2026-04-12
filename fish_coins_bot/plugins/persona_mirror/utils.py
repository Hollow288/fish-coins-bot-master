import json
import re
from collections import Counter
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import jieba

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

# 语气词：用于统计特征，不作为口头禅候选
MODAL_WORDS = ["啊", "吧", "呗", "哈", "啦", "了", "嘛", "吗", "呢", "呀", "哇", "诶", "欸"]

# 通用网络热词（仅作为初始种子辅助统计，不代表个人特征）
SEED_PHRASES = [
    "笑死", "绷不住", "不是哥们", "等会", "离谱", "抽象",
    "逆天", "又来这套", "先看一眼", "无语", "可以的", "好家伙",
]

# jieba 分词时要忽略的停用词
_STOP_WORDS = frozenset({
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
    "那", "它", "把", "被", "从", "对", "让", "之", "而", "但",
})


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def datetime_from_timestamp(timestamp: int | float | None) -> datetime:
    if timestamp is None:
        return now_shanghai()
    return datetime.fromtimestamp(float(timestamp), tz=SHANGHAI_TZ)


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def message_segments_to_list(message: Any) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for segment in message:
        segments.append(
            {
                "type": segment.type,
                "data": dict(segment.data),
            }
        )
    return segments


def render_segments_as_text(raw_segments: list[dict[str, Any]]) -> str:
    rendered: list[str] = []
    for segment in raw_segments:
        segment_type = segment.get("type")
        data = segment.get("data", {})
        if segment_type == "text":
            rendered.append(str(data.get("text", "")))
        elif segment_type == "face":
            rendered.append(f"[face:{data.get('id', '')}]")
        elif segment_type == "image":
            rendered.append("[image]")
        elif segment_type == "at":
            rendered.append(f"@{data.get('qq', '')}")
        else:
            rendered.append(f"[{segment_type}]")
    return "".join(rendered).strip()


def _tokenize(text: str) -> list[str]:
    """用 jieba 分词并过滤停用词和单字符。"""
    if not text:
        return []
    words = jieba.lcut(text)
    return [w for w in words if len(w) > 1 and w not in _STOP_WORDS]


def similarity_score(query: str, candidate: str) -> float:
    """基于分词的 Jaccard + 包含奖励，适合中文短文本。"""
    if not query or not candidate:
        return 0.0

    q_words = set(_tokenize(query))
    c_words = set(_tokenize(candidate))

    if not q_words or not c_words:
        # 分词结果为空时回退到字符级
        q_chars = set(query)
        c_chars = set(candidate)
        if not q_chars or not c_chars:
            return 0.0
        return len(q_chars & c_chars) / len(q_chars | c_chars)

    intersection = len(q_words & c_words)
    union = len(q_words | c_words)
    jaccard = intersection / union
    containment_bonus = 0.15 if query in candidate or candidate in query else 0.0
    return jaccard + containment_bonus


def extract_ngrams(text: str, n: int = 2) -> list[str]:
    """从文本中提取 n-gram 词组。"""
    words = _tokenize(text)
    if len(words) < n:
        return words
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


def build_feature_json(
    raw_segments: list[dict[str, Any]],
    plain_text: str,
) -> dict[str, Any]:
    face_ids = [
        str(segment.get("data", {}).get("id", ""))
        for segment in raw_segments
        if segment.get("type") == "face" and segment.get("data", {}).get("id") is not None
    ]
    modal_hits = [token for token in MODAL_WORDS if token in plain_text]
    seed_hits = [token for token in SEED_PHRASES if token in plain_text]

    # 用分词提取目标自己的高频词组
    bigrams = extract_ngrams(plain_text, 2)
    content_words = _tokenize(plain_text)

    punctuation_counter = Counter(char for char in plain_text if char in "，。！？!?~…,.")

    # 句尾特征（最后一个字符）
    stripped = plain_text.rstrip()
    ending_char = stripped[-1] if stripped else ""

    feature: dict[str, Any] = {
        "text_length": len(plain_text),
        "face_ids": face_ids,
        "has_question": any(mark in plain_text for mark in {"?", "？"}),
        "has_exclamation": any(mark in plain_text for mark in {"!", "！"}),
        "has_comma": any(mark in plain_text for mark in {",", "，"}),
        "modal_words": modal_hits,
        "seed_phrase_hits": seed_hits,
        "content_words": content_words[:20],
        "bigrams": bigrams[:10],
        "ending_char": ending_char,
        "punctuation": dict(punctuation_counter),
    }

    return feature


def safe_json_loads(raw_text: str | None) -> dict[str, Any] | None:
    if not raw_text:
        return None

    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.S)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def top_items(counter: Counter[str], limit: int) -> list[str]:
    return [item for item, _count in counter.most_common(limit)]


def safe_reply_sender_name(reply) -> str:
    if not reply or not getattr(reply, "sender", None):
        return ""
    sender = reply.sender
    return getattr(sender, "card", "") or getattr(sender, "nickname", "") or str(getattr(sender, "user_id", ""))
