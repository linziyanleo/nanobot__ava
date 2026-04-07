# Module Spec: loop_patch — AgentLoop 属性注入、Token 统计与实时广播

> 文件：`ava/patches/loop_patch.py`
> 状态：✅ 已实现（2026-04-07，补 weakref 生命周期约束）
> 执行顺序：字母序第 7 位（`l`），在 `context_patch` 之后、`storage_patch` 之前

---

## 1. 模块职责

为 `AgentLoop` 注入 ava 扩展属性，记录完整的 token 使用情况，并通过 MessageBus 广播消息生命周期事件实现 Console 实时更新。

### 核心能力
- **属性注入**：在 `AgentLoop.__init__` 完成后绑定 db/token_stats/media_service/categorized_memory/history_summarizer/history_compressor
- **Token 统计**：包装 `_run_agent_loop`（拦截 provider 调用获取原始 usage）和 `_process_message`（每轮记录完整字段）
- **Conversation 分段**：为同一 `session_key` 下的逻辑新会话维护 `session.metadata["conversation_id"]`；`/new` 前置轮换新 id，后续 turn 在该 conversation 内重新从 0 编号
- **Phase 0 预记录**：在 `patched_run_agent_loop` 开头（LLM 调用前）写入 pending 状态的 token_usage 记录，首次 LLM 调用完成后 UPDATE 填入真实数值
- **实时广播**：通过 `bus.dispatch_observe_event()` 广播 `message_arrived` / `processing_started` / `token_recorded` / `turn_completed` 四类生命周期事件
- **Database 共享**：通过 `set_shared_db()` 接收 storage_patch 的共享 Database 实例
- **弱引用回指**：模块级 `_agent_loop_ref` 仅保存最近 loop 的 `weakref.ref`，供 console_patch “尽量获取当前 loop”，但不延长 `AgentLoop` 生命周期

> `2026-04-03` 之后的注意点：upstream `AgentLoop` 已新增 `context_block_limit`、`max_tool_result_chars`、`provider_retry_mode` 以及 runtime checkpoint 相关状态面。
> 当前 patch 之所以未被打断，依赖的是 `patched_init(*args, **kwargs)` / `patched_run_agent_loop(..., **kwargs)` 的透传包装；后续若 patch 改成显式签名，必须同步这些字段。

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `AgentLoop.__init__` | 方法包装 | 注入 6 个扩展属性 + back-reference |
| `AgentLoop._set_tool_context` | 方法包装 | 同步更新 StickerTool 的 chat context |
| `AgentLoop._run_agent_loop` | 方法包装 | 开头广播 message_arrived + Phase 0 预记录 + processing_started；拦截 provider.chat_*；首次 LLM 调用 UPDATE Phase 0 |
| `AgentLoop._save_turn` | 方法包装 | 修正 skip 与 compressed history 的不匹配 |
| `AgentLoop._process_message` | 方法包装 | 记录每轮完整 token 统计 + turn 完成后广播 turn_completed + Phase 0 异常处理 |

### 2.1 实时广播事件

| 事件类型 | 触发位置 | payload |
|----------|---------|---------|
| `message_arrived` | `patched_run_agent_loop` 开头 | `{session_key, role, content, timestamp}` |
| `processing_started` | `patched_run_agent_loop` 开头 | `{session_key, model}` |
| `token_recorded` | Phase 0 写入 / UPDATE 时 | `{session_key, record_id, phase}` |
| `turn_completed` | `patched_process_message` 中 original 返回后 | `{session_key, message_count}` |

### 2.2 Phase 0 预记录

在 `patched_run_agent_loop` 开头（此时 slash command 已过、`build_messages` 已调用），写入一条 `finish_reason="pending"`, `model_role="pending"` 的 token_usage 记录。`conversation_history` 使用 `initial_messages`（经过 context_patch summarize + compress 后的真实 LLM context），不是 `session.get_history(10)`。

首次 LLM 调用完成后（`_record_immediately` 中 `iteration == 0`），UPDATE 该记录填入真实 token 数值。LLM 异常退出时，在 `patched_process_message` 的 except 块中将记录标记为 `finish_reason="error"`, `model_role="error"`。

### 2.3 `_store_full_usage` 字段说明

```python
loop._full_last_usage = {
    "prompt_tokens": ...,
    "completion_tokens": ...,
    "total_tokens": ...,
    "_cached_tokens": ...,       # 前缀 _ 表示预解析，传给 record() 跳过二次解析
    "_cache_creation_tokens": ...,
    "finish_reason": ...,
}
```

### 2.4 `patched_process_message` 记录字段

| 字段 | 来源 |
|------|------|
| `conversation_id` | `self._current_conversation_id`（来自 `session.metadata["conversation_id"]`；`/new` 会前置轮换） |
| `prompt_tokens` / `completion_tokens` | `_full_last_usage` |
| `cached_tokens` / `cache_creation_tokens` | `_full_last_usage._cached_tokens` 等（预解析）|
| `current_turn_tokens` | tiktoken 估算 `msg.content` |
| `system_prompt` | `self._last_system_prompt`（context_patch 设置，截 2000 字）|
| `conversation_history` | Phase 0: initial_messages JSON 序列化（真实 LLM context）；backfill: 不再覆盖（Phase 0 已有） |
| `user_message` | `msg.content`（截 1000 字）|
| `output_content` | `result.content`（截 4000 字）|

---

## 3. Database 共享机制

```python
_shared_db = None  # 由 storage_patch 调用 set_shared_db() 设置

def _get_or_create_db(workspace_path):
    if _shared_db is not None:
        return _shared_db
    return Database(get_data_dir() / "nanobot.db")  # fallback
```

执行顺序：`loop_patch`（l）先于 `storage_patch`（s），首次用 fallback db，storage_patch 运行后通过 `set_shared_db()` 替换为共享 db。

### 3.1 Console 回指语义

```python
_agent_loop_ref = weakref.ref(self)

def get_agent_loop():
    return _agent_loop_ref() if _agent_loop_ref is not None else None
```

- `console_patch` 仍可拿到“最近一个还活着的 loop”
- 若旧 `AgentLoop` 已被 GC，`get_agent_loop()` 返回 `None`
- 该回指只用于观测/桥接，不承担生命周期管理职责

---

## 4. 依赖关系

### 上游依赖
- `nanobot.agent.loop.AgentLoop`
- `nanobot.utils.helpers.estimate_prompt_tokens`（当轮 token 估算）

### Sidecar 内部依赖
- `ava.storage.Database`
- `ava.console.services.token_stats_service.TokenStatsCollector`
- `ava.console.services.media_service.MediaService`
- `ava.agent.categorized_memory.CategorizedMemoryStore`
- `ava.agent.history_summarizer.HistorySummarizer`
- `ava.agent.history_compressor.HistoryCompressor`

### 被依赖
- `storage_patch` → `set_shared_db()`
- `tools_patch` → `self.token_stats`、`self.media_service`、`self.db`
- `context_patch` → `self.context._agent_loop`（back-reference）

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 属性注入 | 实例拥有 db/token_stats/media_service/categorized_memory/summarizer/compressor |
| cached_tokens 修复 | DB 记录中 cached_tokens 非 0（Anthropic 缓存命中时）|
| current_turn_tokens | DB 记录中有合理的 tiktoken 估算值 |
| conversation_history | DB 记录中有 initial_messages 序列化的真实 LLM context |
| record() 返回 id | token_stats.record() 返回插入行的 id |
| update_record() | update_record() 更新指定字段，拒绝未知字段 |
| Phase 0 预记录 | LLM 调用前 token_usage 表有 finish_reason="pending" 的记录 |
| Phase 0 UPDATE | 首次 LLM 调用后 pending 记录被 UPDATE |
| Phase 0 异常 | LLM 异常时 pending 记录被标记为 error |
| `/new` conversation 轮换 | slash `/new` 后 `session.metadata["conversation_id"]` 被刷新，下一条普通消息从新 conversation 的 Turn #0 开始 |
| 同序号 turn 不串线 | 同一 `session_key` 下旧 `conversation_id` 的 Turn #0 与 `/new` 后新 `conversation_id` 的 Turn #0 分开聚合 |
| 实时广播时序 | message_arrived → token_recorded(pending) → processing_started → turn_completed |
| shared_db | set_shared_db() 后新 AgentLoop 获得共享 db |
| weakref 回指 | `get_agent_loop()` 在 loop 存活时返回实例，被 GC 后返回 `None` |
| 幂等性 | 多次 apply 不重复包装 |
