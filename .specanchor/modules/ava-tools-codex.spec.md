---
specanchor:
  level: module
  module_name: "Codex 工具"
  module_path: "ava/tools/codex.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-04-04"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "按 SpecAnchor 最新 Module Spec 模板重生，合并 legacy spec 与当前代码扫描结果"
  status: "active"
  depends_on:
    - "nanobot/agent/tools/base.py"
    - "ava/agent/bg_tasks.py"
---

# Codex 工具 (codex_tool)

## 1. 模块职责
- *设计原则：独立工具 + 共享基础设施**
- claude_code 和 codex 是两个独立工具，各自保留完整的能力和特性
- LLM 看到两个工具的签名，可根据任务特征自主选择
- BackgroundTaskStore 是统一的异步任务管理层，两个工具共享

## 2. 业务规则
- 注意：Codex 没有 sync 模式——所有调用默认异步（通过 BackgroundTaskStore）。
- 工具签名是 agent 合同，参数名和返回形态变更必须同步 patch、console 与 task spec
- 涉及长时任务时优先走 BackgroundTaskStore，而不是在 tool 内部维护孤立状态
- 尽量记录 token / media / audit 辅助信息，但缺失依赖时要优雅降级

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `CodexTool` | `class` | Run OpenAI Codex CLI to run code tasks in background. |
| `CodexTool.execute()` | `execute(prompt: str, project_path: str | None = None, mode: str = 'standard', **kwargs) -> str` | 公共方法 |
| `CodexTool.cancel()` | `cancel(task_id: str) -> str` | 公共方法 |
| `TimelineEvent` | `class` | 核心类 |
| `TaskSnapshot` | `class` | 核心类 |
| `BackgroundTaskStore` | `class` | 统一后台任务注册/状态机/timeline/持久化/digest。 |
| `BackgroundTaskStore.record_event()` | `record_event(task_id: str, event: str, detail: str = '') -> None` | 通用事件记录接口（供 cron/subagent observer 使用）。 |
| `BackgroundTaskStore.cancel()` | `cancel(task_id: str) -> str` | 公共方法 |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| _MAX_OUTPUT_CHARS | module | 模块级共享状态或常量 |
| _HEAD_CHARS | module | 模块级共享状态或常量 |
| _TAIL_CHARS | module | 模块级共享状态或常量 |
| _CODEX_SUBCMD | module | 模块级共享状态或常量 |
| TaskStatus | module | 模块级共享状态或常量 |
| _MAX_CONTINUATION_BUDGET | module | 模块级共享状态或常量 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- 保持 Tool.name / description / parameters 与实际执行路径一致
- CLI / runner / provider 不可用时返回可诊断错误，而不是让调用方悬空等待
- 与 console 或 patch 共享上下文时，用显式注入字段而不是隐式全局变量

## 5. 已知约束 & 技术债
- [ ] 待工具实现后，在 ava/templates/TOOLS.md 中添加：
- [ ] 补一个可调用的后台任务状态/等待工具面，而不是依赖 /task
- [ ] 评估是否需要为 loop 层提供“伪阻塞”等待语义：

## 6. TODO
- [ ] 新增参数、返回字段或异步模式后，立即同步 Spec 和调用链说明 @ZiyanLin
- [ ] 补齐针对成功路径、失败路径和降级路径的窄测试 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/tools/codex.py`
- **核心链路**: 工具注册 → tool.execute() → 运行时执行器/CLI/runner → 结构化结果返回
- **数据流**: Agent tool call → 参数校验 → 执行主链路 → 结果/状态写回聊天或后台任务
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/tools/codex.py` | 模块主入口 |
| `ava/agent/bg_tasks.py` | 关联链路文件 |
- **外部依赖**: `nanobot/agent/tools/base.py`、`ava/agent/bg_tasks.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-tools-codex.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
