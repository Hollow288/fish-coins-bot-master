# persona_mirror

`persona_mirror` 是一个独立的 NoneBot2 插件，用来持续采集某个目标 QQ 的发言，生成"说话画像"，并在群聊触发时用他的语气直接发一条消息。

当前版本的真实行为是：

1. 只记录目标本人的消息。
2. 画像总结基于目标本人历史消息，并附带发言前的群聊上下文（用于理解场景）。
3. 自动模仿时，会把目标画像和最近群聊消息一起发给 AI。
4. 触发后机器人是直接发送一条新消息，不是回复某条消息。
5. 仅保留 QQ 内建 `face_id` 的使用习惯，不再保留"表情包素材库"逻辑。

如果你要的就是"记录一个熟人的说话习惯，然后在群里有人叫他时让机器人像他一样接话"，这个插件就是按这个目标写的。

## 1. 当前逻辑总览

完整链路分成四段：

1. 绑定目标。
2. 采集目标消息（附带发言前上下文）。
3. 定时或手动总结画像。
4. 在群里被触发时生成模仿消息并发送。

其中最关键的两个判断是：

- 画像是根据目标本人说过的话（以及说话时的上下文场景）生成的。
- 模仿时会带上最近群聊上下文，避免 AI 脱离当前话题乱接。

## 2. 目录结构

```text
fish_coins_bot/plugins/persona_mirror/
├── __init__.py
├── auto_reply.py
├── collector.py
├── commands.py
├── config.py
├── models.py
├── prompts.py
├── scheduler.py
├── utils.py
├── services/
│   ├── ai_client.py
│   ├── collector_service.py
│   ├── context_service.py
│   ├── persona_service.py
│   └── summarizer_service.py
└── sql/
    └── persona_mirror.sql
```

各文件职责：

- `collector.py`
  监听消息事件，驱动采集。
- `services/collector_service.py`
  只在"发送者就是目标本人"时落库，并抽取文本特征、QQ 表情和发言前上下文。
- `services/context_service.py`
  在内存里缓存最近群消息，供自动模仿时拼接上下文，也为 collector 提供发言前上下文。
- `services/summarizer_service.py`
  负责画像总结和模仿生成。支持扩大候选消息池（最近消息 + 历史采样）。
- `auto_reply.py`
  负责自动触发条件判断和最终发送消息。内置目标缓存减少数据库查询。
- `commands.py`
  负责人设绑定、总结、关键词维护、手动模仿等命令。
- `utils.py`
  工具函数，包括基于 jieba 分词的相似度计算和 n-gram 特征提取。
- `prompts.py`
  AI 提示词构建，支持动态长度约束和场景感知。

## 3. 依赖

本插件额外依赖 `jieba` 分词库，用于提高中文相似度匹配和特征提取的质量。

## 4. 画像结构

画像 JSON 模板：

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

相比旧版新增的字段：
- `sentence_style.typical_length_range` — 消息长度范围（如"3-20"）
- `sentence_style.ending_habits` — 句尾收尾方式
- `response_patterns` — 不同场景下的回应习惯
- `topic_tendencies` — 话题偏好
- `greeting_farewell` — 打招呼和告别方式

## 5. 环境变量

配置读取逻辑在 config.py。

### 5.1 AI 接口

- `PERSONA_TEXT_URI` — 人设插件专用文本接口地址。
- `PERSONA_TEXT_APIKEY` — 人设插件专用文本接口 Key。

如果这两个没配，会回退到 `AI_TEXT_URI` / `AI_TEXT_APIKEY`。

### 5.2 管理员

- `PERSONA_ADMIN_IDS` — 管理员 QQ 列表，英文逗号分隔。
- `ADMIN_ID` — 单个管理员 QQ，作为回退值。

### 5.3 画像总结

- `PERSONA_SUMMARY_BATCH_SIZE` — 自动总结阈值，默认 30。
- `PERSONA_SUMMARY_SAMPLE_SIZE` — 每次喂给画像模型的样本文本条数上限，默认 25。
- `PERSONA_SUMMARY_INTERVAL_MINUTES` — 定时器多久跑一次，默认 30 分钟。
- `PERSONA_SCHEDULER_ENABLED` — 是否启用定时总结，默认开启。

### 5.4 模仿生成

- `PERSONA_SPEAK_SAMPLE_SIZE` — 生成模仿时带几条最像的历史原话，默认 8。
- `PERSONA_RECENT_CONTEXT_SIZE` — 自动模仿时带最近多少条群消息，默认 12。
- `PERSONA_AUTO_REPLY_COOLDOWN_SECONDS` — 自动模仿冷却秒数，默认 180。
- `PERSONA_AUTO_REPLY_MIN_KEYWORD_LENGTH` — 自动触发关键词最短长度，默认 2。

## 6. 指令

- `人设绑定 <QQ号> [备注名]`
- `人设开启 <QQ号>`
- `人设关闭 <QQ号>`
- `人设自动回复开启 <QQ号>`
- `人设自动回复关闭 <QQ号>`
- `人设关键词 <QQ号> <关键词1> [关键词2] ...`
- `人设看关键词 [QQ号]`
- `人设状态`
- `人设总结 [QQ号]`
- `学他说话 [QQ号] <想表达的话>`
