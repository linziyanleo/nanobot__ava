# Module Spec: context_patch — 历史处理与记忆注入

> 文件：`ava/patches/context_patch.py`
> 状态：✅ 已实现
> 执行顺序：字母序第 5 位（`c` 后于 `channel`，`con` > `cha`）

---

## 1. 模块职责

拦截 `ContextBuilder.build_messages()`，在构建发给 LLM 的消息列表之前，应用两层无 LLM 开销的历史压缩，并在之后注入分类记忆。

### 处理流程

```
原始 history
  → HistorySummarizer.summarize()   — 折叠旧轮次 tool 结构为紧凑 user/assistant 对
  → HistoryCompressor.compress()    — 按字符预算筛选保留哪些轮次（含相关性评分）
  → original build_messages()       — 上游构建消息列表
  → CategorizedMemory 注入系统提示词
  → 保存 _last_system_prompt 到 loop（供 token_stats 记录）
```

### 与上游 MemoryConsolidator 的关系

| | 上游 MemoryConsolidator | context_patch |
|---|---|---|
| 触发条件 | token 超限（session 级，异步） | 每轮必然执行（同步） |
| 持久化 | 写 MEMORY.md + HISTORY.md | 无（只影响 LLM 视图） |
| 额外 LLM 调用 | 是 | 否 |
| 定位 | 长期遗忘机制 | 短期聚焦机制 |

两者互补，不互斥。

---

## 2. 拦截点

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `ContextBuilder.build_messages` | 方法替换 | 幂等保护：`_ava_patched` 标记 |

---

## 3. 参数配置来源

压缩参数通过 `context._agent_loop` 反向引用从 `AgentLoop` 实例读取：

| 参数 | 来源 | 默认值 |
|------|------|--------|
| Compressor.max_chars | `config.agents.defaults.context_compression.max_chars` | 50000 |
| Compressor.protected_recent_messages | 同上 | 20 |
| Compressor.max_old_turns | 同上 | 6 |
| Summarizer.protect_recent | `config.agents.defaults.history_summarizer.protect_recent` | 6 |
| Summarizer.tool_result_max_chars | 同上 | 400 |

> `max_chars=50000`：中英混合对话约 6000-8000 tokens，避免过于激进的裁剪。
> `protect_recent=6`：保护最近 ~3 轮的完整 tool call 结构不被 Summarizer 折叠。

---

## 4. 依赖关系

### 上游依赖
- `nanobot.agent.context.ContextBuilder`

### Sidecar 内部依赖
- `ava.patches.loop_patch` — 提供 `self.context._agent_loop` 反向引用
- `ava.agent.history_summarizer.HistorySummarizer`
- `ava.agent.history_compressor.HistoryCompressor`
- `ava.agent.categorized_memory.CategorizedMemoryStore`

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| Summarizer 调用 | history_summarizer.summarize() 被调用 |
| Compressor 调用 | history_compressor.compress() 被调用 |
| 记忆注入 | 系统提示词末尾含 "Personal Memory" 段落 |
| 无 _agent_loop | 原始行为不受影响 |
| 幂等性 | 二次 apply 返回 "skipped" |
| 各步独立错误 | summarizer 失败不影响 compressor 和原始 build_messages |
