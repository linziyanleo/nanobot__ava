---
specanchor:
  level: module
  module_name: "历史压缩器"
  module_path: "ava/agent/history_compressor.py"
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
    - "ava/patches/loop_patch.py"
    - "ava/patches/context_patch.py"
    - "ava/agent/history_summarizer.py"
---

# 历史压缩器 (history_compressor)

## 1. 模块职责
- **字符预算控制**：根据配置的字符预算裁剪历史消息
- **最近轮次保留**：最近 N 轮对话始终保留
- **相关性筛选**：基于轻量级关键词匹配进行相关性评分
- **auto-backfill 识别**：识别并标记自动回填的消息

## 2. 业务规则
- 调用链：原始消息 → HistorySummarizer.summarize() → HistoryCompressor.compress() → 最终消息列表
- 当前由 loop_patch 负责实例注入、context_patch 负责每轮调用，不再是“待接入”状态
- 运行时对象按需初始化，避免 import 时产生重副作用
- 调用方注入的 loop / db / service 缺失时需要可降级

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `_Turn` | `class` | 核心类 |
| `HistoryCompressor` | `class` | Compress history by recency + lightweight relevance under a char budget. |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| max_chars | instance | HistoryCompressor 运行时字段 |
| recent_turns | instance | HistoryCompressor 运行时字段 |
| min_recent_turns | instance | HistoryCompressor 运行时字段 |
| max_old_turns | instance | HistoryCompressor 运行时字段 |
| protected_recent_messages | instance | HistoryCompressor 运行时字段 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.agent.loop.AgentLoop._build_messages — 拦截目标
- ava.agent.history_summarizer.HistorySummarizer — 协作（摘要 → 压缩）
- 标准库 re — 正则表达式用于术语提取

## 5. 已知约束 & 技术债
- [ ] 目前压缩行为只影响发送给 LLM 的视图，不会反写持久化历史；排查问题时要区分“上下文视图”和“落盘历史”。
- [ ] 参数读取仍受 loop_patch / context_patch 的配置回退路径约束，和理想中的 schema 路径尚未完全统一。
- [ ] 若后续更改摘要与压缩的先后顺序，需要同步更新 context_patch 及相关验证用例。

## 6. TODO
- [ ] 按当前 task / execute 计划补齐尚未闭环的实现与验证。 @ZiyanLin
- [ ] 后续实现变更时同步修正文档中的职责、规则与关键文件表 @ZiyanLin
- [ ] 收口当前遗留的集成缺口并补回归验证 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/agent/history_compressor.py`
- **核心链路**: `history_compressor.py` → 核心处理逻辑 → 调用方/上游集成点
- **数据流**: 输入上下文 → 模块处理/存储/压缩 → 输出给调用方或后续链路
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/agent/history_compressor.py` | 模块主入口 |
- **外部依赖**: `(none)`

## 8. 迁移说明
- 本文件由 legacy spec `ava-agent-history_compressor.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
