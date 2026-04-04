# Module Spec 索引

> 最后更新：2026-04-04 (upstream 04a41e31 对照)

## Patch 模块（已实现）

| Patch 文件 | Spec 文件 | 状态 | 说明 |
|-----------|----------|------|------|
| `ava/patches/a_schema_patch.py` | [schema_patch_spec.md](schema_patch_spec.md) | ✅ | Config Schema 模块替换 |
| `ava/patches/b_config_patch.py` | [config_patch_spec.md](config_patch_spec.md) | ✅ | Config 字段注入（降级方案） |
| `ava/patches/bus_patch.py` | [bus_console_listener_spec.md](bus_console_listener_spec.md) | ✅ | MessageBus Console + Observe 双套监听器 |
| `ava/patches/c_onboard_patch.py` | [onboard_patch_spec.md](onboard_patch_spec.md) | ✅ | onboard refresh 旧配置兼容层 |
| `ava/patches/channel_patch.py` | [channel_patch_spec.md](channel_patch_spec.md) | ✅ | 消息批处理 |
| `ava/patches/console_patch.py` | [console_patch_spec.md](console_patch_spec.md) | ✅ | Web Console 独立服务 |
| `ava/patches/context_patch.py` | [context_patch_spec.md](context_patch_spec.md) | ✅ | 历史摘要+压缩+分类记忆注入 |
| `ava/patches/loop_patch.py` | [loop_patch_spec.md](loop_patch_spec.md) | ✅ | AgentLoop 属性注入 + Token 统计 + Phase 0 预记录 + 实时广播 + CancelledError + LifecycleManager 初始化 |
| `ava/patches/skills_patch.py` | [skills_patch_spec.md](skills_patch_spec.md) | ✅ | SkillsLoader 三源发现 + SQLite disabled filter |
| `ava/patches/storage_patch.py` | [storage_patch_spec.md](storage_patch_spec.md) | ✅ | SQLite 存储层替换 |
| `ava/patches/tools_patch.py` | [tools_patch_spec.md](tools_patch_spec.md) | ✅ | 8 个自定义工具注入（含 codex、page_agent、gateway_control） |
| `ava/patches/templates_patch.py` | — | ✅ | 模板同步覆盖：`ava/templates/` → workspace |
| `ava/patches/transcription_patch.py` | [transcription_patch_spec.md](transcription_patch_spec.md) | ✅ | GroqTranscriptionProvider 代理注入 |

## 功能模块（已实现）

| 模块文件 | Spec 文件 | 状态 | 说明 |
|---------|----------|------|------|
| `ava/tools/claude_code.py` | [claude_code_tool_spec.md](claude_code_tool_spec.md) | ✅ | `claude_code` tool，sync/async 模式，async 通过 BackgroundTaskStore 管理 |
| `ava/agent/bg_tasks.py` | [claude_code_tool_spec.md](claude_code_tool_spec.md) §5 | ✅ | `BackgroundTaskStore` — 统一后台任务上下文层，SQLite 持久化 + context digest 注入 |
| `ava/tools/codex.py` | [codex_tool_spec.md](codex_tool_spec.md) | ✅ | `codex` tool，Codex CLI 集成，全异步，共享 BackgroundTaskStore |
| `ava/console/routes/bg_task_routes.py` | — | ✅ | 后台任务 REST + WebSocket API（`/api/bg-tasks/*`） |
| `ava/tools/page_agent.py` + `console-ui/e2e/page-agent-runner.mjs` | [page_agent_runtime_spec.md](page_agent_runtime_spec.md) | ✅ | `page_agent` tool、Node runner、JSON-RPC、screencast / activity、LLM usage 记录、持久化浏览器 |
| `ava/console/routes/page_agent_routes.py` + `console-ui/src/pages/BrowserPage/*` | [console_browser_page_spec.md](console_browser_page_spec.md) | ✅ | `/api/page-agent/*` 与 console-ui `/browser` 预览页链路 |

## 已接入模块

| 模块文件 | 接入方式 | 状态 | 说明 |
|---------|----------|------|------|
| `ava/agent/categorized_memory.py` | `loop_patch` 注入 + `context_patch` 注入记忆 | ✅ | 分类记忆系统 |
| `ava/agent/history_compressor.py` | `loop_patch` 注入 + `context_patch` 调用 | ✅ | 历史压缩器 |
| `ava/agent/history_summarizer.py` | `loop_patch` 注入 + `context_patch` 调用 | ✅ | 历史摘要器 |

## 已复制但未接入模块

| 模块文件 | Spec 文件 | 状态 | 说明 |
|---------|----------|------|------|
| `ava/agent/commands.py` | [commands_spec.md](commands_spec.md) | 🟡 | 统一命令系统 |

## 计划新增模块

| 模块文件 | Spec 文件 | 状态 | 说明 |
|---------|----------|------|------|
| `ava/runtime/lifecycle.py` | [lifecycle-and-frontend-hotupdate](../tasks/2026-04-04_lifecycle-and-frontend-hotupdate.md) §3.2 | ✅ | LifecycleManager：supervisor-first 生命周期后端 |
| `ava/tools/gateway_control.py` | [lifecycle-and-frontend-hotupdate](../tasks/2026-04-04_lifecycle-and-frontend-hotupdate.md) §3.3 | ✅ | 生命周期控制工具（status / restart） |
| `ava/console/ui_build.py` (rebuild 扩展) | [lifecycle-and-frontend-hotupdate](../tasks/2026-04-04_lifecycle-and-frontend-hotupdate.md) §3.4 | 📋 | 前端 rebuild 异步封装（Phase B） |

## 上游新增能力（待 merge 后可用）

> 以下模块随 upstream `04a41e31` 引入，merge 后自动可用。

| 上游模块 | 说明 | sidecar 影响 |
|----------|------|-------------|
| `nanobot/agent/tools/search.py` | GrepTool + GlobTool 原生搜索 | `TOOLS.md` 需记录 |
| `nanobot/agent/tools/schema.py` | `Schema` 类型 + `tool_parameters` 装饰器 | 可简化自定义工具定义 |
| `nanobot/utils/prompt_templates.py` | Jinja2 `render_template()` | 模板引擎可复用 |
| `nanobot/utils/gitstore.py` | Git 版本控制 for memory | Dream 基础设施 |
| `nanobot/utils/restart.py` | 环境变量 restart notice | 与 `LifecycleManager` 互补 |
| `nanobot/agent/memory.py` | `Consolidator` + `Dream` 双阶段记忆 | 替代 `MemoryConsolidator` |

## 其他模块

| 模块路径 | 说明 |
|---------|------|
| `ava/console/` | Web Console 子应用（FastAPI + WebSocket） |
| `ava/tools/` | 8 个自定义工具实现（含 `codex`、`page_agent`、`gateway_control`） |
| `ava/runtime/` | LifecycleManager 生命周期管理 |
| `ava/storage/` | SQLite 数据库封装 |
| `ava/channels/` | 消息批处理器实现 |
| `ava/session/` | Session backfill 实现 |
| `ava/forks/config/` | Config Schema Fork 文件 |
| `ava/skills/` | Skills 静态文件 |
| `ava/templates/` | 模板静态文件 |
