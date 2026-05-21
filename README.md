# fish-coins-bot

基于 NoneBot2 和 OneBot v11 的 QQ 群机器人。当前插件都位于 `fish_coins_bot/plugins`，本文只介绍本地插件。

## 插件清单

### hotta_wiki

幻塔相关插件，入口为 `fish_coins_bot/plugins/hotta_wiki/__init__.py`。

主要功能：

- 图鉴图片查询：武器、武器详情/模组、意志、源器、食物/食材、时装。
- 活动资讯图片生成、查询和即将结束提醒。
- 幻塔十连抽卡模拟，按 QQ 号限制每天一次，并记录保底、UP 中歪和累计抽数。
- 帮助菜单图片。
- 戳一戳问候。
- @ 机器人或回复机器人时触发 AI 兜底回复，闲聊场景可从 `sticker_collector` 的候选表情包中挑选一张一起发送。

群聊指令：

| 指令 | 别名 | 说明 |
| --- | --- | --- |
| `@机器人 帮助` | `help`、`菜单` | 发送帮助菜单图片 |
| `武器图鉴 <名称>` | `武器信息` | 查询武器图鉴 |
| `武器详情 <名称>` | `武器攻击`、`武器模组图鉴`、`模组图鉴`、`攻击模组图鉴`、`攻击图鉴`、`武器模组` | 查询武器详情/模组图鉴 |
| `意志图鉴 <名称>` | `意志` | 查询意志图鉴 |
| `源器图鉴 <名称>` | `源器` | 查询源器图鉴 |
| `食物图鉴 <名称>` | `食谱`、`食材图鉴`、`食材`、`烹饪图鉴`、`食物` | 查询食物/食材图鉴 |
| `时装图鉴 <名称>` | `时装` | 查询时装图鉴 |
| `活动资讯` | `近期活动`、`塔塔活动` | 发送近期活动图 |
| `塔塔抽卡` | `幻塔抽卡`、`幻塔十连`、`塔塔十连` | 每个 QQ 每天一次十连模拟 |

自动行为：

- 戳一戳机器人：按上海时间回复问候和帮助提示。
- @ 机器人或回复机器人：兜底调用文本 AI 生成回复；游戏查询类内容会引导用户发送帮助菜单。
- 每天 00:05、05:05、12:05 生成活动资讯图。
- 每天 12:30 检查 7 天内即将结束的活动，生成并向所有群推送提醒图。
- 每月最后一天 18:30 向所有群推送特殊凭证提醒图。

相关文件和表：

- `fish_coins_bot/plugins/hotta_wiki/alias.json`：武器、意志、源器别名。
- `fish_coins_bot/plugins/hotta_wiki/gacha_config.json`：抽卡配置。
- `screenshots/`：图鉴图片、抽卡素材和生成图片。
- `event_news`：活动资讯数据。
- `gacha_record`：用户抽卡记录。

### bilibili

B 站直播和动态推送插件，入口为 `fish_coins_bot/plugins/bilibili/__init__.py`。

主要功能：

- 每 10 秒检查 `bot_live_state` 中配置的直播间，状态变化时推送开播图或下播时长。
- 启动时同步一次直播间当前状态，避免重启后误判开播/下播。
- 每 60 秒读取 `dynamics_list.json` 中配置的 B 站 UID，检测图文、文字、专栏和视频动态。
- 新动态会通过 Playwright 截图后推送到配置群；超过 2 小时的旧动态只记入去重记录，不再推送。

相关文件和表：

- `fish_coins_bot/plugins/bilibili/dynamics_list.json`：动态推送配置，格式为 `{"B站UID": [群号1, 群号2]}`。
- `bot_live_state`：直播间、推送群和直播状态。
- `dynamics_history`：动态去重记录。

### delta_force

三角洲行动密码房插件，入口为 `fish_coins_bot/plugins/delta_force/__init__.py`。

群聊指令：

| 指令 | 别名 | 说明 |
| --- | --- | --- |
| `密码房密码` | `密码房`、`三角洲密码房`、`三角洲密码`、`三角洲钥匙房`、`鼠鼠行动密码房`、`密码`、`今日密码` | 查询并渲染密码房密码图 |

相关文件：

- `fish_coins_bot/plugins/delta_force/delta_force_request.json`：密码接口 URL 和请求头配置。

### ai_chat

私聊 AI 工具插件，入口为 `fish_coins_bot/plugins/ai_chat/__init__.py`。

这些指令只响应私聊，并且只有 `ADMIN_ID` 能使用。

| 指令 | 别名 | 说明 |
| --- | --- | --- |
| `chat <文本>` | `ai` | 调用文本 AI 接口 |
| `image <提示词>` | `images` | 从当前消息取第一张图片作为输入，调用图片接口后返回图片 |
| `remove <文本>` | `clear` | 调用去文字/清理文本接口 |

相关配置：

- `AI_TEXT_URI`、`AI_TEXT_APIKEY`：文本 AI 接口。
- `AI_IMAGE_URI`、`AI_IMAGE_APIKEY`：图片接口。
- `AI_REMOVE_TEXT_URI`：去文字/清理文本接口。

### agent

图鉴别名 Agent 查询插件，入口为 `fish_coins_bot/plugins/agent/__init__.py`。

指令：

```text
agent <自然语言查询>
```

插件会调用外部 Agent 接口 `/api/v1/agent/ask`，只接收路由到 `alias` Agent 的结果。接口返回标准图鉴名称后，插件会发送对应图片。

支持类型：

- `武器`：默认发送武器图鉴；查询文本中包含“详情”时发送武器详情/模组图。
- `意志`：发送意志图鉴。
- `源器`：发送源器图鉴。

相关配置：

- `AGENT_ASK_URI`：Agent 查询接口地址。
- `AGENT_ASK_APIKEY`：Agent 查询接口密钥。

### download

私聊视频下载插件，入口为 `fish_coins_bot/plugins/download/__init__.py`。

这些指令只响应私聊，并且只有 `ADMIN_ID` 能使用。

| 指令 | 别名 | 说明 |
| --- | --- | --- |
| `下载视频 <url>` | `视频` | 后台调用 `yt-dlp` 下载视频，并同步到 MinIO |

自动行为：

- 视频下载到 `downloads/video`。
- 支持 `.mp4`、`.mkv`、`.webm`、`.mov`、`.avi`。
- 同步到 MinIO 的 `big-file/movies/` 后，本地文件会重命名为 `.uploaded` 标记。

### persona_mirror

人设模仿插件，入口为 `fish_coins_bot/plugins/persona_mirror/__init__.py`。

主要功能：

- 绑定一个或多个被模仿目标 QQ。
- 持续采集目标在群聊/私聊中的发言、消息分段、回复关系、上下文和场景特征。
- 记录目标常用 QQ 内建表情，即 OneBot `face` 段。
- 定时或手动总结目标画像。
- 群聊中有人 @ 目标、回复目标或提到目标触发关键词时，基于画像和最近上下文自动生成目标风格回复。
- 支持手动生成一条目标风格回复。
- 图片表情包采集已迁移到独立的 `sticker_collector` 插件。

管理指令：

这些指令默认仅 `PERSONA_ADMIN_IDS` 或 `ADMIN_ID` 可用；两者都未配置时不限制。

| 指令 | 别名 | 说明 |
| --- | --- | --- |
| `人设帮助` | `persona帮助` | 查看插件指令 |
| `人设绑定 <QQ号> [备注名]` | `persona_bind` | 绑定采集目标，并自动开启采集和自动回复 |
| `人设开启 <QQ号>` | `persona_on` | 开启采集和自动回复 |
| `人设关闭 <QQ号>` | `persona_off` | 关闭采集和自动回复 |
| `人设关键词 <QQ号> <关键词1> [关键词2] ...` | `persona_keywords` | 设置自动触发关键词 |
| `人设看关键词 [QQ号]` | `persona_show_keywords` | 查看触发关键词 |
| `人设状态` | `persona_status` | 查看目标状态、消息数、总结进度和常用 QQ 内建表情 |
| `人设总结 [QQ号]` | `persona_summary` | 强制生成画像摘要 |
| `模仿冷却 [秒数]` | `persona_cooldown` | 查看或临时修改自动回复冷却 |
| `学他说话 [QQ号] <想表达的话>` | `persona_speak` | 手动生成一条目标风格回复 |

自动行为：

- 全局监听群聊/私聊消息，只采集已绑定且启用的目标。
- 群聊采集会记录发言前上下文、连续发言、回复对象，以及“主动发言 / 回复他人 / 被 @ 后回应 / 被提及后回应”等场景类型。
- 定时任务每 `PERSONA_SUMMARY_INTERVAL_MINUTES` 分钟检查启用目标，新增消息达到阈值后自动生成增量画像。
- 自动回复前会检查当前群是否采集过该目标、目标是否已有画像、画像消息数是否达到 `PERSONA_AUTO_REPLY_MIN_MESSAGE_COUNT`，并受冷却时间限制。
- 自动回复结果会写入 `persona_auto_reply_log`。

相关表：

- `persona_target`：被模仿目标。
- `persona_message`：采集到的原始消息。
- `persona_asset`：QQ 内建表情使用记录。
- `persona_profile_state`：当前画像。
- `persona_profile_snapshot`：画像快照。
- `persona_auto_reply_log`：自动回复日志。

### sticker_collector

全局表情包采集 + AI 识别插件，入口为 `fish_coins_bot/plugins/sticker_collector/__init__.py`。

主要功能：

- 无指令交互，自动扫描每条群聊/私聊消息。
- 提取带 `url` 的 `image`、`mface`、`marketface` 段。
- 流式下载图片，超过 `STICKER_COLLECTOR_MAX_SIZE_BYTES` 的资源会跳过。
- 按 `content_sha256` 全局去重，上传到 MinIO 桶 `fish-coins-bot-master/sticker/<sha256>.<ext>`。
- 记录每个用户使用过哪些表情包及使用次数。
- 定时调用 AI 图片识别接口，判断是否适合作为聊天表情包，并写回含义与情绪标签。
- 为 `hotta_wiki` 的 AI 兜底回复提供已识别、适合作为表情包的候选池。

自动行为：

- `STICKER_COLLECTOR_ENABLED=true` 时启用全局采集。
- 每 `STICKER_RECOGNIZE_INTERVAL_MINUTES` 分钟取一批 `recognize_status='pending'` 的表情包做 AI 识别。
- 识别批量大小、最大重试次数和节流间隔分别由 `STICKER_RECOGNIZE_BATCH_SIZE`、`STICKER_RECOGNIZE_MAX_ATTEMPTS`、`STICKER_RECOGNIZE_THROTTLE_MS` 控制。
- AI 识别会写入 `is_suitable_sticker`、`sticker_meaning`、`emotion_tag`、`recognize_status` 等字段。

相关表：

- `sticker_asset`：全局唯一表情包资产，按 `content_sha256` 去重，含 AI 识别结果。
- `sticker_usage`：用户与表情包的使用记录，`(sticker_id, user_id)` 唯一。
