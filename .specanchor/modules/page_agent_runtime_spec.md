# Module Spec: page_agent_runtime — PageAgent Tool 与 Node Runner 调用链

> 相关文件：`ava/tools/page_agent.py`、`ava/tools/__init__.py`、`ava/patches/tools_patch.py`、`ava/forks/config/schema.py`、`console-ui/e2e/page-agent-runner.mjs`
> 状态：✅ 已实现（2026-04-03）

---

## 1. 模块职责

将 `page_agent` 作为 sidecar 自定义工具接入 `AgentLoop`，并通过常驻 Node runner 管理 Playwright 浏览器、页面内 `page-agent` 注入执行、截图采集，以及供 console 预览复用的 screencast / activity 事件流。

这个模块的边界是“工具运行时”而不是“console 页面”。它负责：

- agent 可见的 `page_agent` tool 接口
- Python ↔ Node 的 stdin/stdout JSON-RPC
- 浏览器会话复用与 runner 生命周期管理
- 截图落盘与 `MediaService` 记录
- 向 console 订阅者转发最近一帧与最近事件缓存

---

## 2. 调用链路

```text
AgentLoop._register_default_tools()
  -> tools_patch 注册 PageAgentTool
  -> agent tool_call: page_agent(action=...)
  -> PageAgentTool.execute()
  -> PageAgentTool._rpc()
  -> console-ui/e2e/page-agent-runner.mjs
  -> Playwright Browser / Context / Page
  -> page.addScriptTag(local page-agent demo bundle)
  -> new window.PageAgent(...)
  -> agent.execute(instruction)
  -> stdout RPC 响应 / 推送事件
  -> PageAgentTool 格式化结果或分发给 console 订阅者
```

### 2.1 工具注册链

| 环节 | 说明 |
|------|------|
| `ava/patches/tools_patch.py` | 在上游默认工具注册后追加 `PageAgentTool` |
| `config.tools.page_agent` | 读取启用开关和运行参数；缺失时允许以默认配置运行 |
| `ava/tools/__init__.py` | 导出 `PageAgentTool` 供 patch 引用 |

### 2.2 执行链

| 层级 | 入口 | 说明 |
|------|------|------|
| Agent 工具层 | `PageAgentTool.execute()` | 对外暴露 `execute` / `screenshot` / `get_page_info` / `close_session` |
| Python orchestration | `PageAgentTool._rpc()` | 生成请求 id、写 stdin、等 stdout、做超时控制 |
| Node runner | `page-agent-runner.mjs` handlers | 负责浏览器懒启动、会话池、页面导航、截图、CDP screencast |
| 页内执行层 | `new window.PageAgent(...).execute()` | 通过 demo bundle 暴露的 `PageAgent` 构造器在页面上下文中按自然语言指令操控 DOM |

---

## 3. 公共接口契约

### 3.1 Agent 可见动作

| action | 必填参数 | 返回形态 | 说明 |
|--------|----------|----------|------|
| `execute` | `instruction` | 文本 / JSON 字符串 | 默认文本；`response_format="json"` 时返回 machine-friendly JSON |
| `screenshot` | `session_id` | 文本 / JSON 字符串 | 截图写入磁盘，并在可用时写入 `MediaService` |
| `get_page_info` | `session_id` | 文本 / JSON 字符串 | 返回页面 URL / Title / Viewport |
| `close_session` | `session_id` | 文本 | 关闭对应 Playwright context/page |

说明：

- 对 agent 的最终返回仍是字符串；`response_format="json"` 时返回的是 JSON 字符串，不是原始 JSON-RPC 字典
- `session_id` 缺省时由工具生成 `s_<8hex>`，用于后续会话复用
- `response_format` 仅影响 `execute` / `screenshot` / `get_page_info`

#### execute 返回格式

```
[PageAgent SUCCESS/ERROR/TIMEOUT] session=<id> | Steps: <N> | Duration: <N>ms
URL: <current_url>
Title: <page_title>

<执行结果正文或错误信息>
```

STATUS 三层判定：
1. `TIMEOUT`：Python 端 `_rpc()` 超时合成（不经过 runner）
2. `ERROR`：RPC 失败（runner 异常），或 RPC 成功但 page-agent 内层 `result.success == false`
3. `SUCCESS`：RPC 成功且 page-agent 内层 `result.success == true`

首行保留 `session=` 格式以兼容下游消费者（如 `ava/skills/console_ui_regression/SKILL.md`）。

#### execute JSON 返回格式

```json
{
  "status": "SUCCESS | ERROR | TIMEOUT",
  "session_id": "s_xxx",
  "steps": 3,
  "duration_ms": 1200,
  "page": {
    "url": "http://127.0.0.1:6688/config",
    "title": "Config"
  },
  "result": {
    "success": true,
    "data": "..."
  },
  "page_state": {},
  "error": null
}
```

#### screenshot / get_page_info JSON 返回格式

- `screenshot(json)`：
  - `status`
  - `session_id`
  - `result.success`
  - `result.path`
  - `result.size_bytes`
  - `result.media_record_id`
  - `error`
- `get_page_info(json)`：
  - `status`
  - `session_id`
  - `page.url`
  - `page.title`
  - `page.viewport`
  - `result.success`
  - `error`

### 3.2 Console 复用接口

以下方法不直接暴露给 agent，而是供 console 路由层调用：

| 方法 | 用途 |
|------|------|
| `list_sessions()` | 查询 runner 当前持有的会话 |
| `get_page_info(session_id)` | 给 WS 初始状态提供页面信息 |
| `start_screencast(session_id, **params)` | 启动 Chromium CDP 帧流 |
| `stop_screencast(session_id)` | 停止帧流 |
| `subscribe(session_id, callback)` | 订阅 frame/activity/status 推送，并回放缓存 |
| `unsubscribe(session_id, callback)` | 移除订阅 |

---

## 4. 运行时协议与状态

### 4.1 Python ↔ Node 协议

- 传输介质：runner `stdin/stdout`
- 编码：每行一个 JSON
- RPC 响应：带 `id`
- 推送事件：无 `id`，包含 `type` 和 `session_id`

#### execute 响应字段

**成功**（`success: true`）：

| 字段 | 说明 |
|------|------|
| `session_id` | 会话 ID |
| `data` | page-agent 执行结果文本 |
| `success` | page-agent 内层执行结果（true/false）|
| `steps` | 执行步数 |
| `duration` | 执行耗时（毫秒）|
| `page_url` | 当前页面 URL |
| `page_title` | 当前页面标题 |
| `page_state` | 当前页面结构化状态（headings / alerts / forms / buttons） |

**失败**（`success: false`）：

| 字段 | 说明 |
|------|------|
| `code` | 错误码（`EXECUTION_FAILED` / `MISSING_PARAM`）|
| `message` | 错误描述 |
| `session_id` | 会话 ID |
| `duration` | 执行耗时（毫秒）|
| `page_url` | 当前页面 URL（可能为 "unknown"）|
| `page_title` | 当前页面标题（可能为 "unknown"）|

当前 runner 方法集合：

- `init`
- `execute`
- `screenshot`
- `get_page_info`
- `list_sessions`
- `close_session`
- `start_screencast`
- `stop_screencast`
- `shutdown`

当前推送事件集合：

- `frame`
- `activity`
- `status`

`types.ts` 里预留了 `step` 类型，但当前 runner 尚未实际下发。

### 4.2 生命周期

| 行为 | 实现位置 | 说明 |
|------|----------|------|
| 懒启动 runner | `PageAgentTool._ensure_runner()` | 首次 RPC 才启动 Node 子进程 |
| 初始化配置 | `_send_init_direct()` | 启动后立即下发 browser / model / timeout 配置 |
| 空闲回收 | `_idle_watchdog()` | 5 分钟无活动自动发送 `shutdown` |
| 进程退出清理 | `_read_stdout()` / `_sync_cleanup()` | runner 退出时清空 pending futures；进程退出时 `atexit` kill |
| 最大会话数 | runner `MAX_SESSIONS = 5` | 超限直接报错，不做 LRU 淘汰 |

#### runner 内部状态补充

- 注入使用的 bundle 是 `page-agent.demo.js`，其真实导出形状是 `window.PageAgent = PageAgent`，不是 `window.PageAgent.PageAgentCore`
- `page.exposeFunction("__paOnActivity")` / `__paOnStatus` 的注册状态保存在 runner session 侧；页面内 `window.__paActivityBridged` 只用于 document 级 listener 重建，避免导航后重复注册同名函数

### 4.3 事件缓存

- 每个 session 缓存最近 50 条 `activity/status`
- 额外缓存最后一帧 `frame`
- 新订阅者连接后立即回放缓存，避免 `/browser` 页面连接后全空白

---

## 5. 配置与依赖

### 5.1 配置来源

配置主路径是 `.nanobot/extra_config.json -> tools.pageAgent`，由 `ava/forks/config/schema.py` 的 `PageAgentConfig` 解析：

| 字段 | 说明 |
|------|------|
| `enabled` | 是否注册该工具 |
| `apiBase` / `apiKeyEnv` / `model` | page-agent 所用 OpenAI-compatible LLM 配置 |
| `headless` / `browserType` | 浏览器启动模式 |
| `viewportWidth` / `viewportHeight` | 新 session 的 viewport |
| `maxSteps` / `stepDelay` / `timeout` | 执行步数、节流和 RPC 超时 |
| `language` | page-agent 语言 |
| `screenshotDir` | 截图目录，缺省回落到 `~/.nanobot/media/generated` |

若 fork schema 未启用，`tools_patch` 仍会以 `config=None` 注册 `PageAgentTool`，此时回落到硬编码默认值，不依赖 `b_config_patch`。

### 5.2 依赖关系

#### 上游依赖

- `nanobot.agent.tools.base.Tool`
- `nanobot.config.loader.load_config`（通过 `tools_patch` 读取配置）

#### Sidecar 内部依赖

- `ava/patches/tools_patch.py`
- `ava/forks/config/schema.py`
- `ava.console.services.media_service.MediaService`

#### 外部依赖

- `node`
- `playwright`
- `page-agent`

---

## 6. 边界与限制

- 不修改 `nanobot/`；所有接入都通过 `ava/patches/tools_patch.py`
- runner 只执行预定义 RPC，不接受任意 shell / JS 代码
- screencast 只在 `browserType="chromium"` 时可用
- `page-agent` 基于 DOM 文本理解页面；图片、Canvas、SVG 语义识别需要额外配合 `vision`
- agent 返回格式是结构化文本（`[PageAgent STATUS] ...`），前端 `ToolCallBlock` 可解析展示专属卡片；旧格式降级为通用渲染

---

## 7. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| `tests/tools/test_page_agent.py` | action 参数校验、`response_format=json` schema、`[PageAgent STATUS]` 文本输出格式、`execute/screenshot/get_page_info` JSON contract、`_format_error_result` TIMEOUT/ERROR 格式化、disabled 分支、订阅/反订阅、`list_sessions()` 过滤、`get_page_info()` 透传 |
| `tests/patches/test_tools_patch.py` | `tools_patch` 成功替换注册函数并包含 PageAgent 相关注册逻辑 |
| 手动运行 | 真实 `node + playwright + page-agent` 集成、截图写盘、Chromium screencast、空闲自动回收 |

---
