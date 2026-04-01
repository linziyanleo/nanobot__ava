# Module Spec: bus_patch — Bus Console 监听器

> 文件：`ava/patches/bus_patch.py`
> 状态：✅ 已实现（Phase 2）

---

## 1. 模块职责

为 nanobot 的消息总线（MessageBus）添加 Console 监听机制，支持通过 WebSocket 将异步任务结果实时推送到 Web Console 前端。

### 核心能力
- **监听器注册/注销**：按 `session_key` 动态管理 Console WebSocket 连接对应的队列
- **事件分发**：将指定 session 的事件写入已注册队列
- **总线桥接**：包装 `publish_outbound`，自动把 console 消息路由到对应 session 队列

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `MessageBus` 类 | 方法注入 | 添加 3 个新方法到 MessageBus |

### 注入方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `register_console_listener` | `(self, session_key: str) -> asyncio.Queue` | 注册 session 的 WebSocket 监听队列并返回该队列 |
| `unregister_console_listener` | `(self, session_key: str) -> None` | 注销 session 的监听队列 |
| `dispatch_to_console_listener` | `async (self, session_key: str, event: dict) -> None` | 异步将事件写入指定 session 的队列 |
| `publish_outbound` | `async (self, msg: OutboundMessage) -> None` | 保留原始出站行为，并附加 console 队列路由 |

### 实现细节

- 使用 `self._console_listeners: dict` 存储（lazy init，首次 `register` 时创建）
- key 为 `session_key`，value 为 `asyncio.Queue`
- `dispatch_to_console_listener` 使用 `queue.put_nowait(...)` 写入事件
- 队列满时打印 warning 并丢弃消息
- `publish_outbound` 在原始 MessageBus 出站流程之外，额外尝试将 console 相关消息写入注册队列

---

## 3. 依赖关系

### 上游依赖
- `nanobot.bus.queue.MessageBus` — 注入目标

### Sidecar 内部依赖
- `ava.console.app` — Console 子应用的 WebSocket 端点（消费者）
- `ava.launcher.register_patch` — 自注册机制

---

## 4. 与 console_patch 的关系

- `console_patch` 启动 Console uvicorn server（提供 WebSocket 端点）
- `bus_patch` 为 MessageBus 添加 listener 管理方法
- Console WebSocket 端点在连接建立时调用 `bus.register_console_listener()` 获取队列
- Console WebSocket 端点在连接断开时调用 `bus.unregister_console_listener()`
- Console WebSocket 协程消费该队列并向前端转发
- Agent 处理消息时调用 `bus.dispatch_to_console_listener()`，或通过 `publish_outbound` 自动路由进度

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 注册 listener | 注册后返回 `asyncio.Queue` 且在 `_console_listeners` 中可查到 |
| 注销 listener | 注销后不再接收事件 |
| 事件分发 | dispatch 将事件写入已注册队列 |
| 未注册 session | dispatch 到未注册 session_key 静默返回 |
| lazy init | 首次 register 前 `_console_listeners` 不存在 |
| 重复注册 | 同 session_key 重复注册覆盖旧队列 |
| 幂等性 | 多次调用 `apply_bus_patch()` 不产生副作用 |
