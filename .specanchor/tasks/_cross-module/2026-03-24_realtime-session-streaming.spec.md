---
specanchor:
  level: task
  task_name: "会话记录实时更新可行性分析与双模块规范产出"
  author: "@git_user"
  assignee: "@git_user"
  reviewer: "@git_user"
  created: "2026-03-24"
  status: "review"
  last_change: "完成双模块代码链路分析并产出 Module Spec 草稿"
  related_modules:
    - ".specanchor/modules/console-ui.spec.md"
    - ".specanchor/modules/nanobot.spec.md"
  related_global:
    - ".specanchor/global/coding-standards.spec.md"
    - ".specanchor/global/architecture.spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "REVIEW"
  branch: "feat/0.0.1"
---

# SDD Spec: 会话记录实时更新可行性分析与双模块规范产出

## 0. Open Questions

- [x] 现有后端是否在每次 tool_call 增量阶段就持久化 turn（而非仅 turn 结束后持久化）？→ 否，当前为 turn 结束后统一 `sessions.save()`。
- [x] console-ui 当前是否具备对流式 session 增量事件的订阅机制（SSE/WebSocket）？→ 仅 console 场景有 WebSocket，且事件为文本进度，不含结构化 toolcall。

## 1. Requirements (Context)

- **Goal**: 评估“user 信息与 toolcall 步骤实时更新到 UI 与数据库”的可行性，并产出 `console-ui` 与 `nanobot` 的 Module Spec 草稿。
- **In-Scope**:

  - 梳理会话记录在 `nanobot` 的生成、更新、持久化路径
  - 梳理 `console-ui` 的会话加载、展示与刷新机制
  - 给出当前架构下实时更新方案可行性、改造点与风险
  - 生成两个模块的 Spec 文档（草稿）

- **Out-of-Scope**:

  - 不实现实时流式改造代码
  - 不引入新的基础设施（如消息队列）生产部署方案

## 1.1 Context Sources

- Requirement Source: 用户本次需求描述（实时会话更新 + Module Spec）
- Design Refs: `.specanchor/global/architecture.spec.md`
- Chat/Business Refs: N/A
- Extra Context: 现有 `.specanchor/modules/nanobot-channels.spec.md` 作为风格参考

## 2. Research Findings

- `console-ui/src/pages/ChatPage/index.tsx`：console 场景通过 WS 接收 `thinking/progress/complete`，`complete` 才触发 `/chat/messages` 全量重拉。
- `nanobot/agent/loop.py`：`_run_agent_loop()` 内执行 LLM/tool 迭代；`_save_turn()` + `sessions.save()` 在 turn 结束后调用，未做步骤级落库。
- `nanobot/console/routes/chat_routes.py`：WS 仅透传 progress/thinking 文本块与最终 complete，不包含结构化 toolcall 生命周期事件。
- `nanobot/session/manager.py` + `nanobot/storage/database.py`：会话存储是 append-only，可支持增量写入，但当前调用点是回合级。
- 可行性判断：在现有架构上实现“步骤级实时 UI + 实时落库”是可行的，主要改造在 AgentLoop 事件回调、WS 事件协议、前端状态归并与增量接口。

## 2.1 Next Actions

- 已完成，进入 Review 阶段。

## 3. Innovate (Optional: Options & Decision)

### Option A（低改造）

- 方案：保持现有 `/chat/messages` 全量接口，新增结构化 WS 事件，仅前端内存实时渲染。
- Pros：上线快，对存储层侵入小。
- Cons：DB 仍是回合级提交，刷新/重连一致性弱。

### Option B（推荐）

- 方案：在 AgentLoop 工具步骤处增加增量 flush（assistant tool_call + tool result），WS 同步结构化事件，前端按事件 reducer 更新 turn。
- Pros：UI 与 DB 都可步骤级更新，重连后可从 DB 恢复。
- Cons：需要改造事件协议与写入时机，测试面更大。

### Decision

- Selected: Option B
- Why: 符合“实时展示 + 实时落库”双目标，且可复用现有 append-only 会话模型。

### Skip (for small/simple tasks)

- Skipped: false
- Reason: 任务需比较多种实时化方案并选择可落地路径。

## 4. Plan (Contract)

### 4.1 File Changes

- `.specanchor/tasks/_cross-module/2026-03-24_realtime-session-streaming.spec.md`: 本任务过程记录
- `.specanchor/modules/console-ui.spec.md`: 新建/更新 console-ui 模块规范
- `.specanchor/modules/nanobot.spec.md`: 新建/更新 nanobot 模块规范
- `.specanchor/module-index.md`: 同步模块索引（如新增 Module Spec 文件）

### 4.2 Signatures

- `N/A`（本任务为架构与规范分析，不涉及新增代码 API）

### 4.3 Implementation Checklist

- [x] 1. 完成 console-ui 聊天会话链路调研
- [x] 2. 完成 nanobot 会话与 toolcall 持久化链路调研
- [x] 3. 输出实时更新可行性结论与建议
- [x] 4. 产出 `console-ui` Module Spec 草稿
- [x] 5. 产出 `nanobot` Module Spec 草稿
- [x] 6. 回写本任务 Spec 的 Review 结论

## 5. Execute Log

- [x] 创建 Task Spec 并加载 Global Spec 上下文。
- [x] 分析前端链路：`ChatPage` 状态流、WS 事件处理、turn 分组、toolcall 展示逻辑。
- [x] 分析后端链路：`chat_routes -> chat_service -> agent.loop -> session.manager -> database`。
- [x] 生成 `console-ui.spec.md`、`nanobot.spec.md` 两个 Module Spec 草稿。
- [x] 更新 `.specanchor/module-index.md` 索引。

## 6. Review Verdict

- Spec coverage: PASS（覆盖 `console-ui` 与 `nanobot` 目标模块）
- Behavior check: PASS（仅新增/更新 Spec 文档，无业务代码变更）
- Regression risk: Low（未改运行时代码）
- Module Spec 需更新: Yes（后续若落地实时增量写入，需要同步更新两个模块 Spec）
- Follow-ups:

  - 设计并实现结构化 WS 事件协议。
  - 在 AgentLoop 增加步骤级写入钩子与幂等策略。
  - 增加增量消息读取接口（cursor/seq）。

## 7. Plan-Execution Diff

- 无偏差。按计划完成调研、可行性结论与 Module Spec 产出。
