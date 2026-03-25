# Module Spec: bus_console_listener — Bus Console 监听器（Phase 2.5）

> 状态：🔶 待迁移
> 优先级：Phase 2.5
> 预估工时：1.5h

---

## 1. 模块职责

为 nanobot 的消息总线（MessageBus）添加 Console 监听机制，支持通过 WebSocket 将异步任务结果实时推送到 Web Console 前端。

### 核心能力
- **监听器注册/注销**：动态管理 Console WebSocket 连接的监听器
- **事件分发**：将消息总线事件选择性转发到已注册的 Console 监听器
- **实时推送**：异步任务结果通过 WebSocket 实时推送到前端

---

## 2. 源文件位置

| 类型 | 路径 |
|------|------|
| 源码（feat/0.0.1） | `nanobot/bus/queue.py`（+43 行变更） |
| 计划实现位置 | `cafeext/bus/console_listener.py` |
| Patch 文件 | `cafeext/patches/bus_patch.py`（新建） |

---

## 3. 拦截点设计

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `MessageBus` 类 | 属性注入 + 方法添加 | 为 MessageBus 添加 console listener 管理方法 |
| `MessageBus.publish` | 方法包装 | 在消息发布时同时分发到 console listener |

### 拦截逻辑

1. 在 `MessageBus` 类上注入 `_console_listeners` 属性（listener 字典）
2. 添加三个方法：
   - `register_console_listener(ws_id, callback)` — 注册 WebSocket 监听器
   - `unregister_console_listener(ws_id)` — 注销监听器
   - `dispatch_to_console_listener(event)` — 分发事件到所有已注册监听器
3. 包装 `publish` 方法，在原始发布逻辑之后调用 `dispatch_to_console_listener()`

---

## 4. 接口设计

```python
# 注入到 MessageBus 的方法

def register_console_listener(
    self,
    ws_id: str,
    callback: Callable[[dict], Awaitable[None]],
) -> None:
    """注册一个 Console WebSocket 监听器

    Args:
        ws_id: WebSocket 连接标识符
        callback: 异步回调函数，接收事件字典
    """
    ...

def unregister_console_listener(self, ws_id: str) -> None:
    """注销一个 Console WebSocket 监听器"""
    ...

async def dispatch_to_console_listener(self, event: dict) -> None:
    """将事件分发到所有已注册的 Console 监听器

    单个监听器失败不影响其他监听器。
    """
    ...

def apply_bus_patch() -> str:
    """为 MessageBus 添加 Console listener 机制"""
    ...
```

---

## 5. 依赖关系

### 上游依赖
- `nanobot.bus.queue.MessageBus` — 拦截目标

### Sidecar 内部依赖
- `cafeext.console.app` — Console 子应用，WebSocket 端点的消费者
- `cafeext.patches.console_patch` — 依赖 Console 已挂载

### 外部依赖
- `asyncio` — 异步事件分发

---

## 6. 关键实现细节

### 6.1 Listener 生命周期
- WebSocket 连接建立时注册 listener
- WebSocket 连接断开时注销 listener
- 注册/注销由 Console WebSocket 端点管理

### 6.2 事件过滤
- 不是所有消息总线事件都需要推送到 Console
- 可考虑在 `dispatch_to_console_listener` 中增加事件类型过滤

### 6.3 错误隔离
- 单个 listener 回调失败（如 WebSocket 已断开）不影响其他 listener
- 失败的 listener 自动清理

### 6.4 与 console_patch 的关系
- `console_patch` 负责挂载 Console 子应用
- `bus_patch` 负责连接消息总线和 Console
- 两者配合实现完整的实时推送链路

---

## 7. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 注册 listener | 注册后在 `_console_listeners` 中可查到 |
| 注销 listener | 注销后不再接收事件 |
| 事件分发 | publish 触发后所有 listener 收到事件 |
| 错误隔离 | 一个 listener 异常不影响其他 listener |
| 重复注册 | 同一 ws_id 重复注册覆盖旧回调 |
| 无 listener | 无注册 listener 时 publish 正常工作 |
| 异步安全 | 并发注册/注销/分发不产生竞态 |
| 拦截点缺失 | MessageBus 不存在时优雅降级 |
