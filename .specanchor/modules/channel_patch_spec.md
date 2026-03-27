# Module Spec: channel_patch — Telegram 消息批处理与 send_delta 修复

> 文件：`ava/patches/channel_patch.py`
> 状态：✅ 已实现
> 执行顺序：字母序第 4 位（`c`）

---

## 1. 模块职责

为 Telegram 提供两项上游未覆盖的能力：
1. **消息批处理**：1 秒窗口内合并同一 chat_id 的多条回复，减少消息闪烁
2. **send_delta 修复**：补丁两个上游未处理的边界情况

> 语音转录（Groq Whisper）使用上游原生实现（`config.providers.groq.api_key`），本 patch 不再干预。
> stream_id 匹配、not_modified 错误处理已由上游 `33abe915` 覆盖，本 patch 不重复实现。

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `TelegramChannel.send` | 方法替换 | 消息进入 MessageBatcher，1s 后 flush |
| `TelegramChannel.send_delta` | 方法包装 | 修复两个上游边界情况 |

### 2.1 `patched_send`（消息批处理）

- 所有发往 Telegram 的消息先入 `MessageBatcher`（按 chat_id 分组，1.0s 超时）
- Flush 时构造 `OutboundMessage` 调用 `original_send`
- Batcher 延迟初始化（首次发送时创建）
- `_channel_instance["ref"]` 闭包字典保存实例引用供 callback 使用

### 2.2 `patched_send_delta`（边界修复）

**本 patch 额外处理的两种情况**（上游未覆盖）：

| 情况 | 上游行为 | patch 行为 |
|------|----------|------------|
| `_stream_end` 时 buf 为空（工具调用轮无文字输出） | 不调用 `_stop_typing` → typing 指示器卡住 | 无条件先调用 `_stop_typing` |
| `_stream_end` 时 `buf.message_id is None`（send_message 未完成） | 直接 return，消息丢失 | fallback 发一条新消息 |

---

## 3. 依赖关系

### 上游依赖
- `nanobot.channels.telegram.TelegramChannel`
- `nanobot.bus.events.OutboundMessage`
- `nanobot.utils.helpers.strip_think`

### Sidecar 内部依赖
- `ava.channels.batcher.MessageBatcher`

---

## 4. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 消息合并 | 1s 内多条消息合并为一条发送 |
| chat_id 隔离 | 不同 chat_id 独立批处理 |
| stop_typing 修复 | tool-only 轮 stream_end 时 typing 正确停止 |
| message_id=None fallback | buf 有内容但 message_id 未设置时发新消息 |
| 幂等性 | 多次 apply 不重复包装 |
