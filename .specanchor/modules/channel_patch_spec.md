# Module Spec: channel_patch — 消息批处理与 Session Backfill

> 文件：`cafeext/patches/channel_patch.py`
> 状态：✅ 已实现（Phase 1）

---

## 1. 模块职责

为 Telegram 消息发送增加批处理能力（合并短时间内的多条回复），并为 Session 加载增加历史消息回填（修复缺失的消息对）。

本模块包含**两个独立的 patch**，打包在同一个文件中：
1. **消息批处理器**（Message Batcher）— 合并碎片化回复
2. **Session Backfill**（历史回填）— 修复不完整的消息历史

---

## 2. 拦截点列表

| 拦截点 | 类型 | 功能域 |
|--------|------|--------|
| `TelegramChannel._send_message` | 方法替换 | 消息批处理 |
| `SessionManager._load` | 方法替换 | Session Backfill |

### 2.1 消息批处理拦截

- **原始行为**：`TelegramChannel._send_message(self, msg)` 立即发送单条消息
- **修改后行为**：将消息加入 `MessageBatcher`，等待 1 秒超时窗口，合并同一 chat_id 的多条消息后统一发送
- **原始方法保留**：存储为 `TelegramChannel._original_send_message`，供 batcher 回调使用

### 2.2 Session Backfill 拦截

- **原始行为**：`SessionManager._load(self, key)` 从存储加载 session 数据
- **修改后行为**：加载后调用 `_backfill_messages()` 检查并修复消息历史中缺失的占位符消息，归一化消息格式
- **修复内容**：插入缺失的 placeholder 消息、归一化消息结构

---

## 3. 依赖关系

### 上游依赖
- `nanobot.channels.telegram.TelegramChannel` — 消息发送拦截目标
- `nanobot.session.manager.SessionManager` — Session 加载拦截目标
- `nanobot.config.paths.get_workspace_path` — 工作区路径
- `nanobot.bus.events.OutboundMessage` — 消息数据结构

### Sidecar 内部依赖
- `cafeext.channels.batcher.MessageBatcher` — 批处理器实现
- `cafeext.session.backfill_turns.backfill_workspace_sessions` — 工作区级回填
- `cafeext.session.backfill_turns._backfill_messages` — 消息级回填
- `cafeext.launcher.register_patch` — 自注册机制

---

## 4. 关键实现细节

### 4.1 Batcher 生命周期
- Batcher 实例通过 `nonlocal` 闭包变量延迟创建（首次发送时初始化）
- 超时窗口：1.0 秒
- 按 `chat_id` 分组合并消息
- 使用 `asyncio.create_task()` 异步加入队列

### 4.2 Backfill 逻辑
- 在每次 `_load()` 返回后检查消息列表
- 统计插入的 placeholder 数量和归一化的消息数量
- 修改是就地（in-place）的，直接更新 `session.messages`

---

## 5. 注意事项

- **Patch 冲突**：`storage_patch.py` 也 patch 了 `SessionManager._load`。执行顺序很重要——`storage_patch` 先执行（替换存储后端），`channel_patch` 后执行（在加载后追加 backfill 逻辑）
- **异步上下文**：`patched_send_message` 使用 `asyncio.create_task()`，调用方必须在 asyncio 事件循环中

---

## 6. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 消息合并 | 1 秒内的多条消息被合并为一条发送 |
| 单条透传 | 单条消息在超时后正常发送 |
| chat_id 隔离 | 不同 chat_id 的消息独立批处理 |
| Backfill 插入 | 缺失 placeholder 消息被正确插入 |
| Backfill 归一化 | 消息结构被归一化 |
| 无需修复 | 完整的消息历史不被修改 |
| Patch 顺序 | 与 `storage_patch` 的交互正确 |
| Batcher 延迟初始化 | 首次发送前 batcher 为 None |
