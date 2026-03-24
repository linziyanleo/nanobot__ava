---
specanchor:
  level: module
  module_name: "控制台前端"
  module_path: "console-ui"
  version: "1.0.0"
  owner: "@git_user"
  author: "@git_user"
  reviewers: []
  created: "2026-03-24"
  updated: "2026-03-24"
  last_synced: "2026-03-24"
  last_change: "由代码推断生成聊天会话链路规范草稿（待人工确认）"
  status: draft
  depends_on:
    - "nanobot/console/routes/chat_routes.py"
    - "nanobot/console/services/chat_service.py"
---

# 控制台前端 (Console UI)

> 说明：本 Spec 聚焦 `ChatPage` 会话链路（由代码推断，待人工确认）。

## 1. 模块职责

- 提供聊天会话 UI（Session 列表、消息区、输入区、搜索、工具调用展示）。
- 维护 console 场景 WebSocket 会话并消费进度事件（`thinking` / `progress` / `complete`）。
- 将后端原始消息结构（user/assistant/tool）归并为 Turn 视图，驱动 Tool Call 与结果可视化。
- 通过 REST API 加载会话列表、全量消息和 token 统计。

## 2. 业务规则

- 会话列表固定轮询：`30s`；非 console 场景消息固定轮询：`10s`。
- console 场景发送消息后先做本地乐观更新（插入用户 turn），最终在 `complete` 事件后重新拉取全量消息。
- 工具调用展示依赖持久化消息：assistant 的 `tool_calls` 与 tool 消息按 `tool_call_id` 关联。
- 搜索范围是当前已加载 turns（纯前端匹配，不访问额外后端搜索接口）。
- WebSocket 出错或关闭时会终止发送态（由代码推断，待人工确认）。

## 3. 对外接口契约

### 3.1 导出 API

| 函数/组件 | 签名 | 说明 |
| --- | --- | --- |
| `ChatPage` | `() => JSX.Element` | 聊天主页面，管理会话状态与消息流。 |
| `groupTurns` | `(messages: RawMessage[]) => TurnGroup[]` | 原始消息按 user turn 归并。 |
| `TurnGroupComponent` | `(props) => JSX.Element` | 单轮消息 + tool call 展示。 |
| `ToolCallBlock` | `(props) => JSX.Element` | tool 参数、结果与媒体预览展示。 |

### 3.2 内部状态

| Store/Context | 字段 | 说明 |
| --- | --- | --- |
| `ChatPage state` | `sessions`, `activeScene`, `activeSession` | 当前会话上下文。 |
| `ChatPage state` | `turns`, `loadingMessages` | 消息渲染主状态。 |
| `ChatPage state` | `streaming`, `thinkingStreaming`, `sending` | WebSocket 进度与发送状态。 |
| `ChatPage ref` | `wsRef` | console 会话 WebSocket 连接。 |
| `MessageArea state` | `turnTokenStats`, `showSearch`, `refreshing` | 展示增强状态。 |

### 3.3 API 端点（如有）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/chat/sessions` | 获取会话列表。 |
| POST | `/api/chat/sessions` | 创建 console 会话。 |
| DELETE | `/api/chat/sessions/{session_id}` | 删除 console 会话。 |
| GET | `/api/chat/messages?session_key=...` | 拉取会话全量消息。 |
| WS | `/api/chat/ws/{session_id}` | console 场景双向消息流。 |
| GET | `/api/stats/tokens/by-session?session_key=...` | 按会话查询 turn token 统计。 |
| DELETE | `/api/files/delete` | 非 console 会话按文件路径删除（兼容路径）。 |

## 4. 模块内约定

- Session Key 约定为 `<scene>:<id>`，console 会话使用 `console:<session_id>`。
- WebSocket 事件类型约定：`thinking`、`progress`、`complete`；前端未知事件默认忽略。
- Turn 分组以 user 消息为边界，assistant/tool 消息归并到最近 user turn。
- 工具结果展示优先使用结构化消息，其次做文本解析（如 image_gen 结果路径提取）。

## 5. 已知约束 & 技术债

- [ ] WebSocket 当前只发送文本进度，不发送结构化 toolcall 开始/结束事件。
- [ ] console 场景工具步骤无法“边执行边落 UI 结构化节点”，需要等 `complete` 后重拉历史。
- [ ] `/api/chat/messages` 为全量拉取，消息量大时增量刷新成本高。
- [ ] 非 console 会话依赖轮询，不是事件驱动。
- [ ] 会话重命名接口尚未实现，UI 为占位逻辑。

## 6. TODO

- [ ] 增加结构化实时事件（tool_call_started/tool_result/assistant_delta）。
- [ ] 增加增量消息接口（cursor/seq），替代全量拉取。
- [ ] 完成会话重命名端到端接口与 UI。
- [ ] 统一 console 与非 console 的会话更新机制（推送优先，轮询兜底）。

## 7. 代码结构

- **入口**: `console-ui/src/pages/ChatPage/index.tsx`
- **核心链路**: `用户发送 -> WS /api/chat/ws/{sid} -> progress/thinking/complete -> GET /chat/messages -> groupTurns -> TurnGroup 渲染`
- **数据流**: `后端 RawMessage[] -> groupTurns() -> TurnGroup[] -> MessageBubble/ToolCallBlock`

**关键文件**:

| 文件 | 职责 |
| --- | --- |
| `console-ui/src/pages/ChatPage/index.tsx` | 会话加载、场景切换、WS 管理、发送消息。 |
| `console-ui/src/pages/ChatPage/utils.ts` | turn 分组、消息文本提取与格式化。 |
| `console-ui/src/pages/ChatPage/TurnGroup.tsx` | 每个 turn 的 user/tool/assistant 组合渲染。 |
| `console-ui/src/pages/ChatPage/ToolCallBlock.tsx` | 工具参数与结果展示、媒体特殊渲染。 |
| `console-ui/src/api/client.ts` | REST 与 WS URL 统一封装。 |

- **外部依赖**: `react`, `react-markdown`, `remark-gfm`, `react-syntax-highlighter`, `lucide-react`
