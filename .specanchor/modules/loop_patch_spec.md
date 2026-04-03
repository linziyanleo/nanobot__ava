# Module Spec: loop_patch — AgentLoop 属性注入与 Token 统计

> 文件：`ava/patches/loop_patch.py`
> 状态：✅ 已实现
> 执行顺序：字母序第 7 位（`l`），在 `context_patch` 之后、`storage_patch` 之前

---

## 1. 模块职责

为 `AgentLoop` 注入 ava 扩展属性，并在每次消息处理后记录完整的 token 使用情况（含缓存命中、当轮新增 tokens、对话历史）。

### 核心能力
- **属性注入**：在 `AgentLoop.__init__` 完成后绑定 db/token_stats/media_service/categorized_memory/history_summarizer/history_compressor
- **Token 统计**：包装 `_run_agent_loop`（拦截 provider 调用获取原始 usage）和 `_process_message`（每轮记录完整字段）
- **Database 共享**：通过 `set_shared_db()` 接收 storage_patch 的共享 Database 实例

> `2026-04-03` 之后的注意点：upstream `AgentLoop` 已新增 `context_block_limit`、`max_tool_result_chars`、`provider_retry_mode` 以及 runtime checkpoint 相关状态面。
> 当前 patch 之所以未被打断，依赖的是 `patched_init(*args, **kwargs)` / `patched_run_agent_loop(..., **kwargs)` 的透传包装；后续若 patch 改成显式签名，必须同步这些字段。

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `AgentLoop.__init__` | 方法包装 | 注入 6 个扩展属性 + back-reference |
| `AgentLoop._set_tool_context` | 方法包装 | 同步更新 StickerTool 的 chat context |
| `AgentLoop._run_agent_loop` | 方法包装 | 拦截 provider.chat_* 捕获完整 usage（cached_tokens、finish_reason 等）|
| `AgentLoop._process_message` | 方法包装 | 记录每轮完整 token 统计 |

### 2.1 `_store_full_usage` 字段说明

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

### 2.2 `patched_process_message` 记录字段

| 字段 | 来源 |
|------|------|
| `prompt_tokens` / `completion_tokens` | `_full_last_usage` |
| `cached_tokens` / `cache_creation_tokens` | `_full_last_usage._cached_tokens` 等（预解析）|
| `current_turn_tokens` | tiktoken 估算 `msg.content` |
| `system_prompt` | `self._last_system_prompt`（context_patch 设置，截 2000 字）|
| `conversation_history` | session.get_history(10) JSON 序列化 |
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
| conversation_history | DB 记录中有最近 session 历史 JSON |
| shared_db | set_shared_db() 后新 AgentLoop 获得共享 db |
| 幂等性 | 多次 apply 不重复包装 |
