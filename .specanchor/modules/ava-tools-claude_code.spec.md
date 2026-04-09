---
specanchor:
  level: module
  module_name: "Claude Code 工具"
  module_path: "ava/tools/claude_code.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-04-04"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "按 SpecAnchor 最新 Module Spec 模板重生，合并 legacy spec 与当前代码扫描结果"
  status: "review"
  depends_on:
    - "nanobot/agent/tools/base.py"
    - "nanobot/agent/loop.py"
    - "ava/launcher.py"
    - "ava/tools/__init__.py"
    - "ava/agent/bg_tasks.py"
    - "ava/patches/tools_patch.py"
---

# Claude Code 工具 (claude_code_tool)

## 1. 模块职责
- **同步执行链**：封装 Claude Code CLI 调用、标准输出裁剪和结构化结果返回。
- **取消能力**：提供 task cancel 入口，供上层在 runner 或后台任务模式下统一终止执行。
- **待收口边界**：异步后台任务链、任务状态透出、IM 上下文注入、完成回调落盘仍未完全闭环。
- **不负责**：console 展示协议、后台任务总线和跨渠道通知分发，这些能力应由外层 patch / store 统一承担。

## 2. 业务规则
- 工具签名是 agent 合同，参数名和返回形态变更必须同步 patch、console 与 task spec
- 涉及长时任务时优先走 BackgroundTaskStore，而不是在 tool 内部维护孤立状态
- 尽量记录 token / media / audit 辅助信息，但缺失依赖时要优雅降级

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `ClaudeCodeTool` | `class` | Run Claude Code CLI to modify code, add features, fix bugs, or analyze a codebase. |
| `ClaudeCodeTool.execute()` | `execute(prompt: str, project_path: str | None = None, mode: str = 'standard', session_id: str | None = None, **kwargs) -> str` | 公共方法 |
| `ClaudeCodeTool.cancel()` | `cancel(task_id: str) -> str` | Cancel a running Claude Code task. |
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
| cc_config | instance | ClaudeCodeTool 运行时字段 |
| TaskStatus | module | 模块级共享状态或常量 |
| _MAX_CONTINUATION_BUDGET | module | 模块级共享状态或常量 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- 主路径：config.tools.claude_code（fork schema）
- nanobot.agent.tools.base.Tool
- nanobot.agent.loop.AgentLoop
- ava/patches/tools_patch.py

## 5. 已知约束 & 技术债
- [ ] 当前状态为 `review`；同步执行链可用，但后台任务模式仍未形成完整产品闭环。
- [ ] 异步后台任务链、任务状态透出、IM 上下文注入、完成回调落盘仍需补齐。
- [ ] 若工具签名或返回结构变化，需要同步 `tools_patch`、console 链路和相关 task spec。

## 6. TODO
- [ ] 按当前 task / execute 计划补齐尚未闭环的实现与验证。 @ZiyanLin
- [ ] 新增参数、返回字段或异步模式后，立即同步 Spec 和调用链说明 @ZiyanLin
- [ ] 补齐针对成功路径、失败路径和降级路径的窄测试 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/tools/claude_code.py`
- **核心链路**: 工具注册 → tool.execute() → 运行时执行器/CLI/runner → 结构化结果返回
- **数据流**: Agent tool call → 参数校验 → 执行主链路 → 结果/状态写回聊天或后台任务
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/tools/claude_code.py` | 模块主入口 |
| `ava/agent/bg_tasks.py` | 关联链路文件 |
| `ava/patches/tools_patch.py` | 关联链路文件 |
| `ava/patches/context_patch.py` | 关联链路文件 |
- **外部依赖**: `nanobot/agent/tools/base.py`、`nanobot/agent/loop.py`、`ava/launcher.py`、`ava/tools/__init__.py`、`ava/agent/bg_tasks.py`、`ava/patches/tools_patch.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-tools-claude_code.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
