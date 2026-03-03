---
name: send-sticker
description: Send Telegram stickers from the ava origin sticker pack. Use when Ava wants to express emotions visually or add playful reactions to messages. Supports 24 different stickers for various emotions (happy, shy, angry, sleepy, etc.).
---

# send_sticker

发送 Telegram 表情包（Sticker）

## 功能描述

根据表情编号发送 ava origin 表情包集中的表情。

## 使用方法

### 方式一：命令行脚本（推荐）

```bash
# 设置环境变量
export TELEGRAM_BOT_TOKEN="your_bot_token"

# 发送表情
python send_sticker.py <sticker_id> <chat_id>

# 示例：发送开心的表情到指定聊天
python send_sticker.py 1 -5172087440

# 列出所有表情
python send_sticker.py list
```

### 方式二：在 nanobot 中使用

```bash
# 通过 nanobot 技能系统调用（自动获取 token 和 chat_id）
nanobot skill send-sticker --sticker_id 1
```

### 参数说明

- `sticker_id` (int): 表情编号 (1-24)
- `chat_id` (str): Telegram 聊天 ID（群聊为负数，私聊为正数）

### 环境变量

- `TELEGRAM_BOT_TOKEN`: Telegram Bot Token（从 config.json 或环境变量获取）

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

- Python 3.6+
- Telegram Bot API（通过 urllib 直接调用，无需额外依赖）
- 需要配置 Telegram Bot Token

## 获取必要信息

### 1. 获取 Bot Token

从 `~/.nanobot/config.json` 中读取：

```json
{
  "telegram": {
    "token": "YOUR_BOT_TOKEN"
  }
}
```

或使用环境变量：

```bash
export TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
```

### 2. 获取 Chat ID

- **私聊**：使用用户的 Telegram ID（正数）
- **群聊**：使用群聊 ID（负数，如 `-5172087440`）

可以通过以下方式获取：
- 查看 nanobot 会话日志
- 使用 @userinfobot 等 Telegram 机器人查询

## 注意事项

- ✅ 表情编号必须在 1-24 范围内
- ✅ 需要先在 Telegram 上创建 Bot 并获取 Token
- ✅ 需要配置网络代理（如果在中国大陆）
- ⚠️ 文档中的 Python 函数调用是伪代码，实际使用命令行脚本
