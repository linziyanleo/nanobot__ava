# Module Spec: bus_patch — Bus Console + Observe 监听器

> 文件：`ava/patches/bus_patch.py`
> 状态：✅ 已实现（Phase 2 + Observe Listener 扩展）

---

## 1. 模块职责

为 nanobot 的消息总线（MessageBus）添加两套监听机制：

### 核心能力
- **Console 监听器**：按 `session_key` 管理 Console WebSocket 的 `OutboundMessage` 队列（覆盖式注册，用于双向会话）
- **Observe 监听器**：按 `session_key` 管理 observe WebSocket 的 `dict` 生命周期事件队列（追加式注册，支持多页面同时观察同一 session）
- **总线桥接**：包装 `publish_outbound`，自动把 console 消息路由到对应 session 队列

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `MessageBus` 类 | 方法注入 | 添加 6 个新方法到 MessageBus（3 console + 3 observe） |

### 注入方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `register_console_listener` | `(self, session_key: str) -> asyncio.Queue` | 注册 session 的 Console WebSocket 监听队列（覆盖式） |
| `unregister_console_listener` | `(self, session_key: str) -> None` | 注销 session 的 Console 监听队列 |
| `dispatch_to_console_listener` | `async (self, session_key: str, event: dict) -> None` | 异步将事件写入指定 session 的 Console 队列 |
| `publish_outbound` | `async (self, msg: OutboundMessage) -> None` | 保留原始出站行为，并附加 console 队列路由 |
| `register_observe_listener` | `(self, session_key: str) -> asyncio.Queue` | 注册 observe listener queue（追加式，同 session 支持多个） |
| `unregister_observe_listener` | `(self, session_key: str, queue: asyncio.Queue) -> None` | 移除指定的 observe listener queue |
| `dispatch_observe_event` | `(self, session_key: str, event: dict) -> None` | 向指定 session 的所有 observe listener 广播生命周期事件 |

### Console Listener 实现细节

- 使用 `self._console_listeners: dict[str, asyncio.Queue]` 存储（lazy init）
- 覆盖式注册：同 session_key 重复注册替换旧队列
- `dispatch_to_console_listener` 使用 `queue.put_nowait(...)` 写入事件
- 队列满时打印 warning 并丢弃消息

### Observe Listener 实现细节

- 使用 `self._observe_listeners: dict[str, list[asyncio.Queue]]` 存储（lazy init）
- 追加式注册：同 session_key 可注册多个 queue（支持多页面同时观察）
- `dispatch_observe_event` 遍历同 session_key 的所有 queue，`put_nowait`
- queue maxsize=200，满时丢弃并 warning
- `unregister` 时从 list 中移除指定 queue；list 为空时删除 key

### Console vs Observe 对比

| 维度 | console_listener | observe_listener |
|------|-----------------|------------------|
| 数据类型 | `OutboundMessage` | `dict`（生命周期事件） |
| 每 session 数量 | 1 个（覆盖式注册） | N 个（追加式） |
| 存储结构 | `dict[str, Queue]` | `dict[str, list[Queue]]` |
| 用途 | Console WS 双向会话推送 | 非 Console 会话只读事件订阅 |

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
| Console: 注册 listener | 注册后返回 `asyncio.Queue` 且在 `_console_listeners` 中可查到 |
| Console: 注销 listener | 注销后不再接收事件 |
| Console: 事件分发 | dispatch 将事件写入已注册队列 |
| Console: 未注册 session | dispatch 到未注册 session_key 静默返回 |
| Console: lazy init | 首次 register 前 `_console_listeners` 不存在 |
| Console: 重复注册 | 同 session_key 重复注册覆盖旧队列 |
| Observe: 注册 listener | 注册后 queue 在 `_observe_listeners[key]` 列表中 |
| Observe: 多订阅者 | 同 session_key 注册多个 queue，dispatch 全部收到 |
| Observe: 注销 listener | 注销指定 queue 后该 queue 不再接收事件 |
| Observe: 注销最后一个 | 最后一个 queue 注销后 key 从 dict 中移除 |
| Observe: 队列满 | maxsize 达到时丢弃并 warning |
| Observe: 与 Console 隔离 | console_listener 不收到 observe 事件，反之亦然 |
| 幂等性 | 多次调用 `apply_bus_patch()` 不产生副作用 |
