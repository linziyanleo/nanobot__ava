---
name: send-sticker
description: Send Telegram stickers from the ava origin sticker pack. Use when Ava wants to express emotions visually or add playful reactions to messages. Supports 24 different stickers for various emotions (happy, shy, angry, sleepy, etc.).
---

# send_sticker

发送 Telegram 表情包（Sticker）。已内置为 agent 工具，对话中直接调用即可。

## 使用方法

直接调用内置的 `send_sticker` 工具：

```
send_sticker(sticker_id: int, chat_id?: str)
```

- `sticker_id` (int, 必填): 表情编号 1-24
- `chat_id` (str, 可选): Telegram 聊天 ID。不传时自动使用当前会话的 chat context

### 示例

```
send_sticker(sticker_id=4)              # 发送打招呼表情到当前聊天
send_sticker(sticker_id=14, chat_id="12345678")  # 发送爱心到指定聊天
```

## 表情包信息

- **名称**: ava origin
- **链接**: https://t.me/addstickers/ava_01
- **总数**: 24 个表情

## 表情列表

| 编号 | Emoji | 含义 |
|------|-------|------|
| 1 | 😌🥰 | 满足/幸福 |
| 2 | 😲😱🤯 | 震惊/惊讶 |
| 3 | 😴🥱 | 困倦/想睡 |
| 4 | 😊🌞👋 | 打招呼/阳光 |
| 5 | 🤕😵😰 | 受伤/难受 |
| 6 | 💃🕺🎵 | 跳舞/欢乐 |
| 7 | 😤😒🙄 | 傲娇/不满 |
| 8 | 🤪😶🤨 | 搞怪/疑惑 |
| 9 | 🎸😉🎶 | 音乐/悠闲 |
| 10 | 🎮🕹️👾 | 游戏/玩耍 |
| 11 | 😎🤙😏 | 得意/耍酷 |
| 12 | 🤩😍✨ | 崇拜/花痴 |
| 13 | 😑🙄😓🤦😶 | 无语/无奈 |
| 14 | ❤️😊🥰 | 爱心/喜欢 |
| 15 | 🤔🌀😵‍💫 | 思考/困惑 |
| 16 | 🎧🕺🪩 | 派对/音乐 |
| 17 | 🙂😏👀 | 围观/吃瓜 |
| 18 | 😱😭 | 崩溃/大哭 |
| 19 | 🫨🤹🤡 | 混乱/小丑 |
| 20 | 😳🙈💗🥺💕 | 害羞/心动 |
| 21 | ✨🎭⚡🎉 | 庆祝/魔法 |
| 22 | 😪🥱😴 | 困/睡觉 |
| 23 | 👊💥😤 | 生气/抗议 |
| 24 | 🪼 | 水母/神秘 |

## 使用建议

- 根据对话情绪自然地选择表情，不要每句话都发
- 傲娇时用 7，被夸害羞时用 20，整活时用 8 或 19
- 水母（24）是向晚的专属符号，特殊时刻用

## 注意事项

- 表情编号必须在 1-24 范围内
- 仅支持 Telegram 渠道
