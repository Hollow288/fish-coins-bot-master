# fish-coins-bot

基于 NoneBot2 和 OneBot v11 的 QQ 群机器人。当前插件都位于 `fish_coins_bot/plugins`。

## 插件清单

### hotta_wiki

幻塔相关插件，入口为 `fish_coins_bot/plugins/hotta_wiki/__init__.py`。

主要功能：

- 图鉴图片查询
- 活动资讯图片生成和推送
- 抽卡模拟
- 帮助菜单
- 每月特殊凭证提醒

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

- 戳一戳机器人：按当前时间回复问候和帮助提示。
- 回复机器人消息：提示发送帮助。
- 定时生成活动资讯图。
- 活动即将结束时向所有群推送提醒图。
- 每月最后一天推送特殊凭证提醒。

相关文件：

- `fish_coins_bot/plugins/hotta_wiki/alias.json`：武器、意志、源器别名。
- `fish_coins_bot/plugins/hotta_wiki/gacha_config.json`：抽卡配置。
- `screenshots/`：图鉴图片和生成图片。

### bilibili

B 站直播和动态推送插件，入口为 `fish_coins_bot/plugins/bilibili/__init__.py`。

主要功能：

- 监听直播间状态，开播时推送直播卡片图，下播时推送直播时长。
- 监听 B 站用户动态，发现新动态后截图并推送到配置群。

相关文件：

- `fish_coins_bot/plugins/bilibili/dynamics_list.json`：动态推送配置，格式为 `{"B站UID": [群号1, 群号2]}`。
- `bot_live_state` 表：直播间和推送群配置。
- `dynamics_history` 表：动态去重记录。

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
| `image <提示词>` | `images` | 从当前消息取第一张图片，调用图片接口后返回图片 |
| `remove <文本>` | `clear` | 调用去文字/清理文本接口 |

### agent

图鉴别名 Agent 查询插件，入口为 `fish_coins_bot/plugins/agent/__init__.py`。

指令：

```text
agent <自然语言查询>
```

插件会调用外部 Agent 接口识别查询目标，返回标准图鉴名称后发送对应图片。

支持类型：

- `武器`：发送武器图鉴或武器详情图。
- `意志`：发送意志图鉴。
- `源器`：发送源器图鉴。

### download

私聊视频下载插件，入口为 `fish_coins_bot/plugins/download/__init__.py`。

这些指令只响应私聊，并且只有 `ADMIN_ID` 能使用。

| 指令 | 别名 | 说明 |
| --- | --- | --- |
| `下载视频 <url>` | `视频` | 后台调用 `yt-dlp` 下载视频，并尝试同步到 MinIO |

### persona_mirror

人设模仿插件，入口为 `fish_coins_bot/plugins/persona_mirror/__init__.py`。

主要功能：

- 绑定一个或多个被模仿目标 QQ。
- 持续采集目标发言、QQ 内建表情、回复关系、上下文和场景特征。
- 定时或手动总结目标画像。
- 群聊中有人 @ 目标、回复目标或提到目标关键词时，自动用目标风格回复。
- 记录目标常用 QQ 内建表情。
- 保存目标发送过的图片表情包，并记录使用次数。

管理指令：

| 指令 | 别名 | 说明 |
| --- | --- | --- |
| `人设帮助` | `persona帮助` | 查看插件指令 |
| `人设绑定 <QQ号> [备注名]` | `persona_bind` | 绑定采集目标 |
| `人设开启 <QQ号>` | `persona_on` | 开启采集和自动回复 |
| `人设关闭 <QQ号>` | `persona_off` | 关闭采集和自动回复 |
| `人设关键词 <QQ号> <关键词1> [关键词2] ...` | `persona_keywords` | 设置自动触发关键词 |
| `人设看关键词 [QQ号]` | `persona_show_keywords` | 查看触发关键词 |
| `人设状态` | `persona_status` | 查看目标状态、消息数和常用 QQ 内建表情 |
| `人设总结 [QQ号]` | `persona_summary` | 强制生成画像摘要 |
| `模仿冷却 [秒数]` | `persona_cooldown` | 查看或临时修改自动回复冷却 |
| `学他说话 [QQ号] <想表达的话>` | `persona_speak` | 手动生成一条目标风格回复 |

表情记录：

- QQ 内建表情，即 OneBot `face` 段，记录到 `persona_asset`，保存 `face_id` 和 `used_count`。
- 图片/表情包，即带 `url` 的 `image`、`mface`、`marketface` 段，下载后按内容 `sha256` 去重，保存到 MinIO，并写入 `persona_sticker_asset`。

相关表：

- `persona_target`：被模仿目标。
- `persona_message`：采集到的原始消息。
- `persona_asset`：QQ 内建表情使用记录。
- `persona_sticker_asset`：图片表情包使用记录。
- `persona_profile_state`：当前画像。
- `persona_profile_snapshot`：画像快照。
- `persona_auto_reply_log`：自动回复日志。
