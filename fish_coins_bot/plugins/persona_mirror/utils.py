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

# QQ 表情 ID 到语义的映射。给 AI 看的时候配上语义，它才知道这个 ID 长什么样、什么场景该用。
# 只收录最常见的几十~百多个 ID，覆盖不了的会直接显示 ID。
FACE_MEANINGS: dict[str, str] = {
    "0": "惊讶", "1": "撇嘴", "2": "色", "3": "发呆", "4": "得意",
    "5": "流泪", "6": "害羞", "7": "闭嘴", "8": "睡", "9": "大哭",
    "10": "尴尬", "11": "发怒", "12": "调皮", "13": "呲牙", "14": "微笑",
    "15": "难过", "16": "酷", "18": "抓狂", "19": "吐", "20": "偷笑",
    "21": "可爱", "22": "白眼", "23": "傲慢", "24": "饿", "25": "困",
    "26": "惊恐", "27": "流汗", "28": "憨笑", "29": "悠闲", "30": "奋斗",
    "32": "疑问", "33": "嘘", "34": "晕", "36": "衰", "37": "骷髅",
    "38": "敲打", "39": "再见", "41": "发抖", "42": "爱情", "46": "猪头",
    "49": "拥抱", "53": "蛋糕", "60": "咖啡", "63": "玫瑰", "66": "爱心",
    "67": "心碎", "74": "太阳", "75": "月亮", "76": "赞", "77": "踩",
    "78": "握手", "79": "胜利", "80": "委屈", "81": "快哭了", "85": "飞吻",
    "89": "西瓜", "96": "冷汗", "97": "擦汗", "98": "抠鼻", "99": "鼓掌",
    "100": "糗大了", "101": "坏笑", "104": "哈欠", "105": "鄙视", "106": "委屈",
    "108": "阴险", "109": "亲亲", "110": "吓", "111": "可怜", "116": "示爱",
    "118": "抱拳", "120": "拳头", "144": "喝彩", "172": "抛媚眼", "173": "泪奔",
    "174": "无奈", "175": "卖萌", "176": "小纠结", "177": "喷血", "178": "斜眼笑",
    "179": "doge", "180": "惊喜", "181": "骚扰", "182": "笑哭", "183": "我最美",
    "187": "幽灵", "192": "红包", "193": "大笑", "194": "不开心", "197": "冷漠",
    "198": "呃", "199": "好棒", "200": "拜托", "201": "点赞", "202": "无聊",
    "203": "托脸", "204": "吃", "205": "送花", "206": "害怕", "207": "花痴",
    "208": "小样儿", "210": "飙泪", "211": "我不看", "212": "托腮", "214": "啵啵",
    "215": "糊脸", "216": "拍头", "217": "扯一扯", "218": "舔一舔", "219": "蹭一蹭",
    "222": "抱抱", "223": "暴击", "226": "拍桌", "227": "拍手", "228": "恭喜",
    "229": "干杯", "230": "嘲讽", "231": "哼", "232": "佛系", "233": "掐一掐",
    "234": "惊呆", "235": "颤抖", "236": "啃头", "237": "偷看", "238": "扇脸",
    "239": "原谅", "240": "喷脸", "243": "甩头", "244": "扔狗", "260": "搬砖中",
    "261": "忙到飞起", "262": "脑阔疼", "263": "沧桑", "264": "捂脸", "265": "辣眼睛",
    "266": "哎呦", "267": "小本本", "268": "怀疑", "269": "吃瓜", "270": "渣男",
    "271": "哪吒", "273": "我酸了", "274": "太南了", "277": "汪汪", "278": "汗",
    "279": "打脸", "280": "击掌", "281": "无眼笑", "282": "敬礼", "283": "狂笑",
    "284": "面无表情", "285": "摸鱼", "286": "魔鬼笑", "287": "哦哟", "288": "请",
    "289": "睁眼", "290": "敲开心", "291": "震惊", "292": "让我康康", "293": "摸鱼",
    "294": "永远爱你", "295": "拒绝", "297": "蛇打滚", "298": "树懒", "299": "胜利",
    "300": "拳头", "301": "好的", "302": "草", "303": "加油", "304": "崩溃",
    "305": "脱单", "306": "天啊", "307": "EMO", "308": "我裂开了", "309": "炸药",
    "310": "睡觉", "311": "打call", "312": "变形", "313": "嗑到了", "314": "仔细分析",
    "315": "加油", "316": "我没事", "317": "菜狗", "318": "崇拜", "319": "比心",
    "320": "庆祝", "321": "老色批", "322": "拒绝", "323": "嫌弃", "344": "大怨种",
}


def render_face_id_with_hint(face_id: str | int) -> str:
    """把 face_id 渲染成 [face:178/笑哭] 这种带语义的形式，喂给 AI 时用。"""
    fid = str(face_id).strip()
    if not fid:
        return ""
    meaning = FACE_MEANINGS.get(fid, "")
    if meaning:
        return f"[face:{fid}/{meaning}]"
    return f"[face:{fid}]"


# 同时兼容 [face:178] 和 [face:178/笑哭] 两种写法，只取数字 ID
_INLINE_FACE_PATTERN = re.compile(r"\[face[:：]\s*(\d+)\s*(?:/[^\]]*)?\]", re.IGNORECASE)


def parse_inline_face_text(text: str) -> list[dict[str, Any]]:
    """把 AI 输出的 reply 文本拆成 [{"type": "text"/"face", ...}] 段。

    输出的段已经做过 strip 兼容，调用方可直接拼装成 nonebot Message。
    """
    if not text:
        return []

    segments: list[dict[str, Any]] = []
    pos = 0
    for match in _INLINE_FACE_PATTERN.finditer(text):
        start, end = match.span()
        if start > pos:
            piece = text[pos:start]
            if piece:
                segments.append({"type": "text", "value": piece})
        segments.append({"type": "face", "id": match.group(1)})
        pos = end
    if pos < len(text):
        tail = text[pos:]
        if tail:
            segments.append({"type": "text", "value": tail})
    return segments


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


def render_segments_for_ai(raw_segments: list[dict[str, Any]]) -> str:
    """渲染消息给 AI 看：face 段附带语义提示，让 AI 知道每个 ID 是什么表情。"""
    rendered: list[str] = []
    for segment in raw_segments:
        segment_type = segment.get("type")
        data = segment.get("data", {})
        if segment_type == "text":
            rendered.append(str(data.get("text", "")))
        elif segment_type == "face":
            rendered.append(render_face_id_with_hint(data.get("id", "")))
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


def _detect_face_positions(raw_segments: list[dict[str, Any]]) -> tuple[list[str], bool]:
    """分析 face 段在消息中的位置（head / middle / tail / standalone）。

    返回 (positions, is_standalone)，is_standalone 表示整条消息只有 face，没有文本内容。
    """
    meaningful_indices: list[int] = []
    face_indices: list[int] = []
    for index, segment in enumerate(raw_segments):
        seg_type = segment.get("type")
        if seg_type == "text":
            text = str(segment.get("data", {}).get("text", "")).strip()
            if text:
                meaningful_indices.append(index)
        elif seg_type == "face":
            meaningful_indices.append(index)
            face_indices.append(index)

    if not face_indices:
        return [], False

    if len(meaningful_indices) == len(face_indices):
        # 全是 face，没有文本
        return ["standalone"] * len(face_indices), True

    first = meaningful_indices[0]
    last = meaningful_indices[-1]
    positions: list[str] = []
    for idx in face_indices:
        if idx == first:
            positions.append("head")
        elif idx == last:
            positions.append("tail")
        else:
            positions.append("middle")
    return positions, False


def build_feature_json(
    raw_segments: list[dict[str, Any]],
    plain_text: str,
) -> dict[str, Any]:
    face_ids = [
        str(segment.get("data", {}).get("id", ""))
        for segment in raw_segments
        if segment.get("type") == "face" and segment.get("data", {}).get("id") is not None
    ]
    face_positions, is_standalone_face = _detect_face_positions(raw_segments)
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
        "face_count": len(face_ids),
        "face_positions": face_positions,
        "is_standalone_face": is_standalone_face,
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
