---
name: send-sticker
description: Send Telegram stickers from the ava origin sticker pack. Use when Ava wants to express emotions visually or add playful reactions to messages. Supports 24 different stickers for various emotions (happy, shy, angry, sleepy, etc.).
---

# send_sticker

发送 Telegram 表情包（Sticker）

## 功能描述

根据表情编号发送 ava origin 表情包集中的表情。

## 使用方法

```python
send_sticker(sticker_id: int)
```

### 参数

- `sticker_id` (int): 表情编号 (1-24)

### 示例

```python
# 发送开心的表情
send_sticker(1)

# 发送傲娇的表情
send_sticker(7)

# 发送害羞的表情
send_sticker(20)
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
| 15 | 🤔🌀😵‍💫😵 | 思考/困惑 |
| 16 | 🎧🕺🪩 | 派对/音乐 |
| 17 | 🙂😏👀 | 围观/吃瓜 |
| 18 | 😱😭 | 崩溃/大哭 |
| 19 | 🫨🤹🤡 | 混乱/小丑 |
| 20 | 😳🙈💗🥺💕 | 害羞/心动 |
| 21 | ✨🎭⚡🎉 | 庆祝/魔法 |
| 22 | 😪🥱😴 | 困/睡觉 |
| 23 | 👊💥😤 | 生气/抗议 |
| 24 | 🪼 | 水母/神秘 |

## 依赖

- Telegram Bot API
- 需要配置 `TELEGRAM_BOT_TOKEN` 环境变量

## 使用方法

### 命令行调用

```bash
# 发送表情
TELEGRAM_BOT_TOKEN=YOUR_TOKEN python send_sticker.py <sticker_id> <chat_id>

# 列出所有表情
python send_sticker.py list
```

### 在对话中使用

当 Ava 想要发送表情时，会调用 `send_sticker` 技能，传入表情编号。

## 注意事项

- 表情编号必须在 1-24 范围内
- 需要先在 Telegram 上创建 Bot 并获取 Token
- 通过 @BotFather 创建 Bot 并获取 Token
- 将 Token 添加到环境变量或配置文件中
