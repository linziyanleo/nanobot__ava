---
specanchor:
  level: module
  module_name: "Page Agent 运行时"
  module_path: "ava/tools/page_agent.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-04-03"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "按 SpecAnchor 最新 Module Spec 模板重生，合并 legacy spec 与当前代码扫描结果"
  status: "active"
  depends_on:
    - "nanobot/agent/tools/base.py"
    - "console-ui/e2e/page-agent-runner.mjs"
---

# Page Agent 运行时 (page_agent_runtime)

## 1. 模块职责
- 这个模块的边界是“工具运行时”而不是“console 页面”。它负责：
- agent 可见的 page_agent tool 接口
- Python ↔ Node 的 stdin/stdout JSON-RPC
- 浏览器会话复用与 runner 生命周期管理

## 2. 业务规则
- 工具签名是 agent 合同，参数名和返回形态变更必须同步 patch、console 与 task spec
- 涉及长时任务时优先走 BackgroundTaskStore，而不是在 tool 内部维护孤立状态
- 尽量记录 token / media / audit 辅助信息，但缺失依赖时要优雅降级

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `PageAgentTool` | `class` | Control web pages using natural language via page-agent + Playwright. |
| `PageAgentTool.execute()` | `execute(action: str, response_format: str = 'text', **kwargs) -> str` | 公共方法 |
| `PageAgentTool.start_screencast()` | `start_screencast(session_id: str, **params) -> dict` | 启动指定会话的 CDP 帧流。 |
| `PageAgentTool.stop_screencast()` | `stop_screencast(session_id: str) -> dict` | 停止指定会话的 CDP 帧流。 |
| `PageAgentTool.get_page_info()` | `get_page_info(session_id: str) -> dict[str, Any]` | 返回结构化页面信息，供 console WS 初始化状态。 |
| `PageAgentTool.list_sessions()` | `list_sessions() -> list[str]` | 返回 runner 当前持有的会话列表。 |
| `PageAgentTool.subscribe()` | `subscribe(session_id: str, callback: Callable) -> None` | 注册推送事件回调（frame/activity/status）。同时回放缓存事件。 |
| `PageAgentTool.unsubscribe()` | `unsubscribe(session_id: str, callback: Callable) -> None` | 移除推送事件回调。 |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| _RUNNER_SCRIPT | module | 模块级共享状态或常量 |
| _IDLE_TIMEOUT | module | 模块级共享状态或常量 |
| _LIVE_PAGE_AGENT_TOOLS | module | 模块级共享状态或常量 |
| _PROCESS_CLEANUP_REGISTERED | module | 模块级共享状态或常量 |
| _lock | instance | PageAgentTool 运行时字段 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- 传输介质：runner stdin/stdout
- 编码：每行一个 JSON
- RPC 响应：带 id
- 推送事件：无 id，包含 type 和 session_id

## 5. 已知约束 & 技术债
- [ ] `config.tools.page_agent` 负责启用开关和运行参数；配置缺失时必须允许以默认值运行。

## 6. TODO
- [ ] 新增参数、返回字段或异步模式后，立即同步 Spec 和调用链说明 @ZiyanLin
- [ ] 补齐针对成功路径、失败路径和降级路径的窄测试 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/tools/page_agent.py`
- **核心链路**: 工具注册 → tool.execute() → 运行时执行器/CLI/runner → 结构化结果返回
- **数据流**: Agent tool call → 参数校验 → 执行主链路 → 结果/状态写回聊天或后台任务
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/tools/page_agent.py` | 模块主入口 |
| `console-ui/e2e/page-agent-runner.mjs` | 关联链路文件 |
- **外部依赖**: `nanobot/agent/tools/base.py`、`console-ui/e2e/page-agent-runner.mjs`

## 8. 迁移说明
- 本文件由 legacy spec `ava-tools-page_agent.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
