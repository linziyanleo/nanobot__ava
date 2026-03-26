# Module Spec: history_summarizer — 历史摘要器

> 状态：🟡 已复制到 `ava/agent/history_summarizer.py`，未接入 AgentLoop
> 原始来源：`feat/0.0.1` 分支 `nanobot/agent/history_summarizer.py`（+174 行）

---

## 1. 模块职责

轮级历史摘要系统。将旧轮次的对话压缩为简洁的 `[user, assistant]` 消息对摘要，保留最近消息的原始格式，减少上下文占用。

### 核心能力
- **轮次摘要**：将旧轮次压缩为 `[user, assistant]` 消息对
- **最近保留**：最近 N 条消息保持原始格式不变
- **特殊处理**：
  - 定时任务触发的消息特殊标记
  - 贴纸 emoji 保留
  - Cron 任务 ID 保留

---

## 2. 文件位置

| 类型 | 路径 |
|------|------|
| 当前实现 | `ava/agent/history_summarizer.py` ✅ 已复制 |
| Patch 文件（待创建） | `ava/patches/history_patch.py`（与 history_compressor 共用） |

---

## 3. 接入方案（下一步）

与 `HistoryCompressor` 共用 patch 入口。调用链：

```
原始消息 → HistorySummarizer.summarize() → HistoryCompressor.compress() → 最终消息列表
```

### 拦截点

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `AgentLoop._build_messages` | 方法包装（与 compressor 共用） | 在消息列表构建时应用摘要逻辑 |

---

## 4. 依赖关系

### 上游依赖
- `nanobot.agent.loop.AgentLoop._build_messages` — 拦截目标（与 compressor 共用）

### Sidecar 内部依赖
- `ava.agent.history_compressor.HistoryCompressor` — 协作关系（摘要 → 压缩）

### 外部依赖
- 无（纯 Python 标准库）

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 最近消息保留 | 最近 N 条消息不被摘要 |
| 旧轮次摘要 | 旧轮次正确压缩为 user/assistant 对 |
| 定时任务标记 | Cron 触发的消息被正确标记 |
| 贴纸 emoji | 贴纸 emoji 在摘要中保留 |
| Cron ID 保留 | 任务 ID 在摘要中保留 |
| 消息不足 | 消息数少于 recent_count 时原样返回 |
| 与 compressor 协作 | 摘要后的消息可被 compressor 正确处理 |
