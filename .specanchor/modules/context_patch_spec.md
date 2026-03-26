# Module Spec: context_patch — 历史处理与记忆注入

> 文件：`ava/patches/context_patch.py`
> 状态：✅ 已实现（Phase 3）

---

## 1. 模块职责

拦截 `ContextBuilder.build_messages()`，在消息列表构建过程中应用历史摘要、历史压缩和分类记忆注入。

### 处理流程
```
原始 history → HistorySummarizer.summarize() → HistoryCompressor.compress()
    → 原始 build_messages() → 注入 CategorizedMemory 到系统提示词 → 返回
```

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `ContextBuilder.build_messages` | 方法替换 | 在 history 传入原始方法前应用摘要+压缩，在返回前注入记忆 |

### 拦截详情

- **原始行为**：`build_messages(self, history, current_message, **kwargs)` 构建 `[system, ...history, user]` 消息列表
- **修改后行为**：
  1. 通过 `self._agent_loop` 获取 summarizer/compressor/categorized_memory
  2. 对 history 依次应用 summarize → compress
  3. 调用原始 build_messages
  4. 若有分类记忆且 channel/chat_id 存在，追加到系统提示词末尾
- **幂等保护**：`_ava_patched` 标记防止重复应用

---

## 3. 依赖关系

### 上游依赖
- `nanobot.agent.context.ContextBuilder` — 拦截目标

### Sidecar 内部依赖
- `ava.patches.loop_patch` — 提供 `self.context._agent_loop` 反向引用
- `ava.agent.history_summarizer.HistorySummarizer` — 通过 `_agent_loop.history_summarizer` 访问
- `ava.agent.history_compressor.HistoryCompressor` — 通过 `_agent_loop.history_compressor` 访问
- `ava.agent.categorized_memory.CategorizedMemoryStore` — 通过 `_agent_loop.categorized_memory` 访问

---

## 4. 关键实现细节

### 4.1 AgentLoop 反向引用
- `loop_patch` 在 `patched_init` 末尾设置 `self.context._agent_loop = self`
- `context_patch` 通过 `getattr(self, "_agent_loop", None)` 安全访问
- 若引用不存在（未应用 loop_patch），所有增强逻辑静默跳过

### 4.2 错误隔离
- summarizer/compressor/memory 每步独立 try/except
- 任何一步失败不影响后续步骤和原始 build_messages 调用

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| Patch 应用 | 返回描述字符串 |
| _ava_patched 标记 | 标记设置正确 |
| 幂等性 | 二次调用返回 "skipped" |
| Summarizer 调用 | _agent_loop.history_summarizer.summarize() 被调用 |
| Compressor 调用 | _agent_loop.history_compressor.compress() 被调用 |
| 记忆注入 | 系统提示词中包含 "Personal Memory" + 记忆内容 |
| 无 _agent_loop | 原始行为不受影响 |
