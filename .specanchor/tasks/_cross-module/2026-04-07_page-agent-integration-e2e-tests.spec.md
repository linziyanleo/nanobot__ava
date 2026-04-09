---
specanchor:
  level: task
  task_name: "PageAgent 集成测试 + E2E 冒烟测试"
  author: "@fanghu"
  created: "2026-04-07"
  status: "in_progress"
  last_change: "Spec 初稿"
  related_modules:
    - ".specanchor/modules/ava-tools-page_agent.spec.md"
    - ".specanchor/modules/ava-patches-tools_patch.spec.md"
  related_tasks:
    - ".specanchor/tasks/2026-04-03_generic-page-agent-tool.md"
    - ".specanchor/tasks/_cross-module/2026-04-07_page-agent-memory-hardening.spec.md"
  related_global:
    - ".specanchor/global-patch-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "IMPLEMENT"
  branch: "feat/0.1.1"
---

# SDD Spec: PageAgent 集成测试 + E2E 冒烟测试

## 1. 目标

为 page_agent 补充两层自动化测试，覆盖现有单元测试完全缺失的真实进程通信和浏览器操作链路。

## 2. 测试层次

### Layer 1: 集成测试（`test_page_agent_integration.py`）

真实启动 Node runner 进程，通过 stdin/stdout JSON-RPC 通信，验证 Python ↔ Node 链路。
不涉及浏览器操作（不需要 Playwright）。

**pytest marker**: `@pytest.mark.integration`

| 测试函数 | 验证内容 |
|---------|---------|
| `test_find_node` | `_find_node()` 能找到 node 可执行文件 |
| `test_runner_starts_and_inits` | 启动 runner → init 配置 → 返回 `{"success": true}` |
| `test_list_sessions_empty` | 初始状态 list_sessions 返回空列表 |
| `test_shutdown_exits_cleanly` | shutdown RPC 后进程正常退出（returncode 0） |

### Layer 2: E2E 冒烟测试（`test_page_agent_e2e.py`）

真实启动 Node runner + Playwright 浏览器 + console-ui dev server + 本地 mock LLM server。

**pytest marker**: `@pytest.mark.e2e`

| 测试函数 | 验证内容 |
|---------|---------|
| `test_navigate_and_screenshot` | execute(url=console-ui, instruction) → 截图成功 → base64 数据非空 |
| `test_execute_with_mock_llm` | mock LLM 返回固定 action → execute 完成 → 返回 page_url/page_title/steps |
| `test_session_lifecycle` | navigate → get_page_info → screenshot → close_session → list_sessions 不含已关闭 session |

## 3. 基础设施

### 3.1 共享 Fixture（`tests/tools/conftest.py` 追加）

#### `node_bin` fixture
调用 `_find_node()` 获取 node 路径，找不到则 `pytest.skip`。

#### `runner_process` fixture（scope=function）
启动 `page-agent-runner.mjs` 子进程，提供 stdin/stdout 读写接口，teardown 时发送 shutdown 并等待退出。

#### `rpc` fixture
封装 JSON-RPC 请求/响应协议：发送 `{"id", "method", "params"}` → 读取带相同 id 的响应行。

### 3.2 Mock LLM Server（`tests/tools/mock_llm_server.py`）

轻量 aiohttp server，监听 `localhost:0`（随机端口），模拟 OpenAI-compatible API：

- `POST /v1/chat/completions` — 根据请求轮次返回固定 page-agent action：
  - 第 1 次请求：返回 `{"action": "done", "data": "Task completed"}` （最简单的完成动作）
- 返回格式符合 OpenAI streaming/non-streaming chat completion 规范

#### `mock_llm` fixture（scope=function）
启动 mock server，返回 `base_url`（如 `http://localhost:19832`），teardown 时关闭。

### 3.3 Console-UI Dev Server

#### `console_ui_server` fixture（scope=session）
在 `console-ui/` 目录执行 `npx vite --port 0`（或固定端口如 15173），等待就绪后返回 URL。
teardown 时 kill 进程。前置条件：`node_modules` 已安装。

### 3.4 pytest marker 注册

在 `pyproject.toml` 中注册：

```toml
markers = [
    "integration: 需要 Node.js 的集成测试",
    "e2e: 需要 Node.js + Playwright + console-ui 的端到端测试",
]
```

## 4. 文件清单

| 操作 | 文件路径 |
|------|---------|
| 新增 | `tests/tools/test_page_agent_integration.py` |
| 新增 | `tests/tools/test_page_agent_e2e.py` |
| 新增 | `tests/tools/mock_llm_server.py` |
| 修改 | `tests/tools/conftest.py`（追加共享 fixture） |
| 修改 | `pyproject.toml`（追加 markers） |

## 5. 跳过策略

- 集成测试：`_find_node()` 返回 None 则 skip
- E2E 测试：额外检查 `console-ui/node_modules/playwright` 和 `console-ui/node_modules/.vite` 存在性，缺失则 skip
- CI 中通过 `-m "not e2e"` 跳过重量级测试

## 6. 验收标准

- `pytest tests/tools/test_page_agent_integration.py -v` 全部通过
- `pytest tests/tools/test_page_agent_e2e.py -v` 全部通过
- 现有 `test_page_agent.py` 不受影响
