---
specanchor:
  level: module
  module_name: "后端网关与会话引擎"
  module_path: "nanobot"
  version: "1.0.0"
  owner: "@git_user"
  author: "@git_user"
  reviewers: []
  created: "2026-03-24"
  updated: "2026-03-24"
  last_synced: "2026-03-24"
  last_change: "由代码推断生成聊天会话与持久化链路规范草稿（待人工确认）"
  status: draft
  depends_on:
    - "console-ui"
---

# 后端网关与会话引擎 (Nanobot Runtime)

> 说明：本 Spec 聚焦聊天会话主链路（`console/routes/chat_routes.py`、`console/services/chat_service.py`、`agent/loop.py`、`session/manager.py`、`storage/database.py`），由代码推断，待人工确认。

## 1. 模块职责

- 暴露聊天管理接口（会话列表、会话创建/删除、历史查询、WebSocket 对话）。
- 组织 Agent 主循环执行（LLM 调用、tool 调用、进度回调、最终回复）。
- 维护会话状态与消息持久化（SQLite 主存储，JSONL 兼容回退）。
- 为控制台提供标准化消息读取接口（含 `tool_calls`、`tool_call_id`、`reasoning_content`）。

## 2. 业务规则

- console 聊天入口使用 `session_key = "console:{session_id}"`，通过 `ChatService.send_message -> AgentLoop.process_direct` 执行。
- Agent 在一个 turn 内可能多轮调用 LLM + 多次工具执行；工具提示通过 `on_progress` 回调即时推送。
- 会话落库时机是“turn 结束后一次性保存”：`_save_turn(...)` 后 `sessions.save(session)`。
- 会话消息是 append-only 结构，角色允许 `user | assistant | tool`，`tool` 通过 `tool_call_id` 回连 assistant 的 `tool_calls`。
- tool 结果写入会话时会进行内容截断（默认 500 字符）以控制上下文膨胀。
- console 独立模式下，Console 进程通过 HTTP/WS 反向代理到 Gateway 聊天接口。

## 3. 对外接口契约

### 3.1 导出 API

| 函数/组件 | 签名 | 说明 |
| --- | --- | --- |
| `ChatService.list_sessions` | `(user_id) -> list[dict]` | 返回会话元信息与消息计数。 |
| `ChatService.create_session` | `(user_id, title="") -> str` | 创建 console 会话并返回 `session_id`。 |
| `ChatService.get_messages` | `(session_key) -> list[dict]` | 返回会话全量消息（含 tool_calls）。 |
| `ChatService.send_message` | `async (session_id, message, user_id, on_progress?) -> str` | 执行一轮会话并返回最终内容。 |
| `AgentLoop.process_direct` | `async (content, session_key, channel, chat_id, on_progress?) -> str` | 直接处理消息入口（CLI/Console 复用）。 |
| `SessionManager.save` | `(session) -> None` | 将会话增量消息写入 DB/JSONL。 |

### 3.2 内部状态

| Store/Context | 字段 | 说明 |
| --- | --- | --- |
| `Session` | `messages`, `last_completed`, `token_stats` | 当前会话内存态与统计。 |
| `SessionManager` | `_cache`, `_saved_counts` | 会话缓存与增量保存游标。 |
| `AgentLoop` | `sessions`, `tools`, `_token_stats` | 运行态依赖与工具执行环境。 |
| `Database` | `sessions`, `session_messages`, `token_usage` | 持久化数据核心表。 |

### 3.3 API 端点（如有）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/chat/sessions` | 获取会话列表。 |
| POST | `/api/chat/sessions` | 创建 console 会话。 |
| DELETE | `/api/chat/sessions/{session_id}` | 删除 console 会话。 |
| GET | `/api/chat/messages?session_key=...` | 获取会话全量消息。 |
| GET | `/api/chat/sessions/{session_id}/history` | 获取 user/assistant 历史。 |
| WS | `/api/chat/ws/{session_id}` | 聊天双向流（progress/thinking/complete）。 |

## 4. 模块内约定

- `Session.key` 命名约定：`<channel>:<chat_id>`；console 固定前缀 `console:`。
- `session_messages.seq` 必须维持时间顺序，读取时按 `ORDER BY seq` 还原会话链路。
- agent 内部消息构造约定：

  - assistant 发起工具调用：`tool_calls` 填充到 assistant 消息。
  - 工具结果：`role=tool` + `tool_call_id` + `name` + `content`。

- WebSocket 进度事件约定为 JSON：`{type, content, tool_hint?}`，最终事件为 `type="complete"`。

## 5. 已知约束 & 技术债

- [ ] 当前 `LLMProvider.chat()` 是一次性返回接口，缺少 token 级流式抽象。
- [ ] turn 内消息在内存中累积，默认在 turn 结束后才批量落库；中途崩溃会丢失本轮未提交步骤。
- [ ] `on_progress` 仅推送文本提示，不推送结构化 toolcall 生命周期事件。
- [ ] `/api/chat/messages` 为全量拉取接口，缺少增量 cursor 协议。
- [ ] `session_messages` 依赖进程内 `_saved_counts` 控制增量写入，缺少 `(session_id, seq)` 的显式唯一约束（待评估）。

## 6. TODO

- [ ] 为 AgentLoop 增加“步骤级 flush”能力（assistant tool_call 写入 + tool result 写入）。
- [ ] 设计统一实时事件协议（`tool_call_started`/`tool_result`/`assistant_delta`/`turn_committed`）。
- [ ] 增加增量消息读取接口（按 `seq` 或时间戳游标）。
- [ ] 评估并补齐幂等与重放安全（重复提交、断线重连场景）。

## 7. 代码结构

- **入口**: `nanobot/console/routes/chat_routes.py`
- **核心链路**: `WS /api/chat/ws/{sid} -> ChatService.send_message -> AgentLoop.process_direct -> _process_message -> _run_agent_loop -> _save_turn -> SessionManager.save`
- **数据流**: `InboundMessage -> LLM/tool 迭代 -> Session.messages -> SQLite(session_messages) -> /api/chat/messages -> console-ui`

**关键文件**:

| 文件 | 职责 |
| --- | --- |
| `nanobot/console/routes/chat_routes.py` | Chat HTTP/WS 路由与鉴权入口。 |
| `nanobot/console/services/chat_service.py` | 会话管理、消息读取、与 AgentLoop 对接。 |
| `nanobot/agent/loop.py` | LLM/tool 循环、进度回调、turn 保存。 |
| `nanobot/session/manager.py` | Session 缓存、增量保存、DB/JSONL 兼容层。 |
| `nanobot/storage/database.py` | SQLite schema 与查询执行。 |
| `nanobot/console/app.py` | 一体化模式与 standalone 代理模式装配。 |

- **外部依赖**: `fastapi`, `pydantic`, `sqlite3`, `loguru`, `websockets`, `httpx`
