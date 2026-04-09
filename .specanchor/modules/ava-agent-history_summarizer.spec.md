---
specanchor:
  level: module
  module_name: "历史摘要器"
  module_path: "ava/agent/history_summarizer.py"
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
    - "ava/agent/history_compressor.py"
---

# 历史摘要器 (history_summarizer)

## 1. 模块职责
- **轮次摘要**：将旧轮次压缩为 [user, assistant] 消息对
- **最近保留**：最近 N 条消息保持原始格式不变
- **特殊处理**：保留定时任务标记、贴纸 emoji 和 Cron 任务 ID 等关键上下文

## 2. 业务规则
- 与 HistoryCompressor 组成固定调用链：原始消息 → summarize() → compress() → 最终消息列表
- 当前由 loop_patch 创建实例、context_patch 在 build_messages 期间调用，不再属于“已复制未接入”
- 运行时对象按需初始化，避免 import 时产生重副作用
- 调用方注入的 loop / db / service 缺失时需要可降级
- 跨模块协作以显式依赖为准，不把实现细节藏进隐式全局状态

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `HistorySummarizer` | `class` | Summarize old conversation turns to save tokens. |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| enabled | instance | HistorySummarizer 运行时字段 |
| protect_recent | instance | HistorySummarizer 运行时字段 |
| tool_result_max_chars | instance | HistorySummarizer 运行时字段 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.agent.loop.AgentLoop._build_messages — 拦截目标（与 compressor 共用）
- ava.agent.history_compressor.HistoryCompressor — 协作关系（摘要 → 压缩）
- 无（纯 Python 标准库）

## 5. 已知约束 & 技术债
- [ ] 摘要逻辑只服务于 LLM 上下文视图，不承担持久化、回填或对话归档职责。
- [ ] 参数读取仍沿用 loop_patch / context_patch 的回退逻辑，和理想配置路径存在偏差。
- [ ] 若后续新增特殊消息类型，需要同步更新摘要保留规则和回归用例。

## 6. TODO
- [ ] 按当前 task / execute 计划补齐尚未闭环的实现与验证。 @ZiyanLin
- [ ] 后续实现变更时同步修正文档中的职责、规则与关键文件表 @ZiyanLin
- [ ] 收口当前遗留的集成缺口并补回归验证 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/agent/history_summarizer.py`
- **核心链路**: `history_summarizer.py` → 核心处理逻辑 → 调用方/上游集成点
- **数据流**: 输入上下文 → 模块处理/存储/压缩 → 输出给调用方或后续链路
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/agent/history_summarizer.py` | 模块主入口 |
- **外部依赖**: `(none)`

## 8. 迁移说明
- 本文件由 legacy spec `ava-agent-history_summarizer.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
