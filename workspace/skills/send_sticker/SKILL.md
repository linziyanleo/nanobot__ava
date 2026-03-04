---
name: send-sticker
description: Send Telegram stickers from the sticker pack. Use when Nanobot wants to express emotions visually or add playful reactions to messages.
---

# send_sticker

发送 Telegram 表情包（Sticker）。已内置为 agent 工具，对话中直接调用即可。

## 使用方法

```
send_sticker(sticker_id: int, chat_id?: str)
```

**参数说明**：

- `sticker_id` (int, 必填): 表情数字编号
- `chat_id` (str, 可选): Telegram 聊天 ID，不传时自动使用当前会话的 chat context

## 示例

```
send_sticker(sticker_id=4)              # 发送打招呼表情到当前聊天
send_sticker(sticker_id=14, chat_id="12345678")  # 发送爱心到指定聊天
```

## 注意事项

- 仅支持 Telegram 渠道
- 表情编号和对应的 emoji 映射由配置文件定义，模型会自动读取配置获取可用表情列表
- 使用前确保已配置表情包信息（配置文件路径：`~/.nanobot/sticker.json`）
- 根据对话情绪自然选择表情，建议在对话末尾添加以增强表达效果
