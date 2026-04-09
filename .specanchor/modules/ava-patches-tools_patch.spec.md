---
specanchor:
  level: module
  module_name: "自定义工具注入 Patch"
  module_path: "ava/patches/tools_patch.py"
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
    - "nanobot/agent/loop.py"
    - "ava/launcher.py"
    - "ava/tools/__init__.py"
    - "nanobot/agent/tools/base.py"
    - "nanobot/providers/base.py"
    - "nanobot/config/loader.py"
---

# 自定义工具注入 Patch (tools_patch)

## 1. 模块职责
- 在上游默认工具注册完成后，追加注入 ava 自定义工具。
- 当前包含 4 个固定工具（`claude_code`、`image_gen`、`vision`、`send_sticker`）和 2 个条件工具（`page_agent`、`memory`）。
- 保证上游工具仍然保留，自定义工具只做追加和条件启用，不重写上游注册语义。

## 2. 业务规则
- **原始行为**：AgentLoop._register_default_tools(self) 注册上游内置工具（filesystem、web、shell、cron、mcp 等）
- **修改后行为**：先调用原始方法完成内置工具注册，然后追加注册自定义工具；其中 page_agent 受 config.tools.page_agent.enabled 控制，memory 受 self.categorized_memory 是否存在控制
- **Patch 方式**：保存原始方法引用 → 定义包装函数 → 替换类方法

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `apply_tools_patch()` | `apply_tools_patch() -> str` | Apply the custom tools patch to AgentLoop. |
| `ClaudeCodeTool` | `class` | Run Claude Code CLI to modify code, add features, fix bugs, or analyze a codebase. |
| `ClaudeCodeTool.execute()` | `execute(prompt: str, project_path: str | None = None, mode: str = 'standard', session_id: str | None = None, **kwargs) -> str` | 公共方法 |
| `ClaudeCodeTool.cancel()` | `cancel(task_id: str) -> str` | Cancel a running Claude Code task. |
| `CodexTool` | `class` | Run OpenAI Codex CLI to run code tasks in background. |
| `CodexTool.execute()` | `execute(prompt: str, project_path: str | None = None, mode: str = 'standard', **kwargs) -> str` | 公共方法 |
| `CodexTool.cancel()` | `cancel(task_id: str) -> str` | 公共方法 |
| `PageAgentTool` | `class` | Control web pages using natural language via page-agent + Playwright. |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| _MAX_OUTPUT_CHARS | module | 模块级共享状态或常量 |
| _HEAD_CHARS | module | 模块级共享状态或常量 |
| _TAIL_CHARS | module | 模块级共享状态或常量 |
| cc_config | instance | ClaudeCodeTool 运行时字段 |
| _CODEX_SUBCMD | module | 模块级共享状态或常量 |
| _RUNNER_SCRIPT | module | 模块级共享状态或常量 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.agent.loop.AgentLoop — 拦截目标
- nanobot.config.loader.load_config — 读取配置
- ava.tools.* — 6 个工具实现类（其中 page_agent / memory 为条件注册）
- ava.launcher.register_patch — 自注册机制

## 5. 已知约束 & 技术债
- [ ] `token_stats`、`media_service`、`categorized_memory` 等可选属性缺失时必须静默降级，不能中断工具注册。
- [ ] `AgentLoop` 无 `_register_default_tools` 时必须优雅跳过，并返回可诊断的 skip 文案。

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/tools_patch.py`
- **核心链路**: `tools_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/tools_patch.py` | 模块主入口 |
| `ava/tools/claude_code.py` | 关联链路文件 |
| `ava/tools/codex.py` | 关联链路文件 |
| `ava/tools/page_agent.py` | 关联链路文件 |
| `ava/tools/image_gen.py` | 关联链路文件 |
| `ava/tools/vision.py` | 关联链路文件 |
- **外部依赖**: `nanobot/agent/loop.py`、`ava/launcher.py`、`ava/tools/__init__.py`、`nanobot/agent/tools/base.py`、`nanobot/providers/base.py`、`nanobot/config/loader.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-tools_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
