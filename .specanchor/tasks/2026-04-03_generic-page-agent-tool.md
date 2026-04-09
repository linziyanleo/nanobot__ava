---
specanchor:
  level: task
  task_name: "通用 PageAgent 页面操作工具"
  author: "@fanghu"
  created: "2026-04-03"
  status: "draft"
  last_change: "补齐 page_agent runtime / console-ui browser page module spec，并按当前实现修正文档引用"
  related_modules:
    - ".specanchor/modules/ava-tools-page_agent.spec.md"
    - ".specanchor/modules/console-ui-src-pages-BrowserPage.spec.md"
    - ".specanchor/modules/ava-patches-tools_patch.spec.md"
    - ".specanchor/modules/ava-patches-a_schema_patch.spec.md"
  related_tasks:
    - ".specanchor/tasks/2026-04-02_console-ui-page-agent-autotest-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "refactor/sidecar"
---

# SDD Spec: 通用 PageAgent 页面操作工具

## 0. Open Questions

- [x] **Q1: LLM 配置路径** — 通过 `.nanobot/extra_config.json` 的 `tools.pageAgent` 字段独立配置（page-agent 只接受 OpenAI 兼容 API，与 nanobot 的 Anthropic provider 不同源）
- [x] **Q2: 浏览器会话复用** — v1 支持，通过 session_id 复用浏览器实例
- [x] **Q3: 截图产物** — 复用现有 MediaService / media 体系
- [x] **Q4: URL 访问限制** — v1 默认允许所有 URL，不设白名单

## 1. Requirements

### 1.1 Goal

为 nanobot agent 新增一个**通用页面操作工具** `page_agent`，使 agent 能够通过自然语言指令操控任意网页：填写表单、点击按钮、提取信息、导航页面、截取屏幕等。

### 1.2 与 console-ui autotest spec 的关系

| 维度 | 本 spec（通用 page_agent tool） | console-ui autotest spec |
|------|-------------------------------|--------------------------|
| 定位 | 通用页面操作能力，操作任意网页 | console-ui 专用自回归测试闭环 |
| 调用方 | agent 直接按需调用 | agent 按固定工作流调用 |
| 断言层 | 无内置断言，结果由 agent 判断 | Playwright 强断言 |
| 进程管理 | 不管理目标网站的进程 | 管理 managed_vite 生命周期 |
| 依赖关系 | 独立，无上游依赖 | 可在内部使用本 tool 作为语义执行层 |

**结论**：本 tool 是底层通用能力；console-ui autotest 是上层特定场景的 orchestration，未来可选择在其内部调用本 tool。

### 1.3 In-Scope

- 新增 `page_agent` tool，支持 agent 通过自然语言操控网页
- 通过 Playwright 启动/管理浏览器，在页面内注入 page-agent 运行
- 支持浏览器会话复用（同一会话内多次操作）
- 支持截图并写入 MediaService
- 支持 headless / headed 两种模式
- 提供配置项控制 LLM、浏览器行为（通过 `.nanobot/extra_config.json` 的 `tools.pageAgent`）
- **新增 console-ui 实时预览页面**（`/browser`），在 div 内实时显示 agent 正在操作的页面画面，并附带 page-agent 操作可视化效果和结构化 activity 事件流

### 1.4 Out-of-Scope

- 不修改 `nanobot/`
- 不实现测试框架、断言引擎、测试报告
- 不管理目标网站的进程生命周期
- 不实现 PageAgent 的 MCP server 或浏览器扩展模式
- v1 不支持多标签页并发操作
- v1 不支持文件上传/下载等复杂交互
- 实时预览不支持用户直接在预览画面中点击操作（只读观看）

### 1.5 Success Criteria

- agent 默认工具集中可见 `page_agent`
- `action=execute` 能打开页面并按自然语言指令操作，返回结构化结果
- `action=screenshot` 能截取当前页面并写入 media
- 浏览器会话可跨多次 tool call 复用
- 在 headless 模式下能稳定运行
- console-ui 的 `/browser` 页面能实时显示 agent 操作的浏览器画面（含 page-agent 光标动画和操作面板）
- activity 事件流在预览页面侧边栏实时显示 agent 的思考和操作步骤

## 2. Research Findings

### 2.1 page-agent 技术特性

- **纯前端架构**：page-agent 运行在浏览器页面内部，依赖 window/document API
- **基于文本的 DOM 操作**：通过 DOM 提取生成文本化的页面结构，不需要截图或多模态 LLM
- **LLM 要求**：OpenAI 兼容 API + tool_call 支持（通过 baseURL/apiKey/model 配置）
- **核心 API**：`new PageAgent(config)` -> `agent.execute(instruction)` -> `{ success, data, history }`
- **无 Playwright 官方适配器**：需要自行通过 `page.evaluate()` 在页面上下文中注入和运行
- **NPM 包**：`page-agent`（完整版），`@page-agent/core`（无 UI 核心）

### 2.2 集成方案分析

page-agent 是纯前端代码，无法直接在 Node.js 中运行。集成到 Python sidecar 的可行路径：

**方案 A：Python -> Node runner script -> Playwright -> page.evaluate(page-agent)**

```
ava tool (Python)
  -> asyncio.create_subprocess 启动 Node runner
       -> Playwright 启动浏览器
            -> page.evaluate() 注入 page-agent
                 -> agent.execute(instruction)
                      -> 返回 JSON 结果
```

- 与 claude_code tool 的子进程模式一致
- runner 脚本负责浏览器生命周期和 page-agent 注入
- Python 侧只做 orchestration

**方案 B：Python -> playwright-python -> page.evaluate(page-agent)**

- 省去 Node runner 中间层
- 但 playwright-python 对 long-running evaluate 的异步支持不如原生 Node 版

### 2.3 方案决策

**选择方案 A**，理由：
1. page-agent 本身是 JS 生态，用 Node runner 最自然
2. 浏览器会话管理（持久化、复用）在 Node 侧实现更可靠
3. 与现有 claude_code tool 的子进程调用模式一致
4. runner 可独立测试和演进

### 2.4 现有 sidecar 可复用点

- `tools_patch.py`：统一注入入口
- `loop_patch.py`：依赖注入 media_service
- `claude_code.py`：子进程调用模式（超时、输出解析、环境变量注入）
- `media_service.py`：截图产物归档

## 3. Innovate

### Option A: 每次调用启动新浏览器（无会话）

- Pros: 实现简单，无状态管理
- Cons: 每次都要重新打开页面、登录，延迟高且不实用

### Option B: Node runner 常驻进程 + IPC（选中）

- Pros:
  - 浏览器会话天然持久，支持多次操作复用
  - 通过 stdin/stdout JSON-RPC 通信，延迟低
  - runner 进程生命周期由 Python tool 管理
- Cons:
  - 需要管理进程生命周期和异常恢复

### Option C: WebSocket server 模式

- Pros: 支持多客户端
- Cons: 过度设计，当前只有 agent 一个调用方

### Decision

选择 **Option B**：Node runner 常驻进程模式。

runner 进程启动后保持运行，Python 侧通过 stdin 发送 JSON 命令、从 stdout 读取 JSON 响应。浏览器实例在 runner 进程生命周期内复用。

## 4. Plan (Contract)

### 4.1 Architecture

```
+--------------------------------------------------+
| nanobot agent                                     |
|   | tool_call: page_agent                         |
| +----------------------------------------------+ |
| | PageAgentTool (Python)                       | |
| |  - 管理 runner 子进程生命周期                | |
| |  - 序列化命令 -> stdin JSON                  | |
| |  - 解析 stdout JSON -> 结构化结果            | |
| |  - 截图写入 MediaService                     | |
| +---------------------+------------------------+ |
|                       | stdin/stdout JSON-RPC     |
| +---------------------v------------------------+ |
| | page-agent-runner.mjs (Node)                 | |
| |  - Playwright 浏览器管理                     | |
| |  - page-agent 注入与执行                     | |
| |  - 会话（tab）池管理                         | |
| |  - 截图采集                                  | |
| +----------------------------------------------+ |
+--------------------------------------------------+
```

### 4.2 实时预览架构（console-ui `/browser` 页面）

#### 4.2.1 画面流方案：CDP Page.startScreencast

page-agent 的 SimulatorMask（AI 光标动画 + 操作遮罩）和 Panel UI 是直接渲染在被操作页面 DOM 上的。使用 Chromium CDP 的 `Page.startScreencast` 可以捕获包含这些可视化效果在内的完整渲染帧。

```
[Playwright 浏览器]
    page-agent 在页面内运行
    ├─ SimulatorMask：AI 光标 + 点击涟漪动画 + 操作遮罩
    └─ Panel：状态灯 + 任务历史
         │
         ├─ CDP Page.startScreencast → JPEG 帧流 (5-10 fps)
         │         │
         │         ▼
         ├─ Node runner → stdout 帧事件
         │         │
         │         ▼
         ├─ Python tool → WebSocket /api/page-agent/ws/{session_id}
         │         │
         │         ▼
         └─ console-ui /browser 页面 → <img> 实时刷新
```

**关键点**：
- CDP screencast 只在 Chromium 内核可用，因此实时预览要求 `browserType: "chromium"`
- 帧格式 JPEG quality=60，分辨率跟随 viewport（1280x720），每帧约 30-80KB
- 采用背压控制：每帧需要 ack 才发下一帧，自然限流

#### 4.2.2 Activity 事件流

page-agent 提供两类实时事件，通过同一个 WebSocket 连接并行传输：

| 事件类型 | 来源 | 内容 | 用途 |
|---------|------|------|------|
| `frame` | CDP screencast | base64 JPEG | 画面渲染 |
| `activity` | page-agent activity event | `{type: "thinking"/"executing"/"executed", tool?, input?, output?}` | 侧边栏显示 agent 思考/操作过程 |
| `status` | page-agent statuschange | `"idle"/"running"/"completed"/"error"` | 状态指示 |
| `step` | page-agent historychange | `{reflection, action, observation}` | 操作历史回看 |

#### 4.2.3 console-ui `/browser` 页面 UI 设计

```
+----------------------------------------------------------------+
| [< 浏览器预览]                              [session ▼] [⏸ ■] |
+----------------------------------------------------------------+
|                                    |                            |
|                                    |  Agent Activity            |
|                                    |  ─────────────             |
|      [实时浏览器画面]              |  ● Thinking...             |
|      <img> 或 <canvas>            |    评估上一步：登录成功     |
|      自适应容器宽度                |    下一步：点击配置页       |
|      保持 16:9 比例               |                            |
|                                    |  ◉ Executing               |
|                                    |    click_element [5]       |
|                                    |                            |
|                                    |  ✓ Executed (320ms)        |
|                                    |    已点击"配置"链接        |
|                                    |                            |
|                                    |  ● Thinking...             |
|                                    |    ...                     |
+----------------------------------------------------------------+
|  URL: https://example.com/config   |  Status: ● Running  3/40  |
+----------------------------------------------------------------+
```

**布局**：
- 左侧主区域：浏览器画面，`<img>` 标签通过 `src` 动态替换 base64 帧（或用 canvas drawImage）
- 右侧侧边栏（可折叠）：activity 事件流，按时间倒序，不同类型用不同颜色/图标
- 底部状态栏：当前 URL、agent 状态、步骤计数
- 顶部：session 选择器、暂停/停止按钮
- 响应式：移动端侧边栏折叠为底部 sheet

#### 4.2.4 后端 WebSocket 端点

```
GET /api/page-agent/ws/{session_id}?token=...
```

- 复用 console 现有的 token 认证机制
- 连接建立后，后端向 runner 发送 `start_screencast` 命令
- 断开时发送 `stop_screencast`
- 无观看者时不产生帧流（节省资源）

#### 4.2.5 Runner 新增协议

Python -> Node（新增 screencast 相关命令）：

```jsonc
// 启动帧流
{ "id": "req-10", "method": "start_screencast", "params": { "session_id": "s1", "quality": 60, "maxWidth": 1280, "maxHeight": 720 } }

// 停止帧流
{ "id": "req-11", "method": "stop_screencast", "params": { "session_id": "s1" } }
```

Node -> Python（帧流和事件通过 stdout 推送）：

```jsonc
// 画面帧（推送，无 id）
{ "type": "frame", "session_id": "s1", "data": "<base64 JPEG>", "metadata": { "timestamp": 1234567890 } }

// activity 事件（推送，无 id）
{ "type": "activity", "session_id": "s1", "activity": { "type": "executing", "tool": "click_element_by_index", "input": { "index": 5 } } }

// 状态变化（推送，无 id）
{ "type": "status", "session_id": "s1", "status": "running" }
```

**注意**：帧数据和 RPC 响应共用 stdout，通过有无 `id` 字段区分：有 `id` 的是 RPC 响应，无 `id` 的是推送事件。

### 4.3 通信协议

Python -> Node（stdin，每行一个 JSON）：

```jsonc
// 执行页面操作
{ "id": "req-1", "method": "execute", "params": { "url": "https://example.com", "instruction": "点击登录按钮", "session_id": "s1" } }

// 截图
{ "id": "req-2", "method": "screenshot", "params": { "session_id": "s1", "path": "/tmp/shot.png" } }

// 获取页面信息
{ "id": "req-3", "method": "get_page_info", "params": { "session_id": "s1" } }

// 关闭会话
{ "id": "req-4", "method": "close_session", "params": { "session_id": "s1" } }

// 关闭 runner
{ "id": "req-5", "method": "shutdown" }
```

Node -> Python（stdout，每行一个 JSON）：

```jsonc
// 成功
{ "id": "req-1", "success": true, "result": { "data": "已点击登录按钮", "page_url": "https://example.com/dashboard", "page_title": "Dashboard" } }

// 失败
{ "id": "req-1", "success": false, "error": { "code": "EXECUTION_FAILED", "message": "Element not found" } }
```

### 4.3 File Changes

| 文件 | 操作 | 说明 |
|------|------|------|
| **Node runner 层** | | |
| `console-ui/e2e/page-agent-runner.mjs` | 新增 | Node runner：浏览器管理、page-agent 注入、JSON-RPC、CDP screencast、activity 事件转发 |
| `console-ui/package.json` | 修改 | 新增 page-agent、playwright 依赖 |
| **Python Tool 层** | | |
| `ava/tools/page_agent.py` | 新增 | Tool 主体 + screencast 帧/事件的 asyncio 转发管道 |
| `ava/tools/__init__.py` | 修改 | 导出 PageAgentTool |
| `ava/patches/tools_patch.py` | 修改 | 注入 page_agent |
| **配置层** | | |
| `ava/forks/config/schema.py` | 修改 | 新增 PageAgentConfig |
| `ava/patches/b_config_patch.py` | 计划中未落地 | 当前实现未为 page_agent 追加 fallback 字段；无 fork schema 时退回工具默认配置 |
| **后端 WebSocket** | | |
| `ava/console/routes/page_agent_routes.py` | 新增 | `/api/page-agent/ws/{session_id}` 端点，转发帧流 + activity 事件 |
| `ava/console/app.py` | 修改 | 注册 page_agent 路由 |
| **console-ui 前端** | | |
| `console-ui/src/pages/BrowserPage/index.tsx` | 新增 | 实时预览主页面 |
| `console-ui/src/pages/BrowserPage/ScreencastView.tsx` | 新增 | 画面帧渲染 |
| `console-ui/src/pages/BrowserPage/ActivityPanel.tsx` | 新增 | activity 事件流侧边栏 + 底部状态区 |
| `console-ui/src/pages/BrowserPage/types.ts` | 新增 | 类型定义 |
| `console-ui/src/App.tsx` | 修改 | 新增 `/browser` 路由 |
| `console-ui/src/components/layout/navItems.ts` | 修改 | 新增"浏览器"导航项 |
| **测试** | | |
| `tests/tools/test_page_agent.py` | 新增 | 单元测试 |
| `tests/patches/test_tools_patch.py` | 修改 | 补充注册测试 |

### 4.4 Public Interfaces

#### 配置 Schema

配置路径：`.nanobot/extra_config.json` → `tools.pageAgent`

```jsonc
// .nanobot/extra_config.json
{
  "tools": {
    "pageAgent": {
      "enabled": true,
      "apiBase": "",                // OpenAI 兼容 API base URL
      "apiKeyEnv": "PAGE_AGENT_API_KEY",  // 存放 API key 的环境变量名
      "model": "",                  // 如 "qwen3.5-plus", "gpt-4o"
      "headless": true,
      "browserType": "chromium",    // chromium | firefox | webkit
      "viewportWidth": 1280,
      "viewportHeight": 720,
      "maxSteps": 40,
      "stepDelay": 0.4,
      "timeout": 120,               // 单次 execute 超时（秒）
      "language": "zh-CN",
      "screenshotDir": ""           // 默认 ~/.nanobot/media/generated/
    }
  }
}
```

对应 Python schema：

```python
class PageAgentConfig(Base):
    enabled: bool = True
    api_base: str = ""
    api_key_env: str = "PAGE_AGENT_API_KEY"
    model: str = ""
    headless: bool = True
    browser_type: str = "chromium"
    viewport_width: int = 1280
    viewport_height: int = 720
    max_steps: int = 40
    step_delay: float = 0.4
    timeout: int = 120
    language: str = "zh-CN"
    screenshot_dir: str = ""
```

#### Tool 参数（agent 可见）

```python
name = "page_agent"

description = (
    "Control web pages using natural language instructions. "
    "Can navigate to URLs, fill forms, click buttons, extract information, "
    "and take screenshots. Supports persistent browser sessions."
)

parameters = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["execute", "screenshot", "get_page_info", "close_session"],
            "description": "Action to perform"
        },
        "url": {
            "type": "string",
            "description": "Target URL (only for execute, optional if session already has a page open)"
        },
        "instruction": {
            "type": "string",
            "description": "Natural language instruction for page operation (only for execute)"
        },
        "session_id": {
            "type": "string",
            "description": "Session ID for reusing browser context. Omit to auto-generate."
        }
    },
    "required": ["action"]
}
```

#### 返回格式

```jsonc
// action=execute 成功
{
  "success": true,
  "action": "execute",
  "session_id": "s_abc123",
  "result": {
    "data": "PageAgent 的文本回复（操作结果描述）",
    "page_url": "https://example.com/dashboard",
    "page_title": "Dashboard"
  }
}

// action=screenshot 成功
{
  "success": true,
  "action": "screenshot",
  "session_id": "s_abc123",
  "screenshot_path": "/path/to/screenshot.png",
  "media_record_id": "page-agent-20260403-120000"
}

// action=get_page_info
{
  "success": true,
  "action": "get_page_info",
  "session_id": "s_abc123",
  "page_url": "https://example.com",
  "page_title": "Example",
  "viewport": "1280x720"
}

// 失败
{
  "success": false,
  "error": "描述信息"
}
```

### 4.5 Runner 进程生命周期

1. **懒启动**：首次调用时启动 runner 子进程
2. **心跳**：runner 进程每 30s 向 stderr 输出心跳，Python 侧监控
3. **自动回收**：空闲 5 分钟无操作时，Python 侧发送 shutdown 并终止进程
4. **异常恢复**：runner 进程意外退出时，下次调用自动重启
5. **随主进程退出**：nanobot 退出时通过 atexit 清理 runner 进程

### 4.6 会话管理

- 每个 session_id 对应一个 Playwright Page（浏览器标签页）
- 未指定 session_id 时自动生成 UUID
- close_session 关闭对应标签页
- runner 退出时所有会话自动清理
- v1 最多同时保持 5 个会话

### 4.7 安全考量

- v1 默认允许访问所有 URL（后续可按需增加白名单）
- runner 不执行任意代码，只调用 page-agent 的 execute(instruction)
- page-agent 的 experimentalScriptExecutionTool 默认关闭
- 截图文件仅写入配置的 screenshot_dir，不允许任意路径

### 4.8 Implementation Checklist

**Phase 1: 基础设施（Node runner + 依赖）**

- [ ] 1. 在 `console-ui/package.json` 新增 `page-agent` 和 `playwright` 依赖
- [ ] 2. 编写 `console-ui/e2e/page-agent-runner.mjs`
  - [ ] 2a. stdin JSON-RPC 解析循环（readline，每行一个 JSON）
  - [ ] 2b. Playwright 浏览器懒启动与会话池管理（Map<session_id, Page>）
  - [ ] 2c. page-agent 注入逻辑（通过 page.addScriptTag 注入 CDN 或本地 bundle，再 page.evaluate 创建 PageAgentCore 实例并执行）
  - [ ] 2d. 七个 method handler：execute / screenshot / get_page_info / close_session / shutdown / start_screencast / stop_screencast
  - [ ] 2e. CDP screencast 帧流：通过 `context.newCDPSession(page)` 获取 CDP session，调用 `Page.startScreencast`，将帧以推送事件写入 stdout
  - [ ] 2f. page-agent activity 事件转发：监听 `activity` / `statuschange` / `historychange` 事件，序列化为推送事件写入 stdout
  - [ ] 2g. stderr 心跳输出（每 30s）
  - [ ] 2h. 启动时接收配置参数（LLM config、browser config）通过 init 命令或命令行参数

**Phase 2: 配置层**

- [ ] 3. 在 `ava/forks/config/schema.py` 新增 `PageAgentConfig`，挂载到 `ToolsConfig.page_agent`
  - camelCase alias 保持与 extra_config.json 的 `tools.pageAgent` 一致
- [ ] 4. 在 `ava/patches/b_config_patch.py` 为非 fork schema 路径注入 fallback 字段

**Phase 3: Python Tool**

- [ ] 5. 新增 `ava/tools/page_agent.py`
  - [ ] 5a. Tool 基类四件套（name, description, parameters, execute）
  - [ ] 5b. runner 子进程生命周期管理（懒启动、心跳监控、空闲回收、异常重启、atexit 清理）
  - [ ] 5c. JSON-RPC 请求/响应：stdin 写入、stdout readline、超时控制
  - [ ] 5d. screenshot action 时调用 MediaService.write_record() 归档截图
  - [ ] 5e. set_context(channel, chat_id) 支持
  - [ ] 5f. screencast 转发管道：后台 asyncio task 持续读取 stdout 推送事件，分发给已注册的 WebSocket 观看者
  - [ ] 5g. 公开 `subscribe(session_id, callback)` / `unsubscribe()` 接口供 console WS 路由调用
- [ ] 6. 在 `ava/tools/__init__.py` 导出 `PageAgentTool`
- [ ] 7. 在 `ava/patches/tools_patch.py` 注册 `page_agent`（从 config.tools.page_agent 读取配置）

**Phase 4: 后端 WebSocket 端点**

- [ ] 8. 新增 `ava/console/routes/page_agent.py`
  - [ ] 8a. WebSocket 端点 `/api/page-agent/ws/{session_id}`，复用现有 token 认证
  - [ ] 8b. 连接时通知 PageAgentTool 启动 screencast，断开时停止
  - [ ] 8c. 从 tool 接收帧/activity 事件，转发给 WS 客户端
  - [ ] 8d. 支持多个观看者同时连接同一 session（广播）
- [ ] 9. 在 `ava/console/app.py` 注册 page_agent 路由

**Phase 5: console-ui 前端（`/browser` 页面）**

- [ ] 10. 新增 `console-ui/src/pages/BrowserPage/`
  - [ ] 10a. `index.tsx` — 主容器：左右分栏（画面 + activity 侧边栏），session 选择器
  - [ ] 10b. `ScreencastView.tsx` — 画面渲染：WebSocket 接收 base64 帧 → `<img src="data:image/jpeg;base64,...">` 动态替换，保持 16:9 自适应
  - [ ] 10c. `ActivityPanel.tsx` — activity 事件流：按时间倒序显示 thinking/executing/executed，并承载底部状态区
  - [ ] 10d. `types.ts` — ScreencastFrame、ActivityEvent、SessionInfo 等类型定义
- [ ] 11. 修改 `console-ui/src/App.tsx` — 新增 `/browser` 路由
- [ ] 12. 修改 `console-ui/src/components/layout/navItems.ts` — 新增"浏览器"导航项（Globe 图标）

**Phase 6: 测试**

- [ ] 13. 编写 `tests/tools/test_page_agent.py` 单元测试
- [ ] 14. 在 `tests/patches/test_tools_patch.py` 补充注册测试

**Phase 7: 文档**

- [ ] 15. 更新 `ava/templates/TOOLS.md`（实现完成后按实际行为写入）

## 5. Test Coverage

### 5.1 自动化测试

| ID | 类型 | 覆盖内容 |
|----|------|----------|
| T1 | Unit | 配置加载与默认值 |
| T2 | Unit | runner 进程启动与 shutdown |
| T3 | Unit | JSON-RPC 命令序列化与响应解析 |
| T4 | Unit | session_id 自动生成与复用 |
| T5 | Unit | execute 超时处理 |
| T6 | Unit | runner 进程异常退出后自动重启 |
| T7 | Unit | 截图写入 MediaService 的字段格式 |
| T8 | Unit | 空闲自动回收逻辑 |
| T9 | Patch | page_agent 被正确注入默认工具集合 |
| T10 | Contract | runner 返回畸形 JSON 时工具优雅降级 |

### 5.2 手动验收

| ID | 场景 | 验收标准 |
|----|------|----------|
| M1 | agent 调用 execute + url + instruction | 返回成功结果，data 包含操作描述 |
| M2 | 同一 session_id 连续两次 execute | 第二次复用页面上下文，不重新打开浏览器 |
| M3 | action=screenshot | 截图文件生成且 media record 可查 |
| M4 | 配置 headless: false | 可见浏览器窗口弹出 |
| M5 | 打开 console-ui `/browser` 页面，agent 正在执行 page_agent | 画面实时显示，能看到 AI 光标移动和点击涟漪 |
| M6 | `/browser` 页面侧边栏 | activity 事件实时出现（thinking → executing → executed） |
| M7 | 无 agent 操作时访问 `/browser` | 显示空状态（无活跃会话） |

### 5.3 不做自动化覆盖

- 真实 page-agent LLM 调用不纳入自动化测试（外部 API 依赖）
- 自动化只验证 orchestration 层的 contract

## 6. Acceptance Criteria

- 新工具从 agent 默认工具列表中可见
- execute 能通过自然语言操控页面并返回结构化结果
- 浏览器会话可跨多次 tool call 复用
- 截图产物写入 MediaService
- headless 模式下稳定运行
- 不修改 nanobot/
- runner 进程生命周期可靠（启动、回收、异常恢复）
- console-ui `/browser` 页面能实时显示浏览器画面（含 page-agent 可视化效果）
- activity 事件流在侧边栏实时呈现
- 无观看者时不产生帧流（节省资源）

## 7. Execute Log

- [ ] 尚未进入 Execute

## 8. Review Verdict

- Spec coverage: 待 Review

## 9. Plan-Execution Diff

- Any deviation from plan:
  - `page_agent` 最终没有落在 `b_config_patch` fallback 字段注入上；未启用 fork schema 时直接以默认配置运行
  - 后端路由文件名实际为 `ava/console/routes/page_agent_routes.py`
  - 前端状态栏未拆出 `StatusBar.tsx`，而是合并到 `ActivityPanel.tsx`
