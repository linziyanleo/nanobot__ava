---
specanchor:
  level: task
  task_name: "Console 实时数据流增强：即时落库 + Event Bus + Token Stats 提前记录"
  author: "@fanghu"
  created: "2026-04-03"
  status: "draft"
  last_change: "初始化 task spec"
  related_modules:
    - ".specanchor/modules/loop_patch_spec.md"
    - ".specanchor/modules/bus_console_listener_spec.md"
    - ".specanchor/modules/console_patch_spec.md"
    - ".specanchor/modules/storage_patch_spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "refactor/sidecar"
---

# SDD Spec: Console 实时数据流增强

## 0. Open Questions

- [x] 非 Console 会话实时推送用 WebSocket 还是 SSE？→ WebSocket，与现有 Console 架构保持一致
- [x] Token Stats 预记录用 INSERT + UPDATE 还是 INSERT 新行？→ INSERT Phase 0 预记录，LLM 完成后 UPDATE 同一行
- [x] Event Bus 是否复用现有 bus_patch 的 MessageBus listener？→ 不复用，新建独立 Event Bus 组件
- [x] 对话历史结构化展示形式？→ 气泡式渲染（类似 Chat 页面的消息列表）

## 1. Requirements (Context)

- **Goal**: 解决 Telegram 消息到达后 Console Chat 页面和 Token Stats 页面无法实时更新的问题。通过即时落库、进程内 Event Bus 和 WebSocket 推送，实现非 Console 会话的实时感知。
- **In-Scope**:
  1. **即时落库**：Telegram 消息到达时，user message 在 LLM 调用前立即写入 `session_messages` 表
  2. **Event Bus**：新增进程内事件总线 `ava/console/services/event_bus.py`，解耦事件生产与消费
  3. **Observe WebSocket**：新增 `/api/chat/ws/observe/{session_key}` 端点，为非 Console 会话提供实时事件推送
  4. **Token Stats 提前记录**：LLM 调用前写入 Phase 0 预记录（含 user_message、system_prompt、conversation_history），LLM 完成后 UPDATE 填入 token 数值
  5. **对话历史结构化展示**：Token Stats 页面的 conversation_history 从 JSON 改为气泡式渲染
  6. **前端实时化**：Chat 页面非 Console 会话从 10s 轮询改为 observe WS 实时更新
- **Out-of-Scope**:
  - 修改 `nanobot/` 目录（零上游污染）
  - Page Agent 在 Chat 页面内嵌展示（Spec B 单独处理）
  - 修改现有 `bus_patch.py` 的 MessageBus listener 机制
  - Token Stats API 端点签名变更

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

### 3.1 Event Bus（新增组件）

**文件**：`ava/console/services/event_bus.py`

```python
class EventBus:
    """进程内事件总线，基于 asyncio.Queue 广播。"""

    def subscribe(self, channel: str, callback: Callable[[dict], None]) -> Callable[[], None]:
        """订阅 channel，返回 unsubscribe 函数。"""

    def publish(self, channel: str, event: dict) -> None:
        """向 channel 的所有订阅者广播事件。"""

# 模块级单例
_bus: EventBus | None = None

def get_event_bus() -> EventBus:
    """获取全局 EventBus 单例。"""
```

- channel 命名规则：`session:{session_key}`
- 每个 subscriber 持有独立 `asyncio.Queue(maxsize=200)`
- publish 遍历所有 subscriber 的 queue，`put_nowait`，满时丢弃并 warning
- subscribe 返回 unsubscribe callable，调用后从列表移除

**事件类型**：

| type | 触发时机 | payload |
|------|---------|---------|
| `message_arrived` | user message 落库后 | `{session_key, role, content, timestamp}` |
| `processing_started` | LLM 调用开始 | `{session_key, model}` |
| `token_recorded` | token_usage 写入/更新后 | `{session_key, record_id, phase}` |
| `turn_completed` | 整个 turn 保存完成 | `{session_key, message_count}` |

### 3.2 即时落库（loop_patch 改造）

**文件**：`ava/patches/loop_patch.py`

在 `patched_process_message` 中，LLM 调用前新增两步：

**Step 1：提前写入 user message 到 session_messages**

```python
# 在 _process_message 拦截中，获取 session 后、LLM 调用前：
# 1. 将 user message 追加到 session.messages（内存）
user_entry = {
    "role": "user",
    "content": msg.content,
    "timestamp": datetime.now().isoformat(),
}
session.messages.append(user_entry)

# 2. 调用 storage_patch 的增量保存，仅写入这一条新消息
self.sessions.save(session)

# 3. 广播事件
event_bus.publish(f"session:{sk}", {
    "type": "message_arrived",
    "session_key": sk,
    "role": "user",
    "content": msg.content[:500],
    "timestamp": user_entry["timestamp"],
})
```

**兼容性处理**：提前落库时在 session 对象上设置标记 `session._user_msg_pre_saved = True`。`_save_turn` 在 append user message 前检查此标记：若为 True 则跳过 user message 的 append（因为已在内存和 DB 中），并重置标记。这比基于内容比较更可靠。

**Step 2：写入 Phase 0 token_usage 预记录**

```python
phase0_id = token_stats.record(
    model=self.model,
    provider=provider_name,
    usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    session_key=sk,
    user_message=msg.content[:1000],
    system_prompt=getattr(self, "_last_system_prompt", ""),
    conversation_history=json.dumps(session.get_history(10), ensure_ascii=False),
    finish_reason="pending",
    model_role="pending",
)
self._phase0_record_id = phase0_id

event_bus.publish(f"session:{sk}", {
    "type": "token_recorded",
    "session_key": sk,
    "record_id": phase0_id,
    "phase": "pending",
})
```

**Step 3：LLM 调用开始时广播**

```python
event_bus.publish(f"session:{sk}", {
    "type": "processing_started",
    "session_key": sk,
    "model": self.model,
})
```

**Step 4：LLM 完成后，UPDATE Phase 0 记录**

现有 `_record_immediately` 改为：若 `self._phase0_record_id` 存在，UPDATE 该记录（填入 prompt_tokens、completion_tokens、cached_tokens、finish_reason 等），而不是 INSERT 新行。后续工具调用产生的额外 LLM 调用仍 INSERT 新行（保持现有逻辑）。

### 3.3 storage_patch 兼容

**文件**：`ava/patches/storage_patch.py`

`patched_save` 的增量策略（`start_seq = db_count`）天然兼容提前写入：

- 提前写入 user message 后 `db_count` 增加 1
- `_save_turn` 再次调用 `sessions.save` 时，增量保存只写入 assistant/tool 消息
- 无需修改 `patched_save` 逻辑，但需要确保 `_save_turn` 不重复 append user message

### 3.4 Observe WebSocket 端点

**文件**：`ava/console/routes/chat_routes.py`

```python
@router.websocket("/ws/observe/{session_key:path}")
async def observe_ws(websocket: WebSocket, session_key: str):
    """只读 WebSocket，订阅 Event Bus 推送非 Console 会话的实时事件。"""
    await websocket.accept()
    bus = get_event_bus()
    queue = asyncio.Queue(maxsize=200)

    def on_event(event: dict):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

    unsub = bus.subscribe(f"session:{session_key}", on_event)

    try:
        async def sender():
            while True:
                event = await queue.get()
                await websocket.send_text(json.dumps(event, ensure_ascii=False))

        async def receiver():
            while True:
                await websocket.receive_text()  # 保持连接

        sender_task = asyncio.create_task(sender())
        try:
            await receiver()
        finally:
            sender_task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        unsub()
```

### 3.5 前端 Chat 页面改造

**文件**：`console-ui/src/pages/ChatPage/index.tsx`

非 Console 会话的更新策略从轮询改为 observe WS：

```typescript
// 当 activeSession 不是 console:* 前缀时
if (!activeSession.startsWith('console:')) {
  const ws = new WebSocket(`/api/chat/ws/observe/${encodeURIComponent(activeSession)}`)

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)

    if (msg.type === 'message_arrived') {
      // 追加临时 user bubble（带 pending 标记）
      appendPendingMessage(msg)
    } else if (msg.type === 'processing_started') {
      // 显示 typing indicator
      setProcessing(true)
    } else if (msg.type === 'turn_completed') {
      // 拉取完整消息列表，替换临时 bubble
      setProcessing(false)
      loadSessionMessages(activeSession)
    }
  }
}
```

- 保留 `SESSION_LIST_POLL_MS = 30_000` 会话列表轮询（会话列表变更频率低，轮询足够）
- 移除 `MESSAGE_POLL_MS = 10_000` 的消息轮询（被 observe WS 替代）

### 3.6 Token Stats 对话历史结构化展示

**新增文件**：`console-ui/src/pages/TokenStatsPage/ConversationHistoryView.tsx`

```typescript
interface ConversationHistoryViewProps {
  historyJson: string  // JSON 数组字符串
}

export default function ConversationHistoryView({ historyJson }: Props) {
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
- 在 Token Stats 详情面板中，`conversation_history` 字段替换为此组件

### 3.7 Token Stats pending 状态展示

Token Stats 页面中，`model_role = "pending"` 的记录显示为：
- 状态标签：橙色 "Processing..." badge
- 已填字段正常显示（user_message、system_prompt、conversation_history）
- token 数值字段显示 "—"（而非 0）
- LLM 完成后自动刷新（通过 `token_recorded` 事件触发前端刷新）

## 4. File Changes Summary

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `ava/console/services/event_bus.py` | **新增** | 进程内 Event Bus 单例（~60 行） |
| `ava/patches/loop_patch.py` | 修改 | 提前落库 + Phase 0 token 预记录 + Event Bus 触发 |
| `ava/patches/storage_patch.py` | 验证 | 确认增量策略兼容，预期无需修改 |
| `ava/console/routes/chat_routes.py` | 修改 | 新增 observe WS 端点 |
| `ava/console/services/token_stats_service.py` | 修改 | record() 返回 record_id + 支持 UPDATE 模式 |
| `console-ui/src/pages/ChatPage/index.tsx` | 修改 | 非 Console 会话走 observe WS |
| `console-ui/src/pages/TokenStatsPage/ConversationHistoryView.tsx` | **新增** | 对话历史气泡式渲染 |
| `console-ui/src/pages/TokenStatsPage/` 相关 | 修改 | 集成结构化展示 + pending 状态 |

## 5. Implementation Checklist

- [ ] 1. 新增 `ava/console/services/event_bus.py`，实现 EventBus 单例
- [ ] 2. 修改 `loop_patch.py`：`patched_process_message` 中 LLM 调用前提前将 user message 写入 session_messages
- [ ] 3. 修改 `loop_patch.py`：LLM 调用前写入 Phase 0 token_usage 预记录
- [ ] 4. 修改 `loop_patch.py`：在 4 个关键时点触发 Event Bus 事件
- [ ] 5. 修改 `loop_patch.py`：`_record_immediately` 支持 UPDATE Phase 0 记录
- [ ] 6. 修改 `token_stats_service.py`：`record()` 返回 record_id，新增 `update_record()` 方法
- [ ] 7. 验证 `storage_patch.py` 的增量保存与提前写入兼容（预期无需改动）
- [ ] 8. 修改 `chat_routes.py`：新增 `/api/chat/ws/observe/{session_key}` 端点
- [ ] 9. 修改 `ChatPage/index.tsx`：非 Console 会话连接 observe WS，移除 MESSAGE_POLL_MS 轮询
- [ ] 10. 新增 `ConversationHistoryView.tsx`：对话历史气泡式渲染组件
- [ ] 11. 修改 Token Stats 页面：集成 ConversationHistoryView + pending 状态展示
- [ ] 12. 编写测试：Event Bus subscribe/publish/unsubscribe
- [ ] 13. 编写测试：loop_patch 提前落库 + Phase 0 记录
- [ ] 14. 编写测试：observe WS 端点事件推送
- [ ] 15. 端到端验证：Telegram 消息到达 → Chat 页面实时显示 → Token Stats 实时更新

## 6. Test Coverage

| 测试场景 | 验证内容 |
|----------|----------|
| Event Bus 基础功能 | subscribe → publish → callback 触发；unsubscribe 后不再接收 |
| Event Bus 队列满 | maxsize 达到时丢弃并 warning，不阻塞 publish |
| 提前落库 | _process_message 开始后、LLM 调用前，session_messages 已有 user message |
| 增量保存兼容 | 提前写入后 _save_turn 不重复写入 user message |
| Phase 0 预记录 | LLM 调用前 token_usage 表有 finish_reason="pending" 的记录 |
| Phase 0 UPDATE | LLM 完成后 Phase 0 记录被 UPDATE，prompt_tokens 等非 0 |
| Observe WS 连接 | 连接 → 收到 message_arrived 事件 → 断开后 unsubscribe |
| 前端实时更新 | message_arrived → 临时 bubble 出现；turn_completed → 完整消息替换 |
| 对话历史渲染 | JSON 解析 → user/assistant/tool 分角色渲染，截断和展开正常 |
| pending 状态 | model_role="pending" 的记录显示橙色 badge + token 字段为 "—" |

## 7. Execute Log

（待实现时填写）

## 8. Review Verdict

（待 Review 时填写）

## 9. Risks & Mitigations

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 提前落库后 _save_turn 重复写入 user message | session_messages 出现重复消息 | _save_turn 中检测最后一条消息是否已是同一 user message |
| Event Bus 内存泄漏 | 长期运行后内存增长 | subscriber queue 有 maxsize；unsubscribe 时清理 |
| Phase 0 记录未被 UPDATE（LLM 异常退出） | token_usage 中残留 pending 记录 | 在 _process_message 的 except/finally 中处理，将 pending 标记为 error |
| storage_patch 增量策略假设被打破 | 消息写入错乱 | 充分测试增量保存路径，必要时在 patched_save 中加防御 |
