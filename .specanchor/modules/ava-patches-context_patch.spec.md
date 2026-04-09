---
specanchor:
  level: module
  module_name: "上下文构建 Patch"
  module_path: "ava/patches/context_patch.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-03-26"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "按 SpecAnchor 最新 Module Spec 模板重生，合并 legacy spec 与当前代码扫描结果"
  status: "active"
  depends_on:
    - "ava/launcher.py"
    - "ava/agent/history_summarizer.py"
    - "ava/agent/history_compressor.py"
    - "ava/agent/bg_tasks.py"
---

# 上下文构建 Patch (context_patch)

## 1. 模块职责
- 拦截 `ContextBuilder.build_messages()`，在发送给 LLM 之前执行历史摘要、历史压缩和分类记忆注入。
- 保留无 LLM 开销的同步处理路径，避免把短期聚焦机制依赖到额外模型调用。
- 对非 Claude provider 补齐 trailing assistant / 协议兼容清洗。

## 2. 业务规则
- 保留原始方法引用并打 patched 标记，重复 apply 不得产生副作用
- 目标拦截点不存在时必须 warning + skip，不能静默失败
- 补丁逻辑优先收敛在入口/出口层，避免把 sidecar 规则深入写进上游中段实现

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `sanitize_messages()` | `sanitize_messages(messages: list[dict]) -> list[dict]` | Remove trailing assistant messages and merge consecutive same-role messages. |
| `apply_context_patch()` | `apply_context_patch() -> str` | 公共函数 |
| `HistorySummarizer` | `class` | Summarize old conversation turns to save tokens. |
| `_Turn` | `class` | 核心类 |
| `HistoryCompressor` | `class` | Compress history by recency + lightweight relevance under a char budget. |
| `TimelineEvent` | `class` | 核心类 |
| `TaskSnapshot` | `class` | 核心类 |
| `BackgroundTaskStore` | `class` | 统一后台任务注册/状态机/timeline/持久化/digest。 |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| enabled | instance | HistorySummarizer 运行时字段 |
| protect_recent | instance | HistorySummarizer 运行时字段 |
| tool_result_max_chars | instance | HistorySummarizer 运行时字段 |
| max_chars | instance | HistoryCompressor 运行时字段 |
| recent_turns | instance | HistoryCompressor 运行时字段 |
| min_recent_turns | instance | HistoryCompressor 运行时字段 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.agent.context.ContextBuilder
- nanobot.providers.base.LLMProvider
- ava.patches.loop_patch — 提供 self.context._agent_loop 反向引用
- ava.agent.history_summarizer.HistorySummarizer

## 5. 已知约束 & 技术债
- [ ] 二次 apply 必须返回 `skipped`，不能重复包装 `build_messages` 和 provider 清洗逻辑。

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/context_patch.py`
- **核心链路**: `context_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/context_patch.py` | 模块主入口 |
| `ava/agent/history_summarizer.py` | 关联链路文件 |
| `ava/agent/history_compressor.py` | 关联链路文件 |
| `ava/agent/bg_tasks.py` | 关联链路文件 |
- **外部依赖**: `ava/launcher.py`、`ava/agent/history_summarizer.py`、`ava/agent/history_compressor.py`、`ava/agent/bg_tasks.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-context_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
