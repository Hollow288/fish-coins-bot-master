# persona_mirror

`persona_mirror` 是一个 NoneBot2 插件，用来持续采集某个目标 QQ 的发言，生成"说话画像"，并在群聊触发时用他的语气直接发一条消息。

简单来说就是：长期"偷学"一个人的聊天风格，然后在群里代替他说话。

## 1. 完整链路总览

```
绑定目标 → 采集消息 → 总结画像 → 触发模仿回复
```

四个阶段的详细说明见下文。

---

## 2. 阶段一：消息采集

### 2.1 触发条件

`collector.py` 注册了一个 `priority=1, block=False` 的全局消息监听器，每条群聊/私聊消息都会经过。只有当发送者的 QQ 号在 `persona_target` 表中存在且 `enabled=True` 时，才会真正采集。

### 2.2 采集内容

由 `collector_service.py` 的 `collect_message_event` 完成，对每条目标消息记录以下信息：

| 采集项 | 来源 | 存储字段 |
|--------|------|----------|
| 消息纯文本 | `event.get_plaintext()` | `plain_text` |
| 归一化文本 | 去除多余空白 | `normalized_text` |
| 原始消息分段 | 包含 text、face、image、at 等 | `raw_segments_json` |
| 局部统计特征 | jieba 分词 + 正则提取 | `feature_json` |
| 发言前群聊上下文 | 内存缓存的最近 5 条群消息 | `context_json` |
| 场景分类 | 综合判断（见下文） | `scene_type` |
| 被回复消息文本 | `event.reply.message` | `reply_to_text` |
| 被回复者名字 | `event.reply.sender` | `reply_to_user_name` |
| 是否连续发言 | 上一条缓存消息是否也是目标 | `is_continuation` |

### 2.3 feature_json 结构

由 `utils.py` 的 `build_feature_json` 生成，记录单条消息的微观特征：

```json
{
  "text_length": 12,
  "face_ids": ["178", "13"],
  "has_question": false,
  "has_exclamation": true,
  "has_comma": true,
  "modal_words": ["啊", "呢"],
  "seed_phrase_hits": ["笑死"],
  "content_words": ["今天", "食堂", "难吃"],
  "bigrams": ["今天 食堂", "食堂 难吃"],
  "ending_char": "了",
  "punctuation": {"！": 1, "，": 2}
}
```

### 2.4 context_json 结构

由 `context_service.py` 的 `get_recent_context_structured` 生成，记录目标发言前的群聊上下文：

```json
[
  {"user_id": "123456", "name": "群友A", "text": "你中午吃啥了"},
  {"user_id": "789012", "name": "群友B", "text": "食堂吧"},
  {"user_id": "345678", "name": "群友C", "text": "食堂今天涨价了"}
]
```

### 2.5 场景分类逻辑

由 `collector_service.py` 的 `_classify_scene` 按以下优先级判断：

1. 上一条群消息也是目标发的 → `连续发言`
2. 目标的消息带有 `event.reply`（回复了别人的消息） → `回复他人`
3. 最近群消息中有人 @ 了目标 → `被@后回应`
4. 最近群消息中有人提到了目标的名字或关键词 → `被提及后回应`
5. 以上都不满足 → `主动发言`

### 2.6 QQ 表情记录

每条消息中的 QQ 内建表情（`face` 类型）会单独记入 `persona_asset` 表，按 `(target_user_id, face_id)` 去重并累加 `used_count`。用于后续回复生成时给 AI 提供目标最常用的表情 ID。

### 2.7 群消息内存缓存

`context_service.py` 维护了一个 `_GROUP_MESSAGE_CACHE`（按群号分组的 deque），缓存每个群最近的消息（默认 `recent_context_size * 4` 条）。这个缓存有两个用途：

- **采集时**：为 `collector_service` 提供发言前上下文（`context_json`）和连续发言检测。
- **回复生成时**：为 `auto_reply` 和 `commands` 提供最近群聊上下文（`recent_chat_messages`）。

缓存中每条消息的结构：

```json
{
  "group_id": "群号",
  "message_id": "消息ID",
  "user_id": "发言者QQ",
  "sender_name": "发言者群昵称",
  "rendered_text": "渲染后的文本（含[face:13]等标记）",
  "raw_segments": [{"type": "text", "data": {"text": "..."}}],
  "reply_to_user_id": "如果是回复消息，被回复者的QQ",
  "reply_to_sender_name": "被回复者名字",
  "reply_rendered_text": "被回复消息的文本",
  "timestamp": "2026-04-11T14:30:00+08:00"
}
```

---

## 3. 阶段二：画像总结

### 3.1 触发方式

- **定时触发**：`scheduler.py` 注册了定时任务（默认 30 分钟），遍历所有 `enabled=True` 的目标，当未总结的新增消息数达到 `summary_batch_size` 阈值时自动总结。
- **手动触发**：用户发送 `人设总结 [QQ号]`，跳过阈值判断强制总结。

### 3.2 发送给 AI 的数据

由 `summarizer_service.py` 的 `summarize_target` 组装，通过 `prompts.py` 的 `build_summary_prompt` 构建提示词。发送给 AI 的输入数据包含以下部分：

#### (1) current_profile — 当前画像

如果目标之前已经有画像，传入上一次的画像 JSON（经过 `_normalize_profile` 归一化）；如果是第一次总结，传入空模板。AI 需要在此基础上更新。

#### (2) incremental_stats — 增量统计特征

由 `_build_incremental_stats` 从本次参与总结的消息的 `feature_json` 中聚合而来：

```json
{
  "sample_count": 30,
  "non_empty_text_count": 28,
  "average_text_length": 14.5,
  "typical_length_range": "3-25",
  "question_ratio": 0.133,
  "exclamation_ratio": 0.267,
  "top_face_ids": ["178", "13", "277"],
  "top_seed_phrases": ["笑死", "无语"],
  "top_modal_words": ["啊", "哈", "呢"],
  "top_punctuation": ["！", "，", "。"],
  "top_content_words": ["今天", "食堂", "游戏", "..."],
  "top_bigrams": ["今天 食堂", "游戏 更新", "..."],
  "top_ending_chars": ["了", "啊", "哈"]
}
```

#### (3) sample_messages — 原话样本

从本次参与总结的消息中取最多 `PERSONA_SUMMARY_SAMPLE_SIZE`（默认 25）条，渲染为文本格式（含 `[face:13]` 等标记）。

#### (4) context_samples — 场景化对话样本

由 `_build_context_samples` 从消息的 `context_json`、`scene_type`、`reply_to_text` 中提取，最多 8 个：

```json
[
  {
    "context": [
      {"user_id": "123", "name": "群友A", "text": "你中午吃啥了"},
      {"user_id": "456", "name": "群友B", "text": "食堂吧"}
    ],
    "target_said": "随便吃的 食堂太难吃了",
    "scene_type": "被提及后回应",
    "reply_to": {
      "user_name": "群友A",
      "text": "你中午吃啥了"
    }
  }
]
```

### 3.3 AI 提示词要求

提示词（`build_summary_prompt`）要求 AI 扮演"聊天风格画像分析器"，核心约束：

- 只总结表达习惯，不总结具体事件，不猜测没有证据的性格
- 输出必须是与画像模板兼容的 JSON，不能附带解释文字
- `catchphrases` 只保留目标真正反复使用的表达，不填通用网络流行语
- `negative_rules` 写清楚不要模仿成什么样
- `reply_constraints` 写成生成回复时必须遵守的简短约束
- 分析 `context_samples` 中不同 `scene_type` 下的回应风格差异

### 3.4 AI 返回与后处理

**AI 预期返回**：一个符合画像模板结构的 JSON 对象。

**JSON 解析**（`utils.py` 的 `safe_json_loads`）：
1. 去除 ` ```json ``` ` 代码块标记
2. 尝试 `json.loads` 解析
3. 如果失败，用正则提取最外层 `{...}` 再解析
4. 如果还是失败，触发重试（在 prompt 末尾追加"只输出合法 JSON"的补充要求，最多重试 2 次）

**画像归一化**（`_normalize_profile`）：对 AI 返回的画像做结构校验和清洗，确保每个字段的类型正确（列表字段去重、字符串字段 strip），缺失的字段用默认值填充。

**持久化**：
1. 创建 `persona_profile_snapshot` 记录（保存本次总结的画像、使用的 prompt、AI 原始返回）
2. 更新 `persona_profile_state`（用最新画像覆盖 `current_profile_json`）
3. 更新 `persona_target.last_summarized_message_id`（记录总结到哪条消息了）

---

## 4. 阶段三：模仿回复生成

### 4.1 触发方式

#### 自动触发（auto_reply.py）

注册了 `priority=20, block=False` 的全局消息监听器。触发条件（满足任一）：

| 条件 | 得分 |
|------|------|
| 消息中 @ 了目标 | +120 |
| 消息是回复目标之前说的话 | +100 |
| 消息文本中包含目标的触发关键词 | 每个关键词 +10 + 关键词字符数 |

额外过滤：
- 发送者是目标本人 → 跳过
- 发送者是机器人自己 → 跳过
- 目标的 `auto_reply_enabled` 不为 True → 跳过
- 距上次自动回复未超过冷却时间（默认 180 秒） → 跳过
- 目标还没有画像（`persona_profile_state` 不存在） → 跳过
- 如果多个目标同时被触发，选得分最高的那个

#### 手动触发（commands.py）

用户发送 `学他说话 [QQ号] <想表达的话>`。

### 4.2 发送给 AI 的数据

由 `summarizer_service.py` 的 `generate_reply` 组装，通过 `prompts.py` 的 `build_speak_prompt` 构建提示词。发送给 AI 的输入数据包含以下部分：

#### (1) target_identity — 目标身份信息

```json
{
  "target_user_id": "123456",
  "display_name": "小明",
  "aliases": ["小明", "明哥", "老明"]
}
```

#### (2) trigger_payload — 当前触发信息

自动触发时：

```json
{
  "source": "auto_group_trigger",
  "group_id": "群号",
  "trigger_user_id": "触发者QQ",
  "trigger_user_name": "触发者群昵称",
  "at_target_user": true,
  "reply_to_target_user": false,
  "matched_keywords": ["小明"],
  "raw_trigger_message": "小明你在吗"
}
```

手动触发时：

```json
{
  "source": "manual_command",
  "trigger_user_id": "使用者QQ",
  "trigger_user_name": "使用者昵称",
  "group_id": "群号"
}
```

#### (3) recent_chat_messages — 最近群聊上下文

从内存缓存中取最近 `PERSONA_RECENT_CONTEXT_SIZE`（默认 12）条群消息，每条包含：

```json
{
  "message_id": "消息ID",
  "speaker_id": "发言者QQ",
  "speaker_name": "发言者名字",
  "is_target_user": false,
  "mentions_target_user": true,
  "reply_to_target_user": false,
  "reply_to_sender_name": "",
  "reply_preview": "",
  "text": "小明你中午吃啥了",
  "timestamp": "2026-04-11T14:30:00+08:00"
}
```

#### (4) profile — 目标说话风格画像

从 `persona_profile_state.current_profile_json` 读取，经过 `_normalize_profile` 归一化。结构见 [4.6 画像 JSON 模板](#46-画像-json-模板)。

#### (5) similar_messages — 历史原话风格参考

检索过程：
1. 从 `persona_message` 取最近 200 条 + 随机历史采样 100 条，组成候选池
2. 用 `intent_text`（用户想表达的内容）或最近群聊上下文作为检索 query
3. 对候选池中每条消息计算 Jaccard 相似度（基于 jieba 分词）+ 包含奖励
4. 取相似度最高的 `PERSONA_SPEAK_SAMPLE_SIZE`（默认 8）条，渲染为文本

#### (6) conversation_snippets — 目标历史对话片段

这是本次改动新增的核心数据。检索过程：
1. 从 `persona_message` 取最近 300 条消息，按时间正序排列
2. 将连续发言（`is_continuation=True`）合并到前一条消息，形成对话片段
3. 对每个片段打分：场景类型匹配当前触发场景 +1.0 分，内容相似度 0~0.8 分
4. 取得分最高的 5 个片段，混入少量随机片段增加多样性

每个片段的结构：

```json
{
  "context": [
    {"user_id": "123", "name": "群友A", "text": "你中午吃啥了"},
    {"user_id": "456", "name": "群友B", "text": "食堂吧"}
  ],
  "target_replies": ["随便吃的 食堂太难吃了", "而且今天还涨价了 无语"],
  "scene_type": "被提及后回应",
  "reply_to": {
    "user_name": "群友A",
    "text": "你中午吃啥了"
  }
}
```

`target_replies` 为列表：如果目标当时连发了多条消息，会全部保留，让 AI 看到目标的连发习惯。

#### (7) top_face_ids — 常用 QQ 表情 ID

从 `persona_asset` 按 `used_count` 降序取前 5 个表情 ID。

#### (8) explicit_intent — 显性意图

用户想表达的内容（手动模仿时的文本参数，自动触发时为提取的意图文本）。

### 4.3 AI 提示词约束

提示词（`build_speak_prompt`）的核心约束：

1. 回复长度根据画像中的 `typical_length_range` / `avg_length` 动态生成约束
2. 风格要像熟人群聊随口接话，不要写成客服或公文
3. 如果不适合用 QQ 表情，`face_id` 返回空字符串
4. 不要输出任何图片素材或自定义表情包相关内容
5. reply 必须在语气、句式、标点、用词习惯上尽量接近历史原话的风格，但不要照抄内容
6. 句尾风格要和目标保持一致（比如目标从不加句号你也不要加）
7. 重点参考历史对话片段中目标的接话方式和连发节奏
8. 根据触发场景（被@、被回复、被提及）调整回复策略

### 4.4 AI 预期返回

```json
{
  "reply": "随便吃的 食堂太难吃了",
  "face_id": "178"
}
```

- `reply`：模仿目标语气的回复文本。如果目标有连发习惯，可以用换行分成多条短句。
- `face_id`：可选的 QQ 内建表情 ID，空字符串表示不加表情。

### 4.5 返回后处理

1. **JSON 解析**：同画像总结一样，经过 `safe_json_loads` 解析，解析失败时追加"只输出合法 JSON"重试，最多 2 次。
2. **校验**：`reply` 字段不能为空，否则抛出异常。
3. **构建消息**：用 `reply` 构建 `Message` 对象。如果 `face_id` 是合法数字，追加一个 `MessageSegment.face(int(face_id))`。
4. **发送**：通过 `bot.send(event, message)` 发送到触发消息所在的群。
5. **更新冷却**（仅自动触发）：将当前时间写入 `persona_target.last_auto_reply_at`，并清除内存中的目标缓存。

### 4.6 AI 接口调用细节

`ai_client.py` 的 `call_text_model` 负责与外部 AI 服务通信：

- **请求格式**：POST 请求，body 为 `{"message": "prompt文本", "memoryId": "唯一ID"}`
- **认证**：通过 `X-API-KEY` header 传递 API Key
- **超时**：70 秒
- **重试**：最多 3 次，每次使用不同的 `memoryId`（格式：`{prefix}-{uuid}`）
- **响应解析**：预期响应 `{"code": 200, "data": {"message": "AI返回的文本"}}`

---

## 5. 目录结构

```text
fish_coins_bot/plugins/persona_mirror/
├── __init__.py                # 插件入口，注册子模块
├── auto_reply.py              # 自动触发条件判断、评分、消息发送
├── collector.py               # 全局消息监听器，驱动采集
├── commands.py                # 指令处理（绑定、总结、关键词、手动模仿等）
├── config.py                  # 环境变量读取，lru_cache 缓存配置
├── models.py                  # Tortoise ORM 模型定义
├── prompts.py                 # AI 提示词构建（画像总结 + 模仿回复）
├── scheduler.py               # 定时画像总结任务
├── utils.py                   # 工具函数（分词、相似度、特征提取、JSON 解析等）
├── services/
│   ├── ai_client.py           # AI 文本接口调用（重试、错误处理）
│   ├── collector_service.py   # 消息采集核心（上下文提取、场景分类、对话对记录）
│   ├── context_service.py     # 群消息内存缓存、结构化上下文、目标提及检测
│   ├── persona_service.py     # 目标管理（绑定、启停、关键词、解析）
│   └── summarizer_service.py  # 画像总结、对话片段提取、模仿回复生成
└── sql/
    └── persona_mirror.sql     # 建表和升级脚本
```

---

## 6. 数据模型

### 6.1 persona_target — 模仿目标

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INT PK | 主键 |
| `owner_user_id` | VARCHAR(32) | 绑定该目标的管理员 QQ |
| `target_user_id` | VARCHAR(32) UNIQUE | 被观察目标 QQ |
| `target_name` | VARCHAR(100) NULL | 目标备注名 |
| `enabled` | BOOL | 是否启用采集 |
| `auto_reply_enabled` | BOOL | 是否启用自动模仿回复 |
| `trigger_keywords_json` | JSON | 自动触发关键词列表 |
| `summary_batch_size` | INT | 触发总结的增量条数阈值 |
| `last_summarized_message_id` | INT | 已总结到的消息 ID |
| `last_auto_reply_at` | DATETIME NULL | 最近一次自动回复时间 |
| `total_collected_messages` | INT | 累计采集条数 |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |

### 6.2 persona_message — 采集的原始消息

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INT PK | 主键 |
| `target_user_id` | VARCHAR(32) | 目标 QQ |
| `group_id` | VARCHAR(32) NULL | 群号 |
| `chat_type` | VARCHAR(16) | `group` 或 `private` |
| `platform_message_id` | VARCHAR(64) NULL | 平台消息 ID |
| `plain_text` | TEXT NULL | 消息纯文本 |
| `normalized_text` | TEXT NULL | 归一化后的文本 |
| `raw_segments_json` | JSON | 原始消息分段（含表情、图片、@等） |
| `feature_json` | JSON | 局部统计特征（标点、语气词、分词等） |
| `scene_type` | VARCHAR(32) | 场景分类：`被@后回应`、`回复他人`、`被提及后回应`、`连续发言`、`主动发言` |
| `reply_to_text` | TEXT NULL | 如果目标在回复某条消息，记录被回复的内容 |
| `reply_to_user_name` | VARCHAR(100) NULL | 被回复者的名字 |
| `is_continuation` | BOOL | 是否为连续发言（目标连发多条消息中的后续部分） |
| `context_json` | JSON | 发言前群聊上下文（结构化，含 user_id、name、text） |
| `message_time` | DATETIME | 消息时间 |
| `created_at` | DATETIME | 入库时间 |

### 6.3 persona_asset — QQ 表情使用记录

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INT PK | 主键 |
| `target_user_id` | VARCHAR(32) | 目标 QQ |
| `message_ref_id` | INT NULL | 来源消息 ID |
| `asset_type` | VARCHAR(16) | 固定为 `face` |
| `asset_key` | VARCHAR(255) | 去重主键（格式：`face:{id}`） |
| `face_id` | VARCHAR(32) | QQ 表情 ID |
| `used_count` | INT | 出现次数 |
| `first_seen_at` | DATETIME | 首次出现时间 |
| `last_seen_at` | DATETIME | 最近出现时间 |

联合唯一约束：`(target_user_id, asset_type, asset_key)`

### 6.4 persona_profile_state — 聚合画像

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INT PK | 主键 |
| `target_user_id` | VARCHAR(32) UNIQUE | 目标 QQ |
| `current_profile_json` | JSON | 当前聚合画像 |
| `latest_snapshot_id` | INT NULL | 最近快照 ID |
| `last_summary_message_id` | INT | 最近总结到的消息 ID |
| `last_summary_at` | DATETIME NULL | 最近总结时间 |
| `total_message_count` | INT | 画像基于的消息总量 |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |

### 6.5 persona_profile_snapshot — 画像快照

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INT PK | 主键 |
| `target_user_id` | VARCHAR(32) | 目标 QQ |
| `summary_type` | VARCHAR(32) | 总结类型：`incremental`（定时）或 `manual`（手动） |
| `source_message_count` | INT | 本次参与总结的消息数 |
| `start_message_id` | INT | 起始消息 ID |
| `end_message_id` | INT | 结束消息 ID |
| `summary_json` | JSON | 本次生成的画像 JSON |
| `prompt_text` | LONGTEXT NULL | 总结时使用的提示词（完整 prompt） |
| `raw_response` | LONGTEXT NULL | AI 原始返回文本 |
| `created_at` | DATETIME | 创建时间 |

### 6.6 画像 JSON 模板

`current_profile_json` 和 `summary_json` 的结构：

```json
{
  "tone": [],
  "sentence_style": {
    "avg_length": "",
    "typical_length_range": "",
    "structure": "",
    "punctuation": [],
    "rhythm": "",
    "ending_habits": []
  },
  "catchphrases": [],
  "habit_words": [],
  "emoji_habits": {
    "qq_faces": []
  },
  "response_patterns": [],
  "topic_tendencies": [],
  "greeting_farewell": "",
  "situational_patterns": [],
  "negative_rules": [],
  "reply_constraints": []
}
```

各字段含义：

| 字段 | 说明 |
|------|------|
| `tone` | 整体语气风格（如"随意"、"直接"、"偶尔调侃"） |
| `sentence_style.avg_length` | 平均句子长度（数字） |
| `sentence_style.typical_length_range` | 典型句子长度范围（如"3-20"） |
| `sentence_style.structure` | 句式结构描述 |
| `sentence_style.punctuation` | 标点使用习惯 |
| `sentence_style.rhythm` | 说话节奏描述 |
| `sentence_style.ending_habits` | 句尾收尾方式（如"~"、"哈哈"、不加标点等） |
| `catchphrases` | 目标真正反复使用的口头禅 |
| `habit_words` | 高频用词和语气词组合 |
| `emoji_habits.qq_faces` | 最常用的 QQ 表情 ID |
| `response_patterns` | 不同场景下的回应习惯 |
| `topic_tendencies` | 话题偏好（倾向聊什么、回避什么） |
| `greeting_farewell` | 打招呼和告别方式 |
| `situational_patterns` | 特定情境下的表现模式 |
| `negative_rules` | 不要模仿成什么样（如"不用书面语"） |
| `reply_constraints` | 生成回复时必须遵守的约束 |

---

## 7. 环境变量

### 7.1 AI 接口

- `PERSONA_TEXT_URI` — 人设插件专用文本接口地址。
- `PERSONA_TEXT_APIKEY` — 人设插件专用文本接口 Key。

如果这两个没配，会回退到 `AI_TEXT_URI` / `AI_TEXT_APIKEY`。

### 7.2 管理员

- `PERSONA_ADMIN_IDS` — 管理员 QQ 列表，英文逗号分隔。
- `ADMIN_ID` — 单个管理员 QQ，作为回退值。如果都没配，所有人都可执行管理指令。

### 7.3 画像总结

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PERSONA_SUMMARY_BATCH_SIZE` | 30 | 新增多少条消息后自动触发总结 |
| `PERSONA_SUMMARY_SAMPLE_SIZE` | 25 | 每次喂给 AI 的样本文本条数上限 |
| `PERSONA_SUMMARY_INTERVAL_MINUTES` | 30 | 定时器检查间隔（分钟） |
| `PERSONA_SCHEDULER_ENABLED` | true | 是否启用定时总结 |

### 7.4 模仿生成

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PERSONA_SPEAK_SAMPLE_SIZE` | 8 | 生成模仿时带几条最像的历史原话 |
| `PERSONA_RECENT_CONTEXT_SIZE` | 12 | 自动模仿时带最近多少条群消息 |
| `PERSONA_AUTO_REPLY_COOLDOWN_SECONDS` | 180 | 同一目标自动模仿的冷却秒数 |
| `PERSONA_AUTO_REPLY_MIN_KEYWORD_LENGTH` | 2 | 自动触发关键词的最短长度 |

---

## 8. 指令

| 指令 | 说明 |
|------|------|
| `人设帮助` | 查看指令列表 |
| `人设绑定 <QQ号> [备注名]` | 绑定观察目标，自动开启采集和自动回复 |
| `人设开启 <QQ号>` | 开启目标的采集和自动回复 |
| `人设关闭 <QQ号>` | 关闭目标的采集和自动回复 |
| `人设关键词 <QQ号> <关键词1> [关键词2] ...` | 设置自动触发关键词 |
| `人设看关键词 [QQ号]` | 查看当前触发关键词 |
| `人设状态` | 查看所有目标的采集和画像状态 |
| `人设总结 [QQ号]` | 手动触发画像总结 |
| `学他说话 [QQ号] <想表达的话>` | 用目标的语气说一句话 |

---

## 9. 依赖

- `nonebot_plugin_apscheduler` — 定时任务
- `tortoise-orm` — 数据库 ORM
- `jieba` — 中文分词（用于相似度匹配和特征提取）
- `httpx` — AI 接口调用
