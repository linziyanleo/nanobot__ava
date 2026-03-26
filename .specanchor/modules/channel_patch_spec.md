# Module Spec: channel_patch — 消息批处理

> 文件：`ava/patches/channel_patch.py`
> 状态：✅ 已实现（Phase 1 创建，Phase 2 修复，Phase 3 职责精简）

---

## 1. 模块职责

为 Telegram 消息发送增加批处理能力（合并短时间内的多条回复）。

> **注意**：Session Backfill 逻辑已移至 `storage_patch.py`（在 SQLite load 之后执行），
> 解决了 channel_patch 与 storage_patch 对 `SessionManager._load` 的冲突问题。

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `TelegramChannel.send` | 方法替换 | 消息批处理 |

### 拦截详情

- **原始行为**：`TelegramChannel.send(self, msg)` 立即发送单条消息
- **修改后行为**：将消息加入 `MessageBatcher`，等待 1 秒超时窗口，合并同一 chat_id 的多条消息后统一发送
- **实例引用**：通过 `_channel_instance["ref"]` 闭包字典保存 `self` 引用，供 batcher 回调使用
- **回调机制**：`batched_send_callback` 构造 `OutboundMessage` 并调用 `original_send(instance, msg)`

---

## 3. 依赖关系

### 上游依赖
- `nanobot.channels.telegram.TelegramChannel` — 消息发送拦截目标
- `nanobot.bus.events.OutboundMessage` — 消息数据结构

### Sidecar 内部依赖
- `ava.channels.batcher.MessageBatcher` — 批处理器实现
- `ava.launcher.register_patch` — 自注册机制

---

## 4. 关键实现细节

### 4.1 Batcher 生命周期
- Batcher 实例通过 `nonlocal` 闭包变量延迟创建（首次发送时初始化）
- 超时窗口：1.0 秒
- 按 `chat_id` 分组合并消息
- `patched_send` 是 `async def`，直接 `await batcher.add()`

### 4.2 实例引用传递
- 使用 `_channel_instance: dict = {}` 闭包字典存储 `TelegramChannel` 实例
- `patched_send` 在每次调用时更新 `_channel_instance["ref"] = self`
- `batched_send_callback` 通过 `_channel_instance.get("ref")` 获取实例来调用原始 `send`

### 4.3 防御性编程
- `patched_send` 使用 `getattr(msg, "media", None)` 等防御性访问

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 消息合并 | 1 秒内的多条消息被合并为一条发送 |
| 单条透传 | 单条消息在超时后正常发送 |
| chat_id 隔离 | 不同 chat_id 的消息独立批处理 |
| 实例引用 | `_channel_instance["ref"]` 正确保存 TelegramChannel 实例 |
| Batcher 延迟初始化 | 首次发送前 batcher 为 None |
| 幂等性 | 多次调用不重复包装 |
