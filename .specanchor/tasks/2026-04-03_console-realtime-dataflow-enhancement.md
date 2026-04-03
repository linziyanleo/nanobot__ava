---
specanchor:
  level: task
  task_name: "Console 实时数据流增强：实时广播 + Observe WS + Token Stats Phase 0 预记录"
  author: "@fanghu"
  created: "2026-04-03"
  status: "draft"
  last_change: "根据 Codex review 修正 4 个硬伤：WS 鉴权、hook 点选择、conversation_history 定义、Token Stats 刷新闭环"
  related_modules:
    - ".specanchor/modules/loop_patch_spec.md"
    - ".specanchor/modules/bus_console_listener_spec.md"
    - ".specanchor/modules/console_patch_spec.md"
    - ".specanchor/modules/storage_patch_spec.md"
    - ".specanchor/global/global-patch-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "refactor/sidecar"
---

# SDD Spec: Console 实时数据流增强

## 0. Open Questions

- [x] 非 Console 会话实时推送用 WebSocket 还是 SSE？→ WebSocket，与现有 Console 架构保持一致
- [x] Token Stats 预记录用 INSERT + UPDATE 还是 INSERT 新行？→ INSERT Phase 0 预记录，LLM 完成后 UPDATE 同一行
- [x] Event Bus 是否复用现有 bus_patch 的 MessageBus listener？→ **复用并扩展** bus_patch，添加 observe listener 注册方法，不新建独立 Event Bus
- [x] 对话历史结构化展示形式？→ 气泡式渲染（类似 Chat 页面的消息列表）
- [x] 稳定 hook 点选择：在哪里触发"消息到达"广播和 Phase 0 预记录？→ `patched_run_agent_loop` 开头（此时 slash command 已过、`build_messages` 已调用，`initial_messages` 和 `session` 均可用），而非 `patched_process_message`；turn 完成广播在 `patched_process_message` 中 `original` 返回后
- [x] conversation_history 记录的是什么？→ `initial_messages`（`build_messages()` 输出，经过 summarize + compress + 记忆注入的真实 LLM context），**不是** `session.get_history(10)`
- [x] Token Stats 页面实时刷新方式？→ 增加 auto-refresh 轮询（pending 记录存在时 5s 间隔），不引入额外 WS 端点；后续可升级为 WS 推送
- [x] 是否做提前落库（user message 在 LLM 调用前写入 session_messages 表）？→ **不做**，改为实时广播。理由：提前落库需要在 slash command dispatch 之后、build_messages 之前插入逻辑，这要求复制 `_process_message` 大段内部流程，违反 global-patch-spec §1.2 最小拦截原则。改为通过 MessageBus 广播事件 + 前端临时 pending bubble 实现实时感知

## 1. Requirements (Context)

- **Goal**: 解决 Telegram 消息到达后 Console Chat 页面和 Token Stats 页面无法实时更新的问题。通过即时落库、进程内 Event Bus 和 WebSocket 推送，实现非 Console 会话的实时感知。
- **In-Scope**:
  1. **实时广播**：Telegram 消息到达并通过 slash command 判断后，通过 MessageBus 广播 `message_arrived` 事件，前端显示临时 pending bubble（不做提前落库，避免违反最小拦截原则）
  2. **扩展 MessageBus**：在 `ava/patches/bus_patch.py` 中为 MessageBus 添加 observe listener 机制（`register_observe_listener` / `unregister_observe_listener` / `dispatch_observe_event`），复用现有 session_key 管理基础设施
  3. **Observe WebSocket**：新增 `/api/chat/ws/observe/{session_key}` 端点（含 JWT 鉴权，复用 `auth.get_ws_user`），为非 Console 会话提供实时事件推送
  4. **Token Stats 提前记录**：LLM 调用前写入 Phase 0 预记录（含 user_message、system_prompt、initial_messages 形式的真实 LLM context），LLM 完成后 UPDATE 填入 token 数值
  5. **对话历史结构化展示**：Token Stats 页面的 conversation_history 从 JSON 改为气泡式渲染
  6. **前端实时化**：Chat 页面非 Console 会话从 10s 轮询改为 observe WS 实时更新；Token Stats 页面增加 auto-refresh 轮询
- **Out-of-Scope**:
  - 修改 `nanobot/` 目录（零上游污染）
  - Page Agent 在 Chat 页面内嵌展示（Spec B 单独处理）
  - Token Stats API 端点签名变更
  - user message 提前写入 session_messages 表（不做提前落库）

### 1.1 Context Sources

- Requirement Source:
  - 用户反馈：Telegram 消息到达后 `_process_message` 日志已输出，但消息未写入 nanobot.db，Chat 页面无法同步
  - 用户要求：消息到达时立即在 Chat 页面显示 + Processing 状态；Token Stats 立即记录用户消息和完整上下文
- Design Refs:
  - `.specanchor/modules/loop_patch_spec.md`
  - `.specanchor/modules/bus_console_listener_spec.md`
  - `.specanchor/modules/storage_patch_spec.md`
  - `.specanchor/tasks/fix-token-stats-recording.md`
- Code Refs:
  - `ava/patches/loop_patch.py` — 当前 token 统计拦截逻辑
  - `ava/patches/storage_patch.py` — `patched_save` 增量保存策略
  - `ava/console/routes/chat_routes.py` — 现有 WebSocket 端点
  - `console-ui/src/pages/ChatPage/index.tsx` — 前端消息轮询逻辑
  - `console-ui/src/pages/TokenStatsPage/` — Token 统计展示

## 2. Research Findings

### 问题根因：消息批量延迟落库

当前消息写入流程：
```
T0  Telegram 消息到达
T1  _process_message 开始（日志输出 "Processing message"）
T2  构建 LLM 输入、调用 LLM（3 秒 ~ 数分钟）
T3  LLM 返回 → _record_immediately 写入 token_usage（user_message="" 空）
T4  _save_turn → session.messages.append（内存）
T5  sessions.save → storage_patch.patched_save → INSERT session_messages + commit
```

**核心问题**：用户消息在 T5 才写入 DB，而 T2→T5 之间可能有数分钟延迟。Chat 页面的 10s 轮询在 T0→T5 期间查不到任何新消息。

### Token Stats 记录时机

- T3（LLM 返回后）才 INSERT token_usage，此时 user_message="" 空
- T5 之后才回填 user_message 和 output_content
- system_prompt 和 conversation_history 在 T3 已可用但未完整传递

### Chat 页面更新机制

- Console 会话（`console:*`）：WebSocket 双向，实时推送
- 非 Console 会话（`telegram:*` 等）：`MESSAGE_POLL_MS = 10_000` 轮询 + `SESSION_LIST_POLL_MS = 30_000`
- 无事件驱动机制，完全依赖定时拉取

## 3. Design

### 3.1 扩展 MessageBus observe listener（bus_patch 改造）

**文件**：`ava/patches/bus_patch.py`

**为什么不新建 `event_bus.py`**：bus_patch 已经为 MessageBus 实现了按 `session_key` 管理 listener queue 的基础设施（`register_console_listener` / `unregister_console_listener`），参见 `bus_console_listener_spec.md`。新建独立 Event Bus 等于造第二套 session event system，增加维护负担且两套机制的生命周期管理容易冲突。

在现有 `apply_bus_patch()` 中追加 3 个方法注入：

```python
def register_observe_listener(self: MessageBus, session_key: str) -> asyncio.Queue:
    """注册 observe listener queue，接收生命周期事件（dict）。
    与 console_listener（接收 OutboundMessage）平行，互不干扰。
    """
    if not hasattr(self, "_observe_listeners"):
        self._observe_listeners: dict[str, list[asyncio.Queue]] = {}
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    self._observe_listeners.setdefault(session_key, []).append(queue)
    return queue

def unregister_observe_listener(self: MessageBus, session_key: str, queue: asyncio.Queue) -> None:
    """移除指定的 observe listener queue。"""
    listeners = getattr(self, "_observe_listeners", {})
    if session_key in listeners:
        try:
            listeners[session_key].remove(queue)
        except ValueError:
            pass
        if not listeners[session_key]:
            del listeners[session_key]

def dispatch_observe_event(self: MessageBus, session_key: str, event: dict) -> None:
    """向指定 session_key 的所有 observe listener 广播生命周期事件。"""
    listeners = getattr(self, "_observe_listeners", {})
    for queue in listeners.get(session_key, []):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Observe listener queue full for {}, dropping event", session_key)
```

**与 console_listener 的区别**：

| 维度 | console_listener | observe_listener |
|------|-----------------|------------------|
| 数据类型 | `OutboundMessage` | `dict`（生命周期事件） |
| 每 session 数量 | 1 个（覆盖式注册） | N 个（追加式，支持多页面同时观察） |
| 用途 | Console WS 双向会话推送 | 非 Console 会话只读事件订阅 |

**事件类型**：

| type | 触发位置 | payload |
|------|---------|---------|
| `message_arrived` | `patched_run_agent_loop` 开头 | `{session_key, role, content, timestamp}` |
| `processing_started` | `patched_run_agent_loop` 开头 | `{session_key, model}` |
| `token_recorded` | `patched_run_agent_loop` 开头（Phase 0） + `_record_immediately`（UPDATE） | `{session_key, record_id, phase}` |
| `turn_completed` | `patched_process_message` 中 `original` 返回后 | `{session_key, message_count}` |

### 3.2 实时广播 + Phase 0 预记录（loop_patch 改造）

**文件**：`ava/patches/loop_patch.py`

#### 为什么不做提前落库

原始方案"LLM 调用前将 user message 写入 session_messages"需要在 slash command dispatch 之后、`build_messages()` 之前插入逻辑。但 upstream `_process_message` 的内部流程是：

```
L548  session = self.sessions.get_or_create(key)
L554  slash command dispatch → 可能直接 return
L559  memory_consolidator.maybe_consolidate_by_tokens
L566  history = session.get_history(max_messages=0)
L567  initial_messages = self.context.build_messages(...)
L582  _run_agent_loop(initial_messages, session=session, ...)
L595  _save_turn + sessions.save
```

`patched_process_message` 只能在 `original_process_message()` 的外层 wrap，无法在 L554 和 L566 之间插入逻辑——除非复制整段 `_process_message`。这与 `global-patch-spec.md` §1.2 最小拦截原则冲突，也与 `TODO.md` 关于 loop_patch 热区判断的警告冲突。

#### 稳定 hook 点选择

**`patched_run_agent_loop` 开头**是理想 hook 点：

- **slash command 已过**：`_run_agent_loop` 在 slash command dispatch 之后才被调用，不存在"写入了不该写的消息"的风险
- **`initial_messages` 可用**：这是 `build_messages()` 的输出，即经过 `context_patch` 的 summarize + compress + 记忆注入后的**真实 LLM context**
- **`session` 可用**：upstream 通过 keyword arg `session=session` 传入
- **已有拦截**：`patched_run_agent_loop` 已经在做 provider 方法拦截（`intercepted_chat` / `intercepted_chat_stream`），追加逻辑自然

**`patched_process_message` 中 `original` 返回后**适合触发 `turn_completed`：此时 `_save_turn` + `sessions.save` 已完成，DB 中消息已持久化。

#### 实现草图

**在 `patched_run_agent_loop` 开头，`original_run_agent_loop` 调用前**：

```python
async def patched_run_agent_loop(self: AgentLoop, initial_messages, **kwargs):
    # === 新增：实时广播 + Phase 0 预记录 ===
    session = kwargs.get('session')
    sk = getattr(self, '_current_session_key', '') or ''
    user_msg = getattr(self, '_current_user_message', '') or ''

    if sk and user_msg:
        bus = self.bus

        # 1. 广播 message_arrived（前端显示临时 pending bubble）
        bus.dispatch_observe_event(sk, {
            "type": "message_arrived",
            "session_key": sk,
            "role": "user",
            "content": user_msg[:500],
            "timestamp": datetime.now().isoformat(),
        })

        # 2. 写入 Phase 0 token_usage 预记录
        token_stats = getattr(self, 'token_stats', None)
        if token_stats:
            # conversation_history 使用 initial_messages（真实 LLM context）
            conversation_history = json.dumps(
                [{"role": m.get("role", ""), "content": str(m.get("content", ""))[:200]}
                 for m in initial_messages if m.get("role") != "system"],
                ensure_ascii=False,
            )
            provider_name = type(self.provider).__name__.lower().replace("provider", "")
            phase0_id = token_stats.record(
                model=self.model,
                provider=provider_name,
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                session_key=sk,
                user_message=user_msg[:1000],
                system_prompt=getattr(self, "_last_system_prompt", ""),
                conversation_history=conversation_history,
                finish_reason="pending",
                model_role="pending",
            )
            self._phase0_record_id = phase0_id
            bus.dispatch_observe_event(sk, {
                "type": "token_recorded",
                "session_key": sk,
                "record_id": phase0_id,
                "phase": "pending",
            })

        # 3. 广播 processing_started
        bus.dispatch_observe_event(sk, {
            "type": "processing_started",
            "session_key": sk,
            "model": self.model,
        })

    # === 现有逻辑：provider 方法拦截 ===
    original_chat = self.provider.chat_with_retry
    # ... (现有 intercepted_chat / _record_immediately 逻辑保持不变)
```

**在现有 `_record_immediately` 中**：若 `self._phase0_record_id` 存在且为第一次 LLM 调用（`iteration == 0`），UPDATE Phase 0 记录而非 INSERT 新行。后续工具调用的 LLM 调用仍 INSERT（保持现有逻辑）。

**在 `patched_process_message` 中，`original` 返回后**：

```python
async def patched_process_message(self, msg, session_key=None, ...):
    # ... 设置上下文（保持不变）
    result = await original_process_message(...)

    # === 新增：广播 turn_completed（此时 _save_turn + sessions.save 已完成）===
    sk = getattr(self, '_current_session_key', '') or ''
    if sk:
        session = self.sessions.get_or_create(sk) if sk else None
        self.bus.dispatch_observe_event(sk, {
            "type": "turn_completed",
            "session_key": sk,
            "message_count": len(session.messages) if session else 0,
        })

    # ... backfill token stats（保持不变）
    return result
```

### 3.3 storage_patch 兼容

**文件**：`ava/patches/storage_patch.py`

本方案不做提前落库，user message 仍在 `_save_turn` → `sessions.save` → `patched_save` 的原有链路中写入 DB。`patched_save` 的增量策略不受影响，**无需修改**。

### 3.4 Observe WebSocket 端点

**文件**：`ava/console/routes/chat_routes.py`

**关键变更**：复用 `auth.get_ws_user` 鉴权（与现有 `chat_ws` 端点一致），复用 bus_patch 的 observe listener。

```python
@router.websocket("/ws/observe/{session_key:path}")
async def observe_ws(websocket: WebSocket, session_key: str):
    """只读 WebSocket，订阅 MessageBus observe listener 推送非 Console 会话的实时事件。"""
    # 鉴权（复用现有 WS 鉴权契约）
    user = await auth.get_ws_user(websocket)
    await websocket.accept()

    svc_chat = _get_chat_service()
    bus = svc_chat._agent.bus
    queue = bus.register_observe_listener(session_key)

    try:
        async def sender():
            while True:
                event = await queue.get()
                await websocket.send_text(json.dumps(event, ensure_ascii=False))

        async def receiver():
            while True:
                await websocket.receive_text()

        sender_task = asyncio.create_task(sender())
        try:
            await receiver()
        finally:
            sender_task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        bus.unregister_observe_listener(session_key, queue)
```

### 3.5 前端 Chat 页面改造

**文件**：`console-ui/src/pages/ChatPage/index.tsx`

非 Console 会话的更新策略从轮询改为 observe WS。**使用 `wsUrl()` 构造带 token 的 WS URL**（复用现有鉴权契约，与 `client.ts` line 47 的 `wsUrl` 函数一致）：

```typescript
// 当 activeSession 不是 console:* 前缀时
if (!activeSession.startsWith('console:')) {
  // 复用 wsUrl()，自动拼接 ?token=xxx 鉴权参数
  const ws = new WebSocket(wsUrl(`/chat/ws/observe/${encodeURIComponent(activeSession)}`))

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)

    if (msg.type === 'message_arrived') {
      appendPendingMessage(msg)
    } else if (msg.type === 'processing_started') {
      setProcessing(true)
    } else if (msg.type === 'turn_completed') {
      setProcessing(false)
      loadSessionMessages(activeSession)
    }
  }

  ws.onclose = () => {
    // 断线重连（复用现有 wsReconnectTimer 模式）
    wsReconnectTimer.current = setTimeout(() => connectObserveWs(activeSession), 2000)
  }
}
```

- 保留 `SESSION_LIST_POLL_MS = 30_000` 会话列表轮询（变更频率低）
- 移除非 Console 会话的 `MESSAGE_POLL_MS = 10_000` 消息轮询（被 observe WS 替代）
- 刷新页面恢复：连接 observe WS 后立即拉取一次 `/api/chat/messages` 作为初始状态

### 3.6 Token Stats 对话历史结构化展示

**新增组件文件**：`console-ui/src/components/ConversationHistoryView.tsx`

> 注意：`TokenStatsPage` 实际是单文件 `console-ui/src/pages/TokenStatsPage.tsx`（非目录），所以将此组件放在 `components/` 下作为通用组件。

```typescript
interface ConversationHistoryViewProps {
  historyJson: string
}

export default function ConversationHistoryView({ historyJson }: ConversationHistoryViewProps) {
  const messages = JSON.parse(historyJson)
  return (
    <div className="space-y-2 max-h-[400px] overflow-y-auto">
      {messages.map((msg, i) => (
        <div key={i} className={msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
          {msg.role === 'user' && <UserBubble content={msg.content} />}
          {msg.role === 'assistant' && <AssistantBubble content={msg.content} />}
          {msg.role === 'tool' && <ToolCallCard name={msg.name} content={msg.content} />}
        </div>
      ))}
    </div>
  )
}
```

- `UserBubble`：右对齐，蓝色背景，内容超 200 字截断 + "展开"按钮
- `AssistantBubble`：左对齐，灰色背景，支持 markdown 渲染
- `ToolCallCard`：折叠卡片，显示工具名，展开看参数和结果
- 在 `TokenStatsPage.tsx` 的详情面板中，`conversation_history` 字段替换为此组件

### 3.7 Token Stats pending 状态展示 + 刷新闭环

**文件**：`console-ui/src/pages/TokenStatsPage.tsx`

**pending 状态展示**（`model_role = "pending"` 的记录）：
- 状态标签：橙色 "Processing..." badge
- 已填字段正常显示（user_message、system_prompt、conversation_history）
- token 数值字段显示 "—"（而非 0）

**刷新闭环设计**（当前 Spec 阶段用轮询，后续可升级为 WS）：

```typescript
const AUTO_REFRESH_MS = 5_000

useEffect(() => {
  // 检测是否存在 pending 记录，存在则启动 auto-refresh
  const hasPending = records.some(r => r.model_role === 'pending')
  if (!hasPending) return

  const timer = setInterval(() => {
    loadRecords(page)
  }, AUTO_REFRESH_MS)

  return () => clearInterval(timer)
}, [records, page, loadRecords])
```

- **谁触发刷新**：前端自身检测 pending 记录存在时启动 5s 间隔自动轮询
- **怎么停止**：当没有 pending 记录时（LLM 完成后 Phase 0 记录已被 UPDATE），轮询自动停止
- **掉线/刷新恢复**：页面加载时初始拉取会包含 pending 记录，自动进入 auto-refresh 模式
- **不引入额外 WS 端点**：Token Stats 是跨 session 的聚合视图，按 session_key 的 observe WS 不适用；全局 WS 端点的 ROI 不足以在本迭代引入

## 4. File Changes Summary

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `ava/patches/bus_patch.py` | 修改 | 新增 observe listener 三方法注入（`register/unregister/dispatch_observe_event`） |
| `ava/patches/loop_patch.py` | 修改 | `patched_run_agent_loop` 开头增加实时广播 + Phase 0 预记录；`patched_process_message` 增加 turn_completed 广播；`_record_immediately` 支持 UPDATE Phase 0 |
| `ava/patches/storage_patch.py` | 不变 | 不做提前落库，增量策略不受影响 |
| `ava/console/routes/chat_routes.py` | 修改 | 新增 observe WS 端点（含 `auth.get_ws_user` 鉴权） |
| `ava/console/services/token_stats_service.py` | 修改 | `record()` 返回 record_id + 新增 `update_record()` 方法 |
| `console-ui/src/pages/ChatPage/index.tsx` | 修改 | 非 Console 会话走 observe WS（使用 `wsUrl()` 带 token） |
| `console-ui/src/components/ConversationHistoryView.tsx` | **新增** | 对话历史气泡式渲染组件 |
| `console-ui/src/pages/TokenStatsPage.tsx` | 修改 | 集成 ConversationHistoryView + pending 状态 + auto-refresh |

## 5. Implementation Checklist

- [ ] 1. 修改 `bus_patch.py`：添加 `register_observe_listener` / `unregister_observe_listener` / `dispatch_observe_event` 方法注入
- [ ] 2. 修改 `loop_patch.py`：`patched_run_agent_loop` 开头广播 `message_arrived` + `processing_started`
- [ ] 3. 修改 `loop_patch.py`：`patched_run_agent_loop` 开头写入 Phase 0 token_usage 预记录（conversation_history 使用 `initial_messages`）
- [ ] 4. 修改 `loop_patch.py`：`_record_immediately` 支持 UPDATE Phase 0 记录（`iteration == 0` 时）
- [ ] 5. 修改 `loop_patch.py`：`patched_process_message` 中 `original` 返回后广播 `turn_completed`
- [ ] 6. 修改 `token_stats_service.py`：`record()` 返回 record_id，新增 `update_record()` 方法
- [ ] 7. 修改 `chat_routes.py`：新增 `/api/chat/ws/observe/{session_key}` 端点（含 `auth.get_ws_user` 鉴权）
- [ ] 8. 修改 `ChatPage/index.tsx`：非 Console 会话连接 observe WS（使用 `wsUrl()`），移除 MESSAGE_POLL_MS 轮询
- [ ] 9. 新增 `components/ConversationHistoryView.tsx`：对话历史气泡式渲染组件
- [ ] 10. 修改 `TokenStatsPage.tsx`：集成 ConversationHistoryView + pending 状态展示 + auto-refresh 轮询
- [ ] 11. 编写测试：bus_patch observe listener register/unregister/dispatch
- [ ] 12. 编写测试：loop_patch 实时广播 + Phase 0 记录（conversation_history 使用 initial_messages）
- [ ] 13. 编写测试：observe WS 端点鉴权 + 事件推送 + 断开清理
- [ ] 14. 端到端验证：Telegram 消息到达 → Chat 页面实时 pending bubble → turn_completed → 完整消息替换 → Token Stats auto-refresh

## 6. Test Coverage

| 测试场景 | 验证内容 |
|----------|----------|
| observe listener 基础功能 | register → dispatch → queue 收到事件；unregister 后不再接收 |
| observe listener 多订阅者 | 同 session_key 注册多个 queue，dispatch 全部收到 |
| observe listener 队列满 | maxsize 达到时丢弃并 warning，不阻塞 dispatch |
| observe listener 与 console_listener 隔离 | console_listener 不收到 observe 事件，反之亦然 |
| 实时广播时序 | patched_run_agent_loop 开头按 message_arrived → token_recorded(pending) → processing_started 顺序广播 |
| turn_completed 时序 | patched_process_message 中 original 返回后（DB 已保存）广播 turn_completed |
| Phase 0 预记录 | LLM 调用前 token_usage 表有 finish_reason="pending" 的记录，conversation_history 来自 initial_messages |
| Phase 0 UPDATE | 第一次 LLM 调用完成后 Phase 0 记录被 UPDATE，prompt_tokens 等非 0 |
| Phase 0 异常处理 | LLM 异常退出时 Phase 0 记录被标记为 error |
| observe WS 鉴权 | 无 token 连接被拒（WS_1008）；有效 token 连接成功 |
| observe WS 事件推送 | 连接 → dispatch_observe_event → 前端收到 JSON 事件 |
| observe WS 断开清理 | 断开后 queue 从 _observe_listeners 移除 |
| 前端 pending bubble | message_arrived → 临时 bubble 出现；turn_completed → 拉取完整消息替换 |
| Token Stats auto-refresh | 存在 pending 记录时 5s 轮询；全部完成后轮询停止 |
| 对话历史渲染 | JSON 解析 → user/assistant/tool 分角色渲染，截断和展开正常 |

## 7. Execute Log

（待实现时填写）

## 8. Review Verdict

（待 Review 时填写）

## 9. Risks & Mitigations

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 刷新页面丢失 pending 状态 | 用户在 LLM 处理期间刷新页面，看不到 pending bubble | 连接 observe WS 后立即拉取一次消息列表作为初始状态；Phase 0 token_usage 记录可作为"有消息正在处理"的信号 |
| observe listener 内存泄漏 | WS 断开但 unregister 未调用 | finally 块确保 unregister；queue 有 maxsize=200 上限 |
| Phase 0 记录未被 UPDATE（LLM 异常退出） | token_usage 中残留 pending 记录 | 在 patched_process_message 的 except/finally 中处理，将 pending 标记为 error |
| observe listener 与 console_listener 事件混乱 | 两套 listener 注册到同一 session_key 时相互干扰 | 使用独立的 `_observe_listeners` dict，与 `_console_listeners` 完全隔离 |
| Token Stats auto-refresh 轮询频率 | pending 记录多时 5s 轮询增加服务端压力 | 仅当页面可见时启动轮询（`document.visibilityState`）；后续可升级为 WS 推送 |
| initial_messages 序列化过大 | conversation_history 字段存储大量数据 | 每条消息 content 截断到 200 字符，与现有 backfill 逻辑一致 |
