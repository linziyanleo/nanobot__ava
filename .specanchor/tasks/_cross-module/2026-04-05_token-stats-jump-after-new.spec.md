---
specanchor:
  level: task
  task_name: "修复 /new 后 Token 统计 turn 跳转串线"
  author: "@fanghu"
  created: "2026-04-05"
  status: "in_progress"
  last_change: "Execute 收尾：修复 legacy DB 升级顺序、补齐 /new conversation_id 分段回归测试，并消除 ChatPage conversation_id 刷新竞态"
  related_modules:
    - ".specanchor/modules/ava-patches-loop_patch.spec.md"
    - ".specanchor/modules/ava-patches-storage_patch.spec.md"
    - ".specanchor/modules/ava-patches-console_patch.spec.md"
  related_tasks:
    - ".specanchor/tasks/2026-04-03_console-realtime-dataflow-enhancement.md"
    - ".specanchor/tasks/fix-token-stats-recording.md"
  related_global:
    - ".specanchor/global-patch-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "EXECUTE"
  branch: "feat/0.1.1"
---

# SDD Spec: 修复 /new 后 Token 统计 turn 跳转串线

## 0. Open Questions

- [x] `/new` 是不是创建了新的 `session_key`？
  → 不是。当前生效的是 `nanobot/command/builtin.py::cmd_new()`，它复用同一 `session_key`，只执行 `session.clear()` + `save()` + `invalidate()`。
- [x] 当前问题是不是“当前 turn 来源不对”？
  → 只问了一半。真正问题是 **逻辑会话被重置了，但 token 统计仍只靠 `session_key + turn_seq` 标识**，所以 `/new` 后 Turn #0 / #1 / ... 会和旧记录撞键。
- [x] `ava/agent/commands.py` 能不能直接改？
  → 不能作为主路径。该文件目前只是 sidecar 内复制稿，真实 slash command dispatch 走的是上游 `nanobot.command.register_builtin_commands()`。
- [x] 旧历史中没有 `conversation_id` 的 token 记录，升级后在 Token Stats 页如何展示？
  → 已落地：全局审计 / 未带 `conversation_id` 的 records 查询仍保留 legacy 记录；从 Chat 页进入的单 Session 调试显式携带当前 `conversation_id`，避免 `/new` 前后同序号 turn 混合。

## 1. Requirements (Context)

- **Goal**: 修复 `/new` 之后 Token 统计页、Chat 页 token badge、以及 turn 级跳转的串线/覆盖问题，使“逻辑新会话”拥有稳定锚点。
- **In-Scope**:
  - 为同一 `session_key` 下被 `/new` 切分的不同逻辑会话引入稳定标识
  - token_usage 记录链路补记该标识，并支持查询/聚合/跳转过滤
  - ChatPage → TokenStatsPage 路由从 `session_key + turn_seq` 升级为稳定组合键
  - `/stats/tokens/by-session` / `/detailed` / `/records` 的 contract 与 UI 对齐
  - 最小必要测试：`/new` 后新旧记录不再按同一 turn 聚合
- **Out-of-Scope**:
  - 不重做全站 Session / Chat 架构
  - 不追求一次性修复所有历史缺失 `turn_seq` / 缺失 conversation 边界的旧数据
  - 不修改 `nanobot/`，除非后续确认必须作为 upstream bugfix 提交

## 1.1 Context Sources

- Requirement Source: 用户报告“Token统计页面跳转有问题；`/new` 会更新当前 turn，导致记录覆盖之前的 turn”
- Code Refs:
  - `nanobot/command/builtin.py::cmd_new`
  - `nanobot/agent/loop.py::_process_message`
  - `ava/patches/loop_patch.py::patched_process_message`
  - `ava/console/services/token_stats_service.py`
  - `console-ui/src/pages/ChatPage/TokenInfoPopover.tsx`
  - `console-ui/src/pages/ChatPage/MessageBubble.tsx`
  - `console-ui/src/pages/TokenStatsPage.tsx`
- Related Task Refs:
  - `.specanchor/tasks/2026-04-03_console-realtime-dataflow-enhancement.md`
  - `.specanchor/tasks/fix-token-stats-recording.md`

## 2. Research Findings

- `cmd_new()` 复用原 `session_key`，只清空 `session.messages`。这意味着逻辑上开始了新会话，但主键层面没有切 session。
- `loop_patch` 当前用“已有 user message 数量”计算 `_current_turn_seq`。`/new` 清空后，下一个 turn 会重新从 0 开始。
- Chat 页与 Token Stats 页当前跳转 contract 只有 `session_key + turn_seq`。对应实现位于 `TokenInfoPopover.tsx`、`MessageBubble.tsx` 和 `TokenStatsPage.tsx` 的 query params。
- `TokenStatsCollector` 的 `get_by_session()` / `get_by_session_detailed()` / `get_records()` 也都只按 `session_key`、`turn_seq` 聚合和过滤，没有“逻辑会话分代”维度。
- 因此问题不在于“换一个 current turn 来源”。只要继续用 `session_key + turn_seq`，`/new` 后新 turn 仍会和旧记录撞在一起。
- 现有 `record_id` 已经稳定，但它只能唯一标识单条 LLM 调用，不能单独解决“turn 聚合”和“turn 级页面跳转”在 `/new` 后的串线。

## 2.1 Next Actions

- 给 session metadata 与 token_usage 引入 conversation 级稳定键
- 让 ChatPage / TokenStatsPage 跳转与查询显式携带该键
- 用一条 `/new` 场景测试锁死“不再复用旧 turn 聚合”

## 3. Innovate

### Option A：跳转改用 `record_id`

- Pros: 前端 landing 改动最小，单条记录定位稳定
- Cons: 无法解决 `/stats/tokens/by-session` 的 turn 聚合碰撞；同一 `session_key` 下 `/new` 前后的 Turn #0 仍会混在一起

### Option B：引入 `conversation_id`，turn 只在 conversation 内编号

- Pros:
  - 能精确表达“同一 session_key 下的多段逻辑会话”
  - 兼容现有 `turn_seq` 语义，turn 视图改动可控
  - ChatPage token badge、TokenStatsPage、record query 可以统一 contract：`session_key + conversation_id + turn_seq`
- Cons:
  - 需要补 DB 字段、查询参数、前端路由和测试
  - 旧历史数据不一定能完全自动 backfill 出正确 `conversation_id`

### Option C：用 `/new` 时间戳做边界推断

- Pros: 看起来不用加新字段
- Cons: 依赖推断；跨时区、历史数据、异步记录顺序都可能出错，长期不可维护

### Decision

- Selected: **Option B**
- Why: 这是首个能同时修复“turn 聚合”“页面跳转”“Chat 页 token badge 对齐”的最小闭环方案。`record_id` 可以作为后续增强，但不能替代逻辑会话边界键。
- Skipped: false

## 4. Plan (Contract)

### 4.1 File Changes

- `ava/patches/loop_patch.py`
  - 增加 session conversation 上下文初始化 helper
  - 普通消息进入时确保 `session.metadata["conversation_id"]` 存在
  - `/new` 进入原始 dispatch 前先轮换新的 `conversation_id`，让清空后的会话立即进入新逻辑分段
  - Phase 0 与后续 iteration 记录都写入 `conversation_id`
- `ava/storage/database.py`
  - `token_usage` 增加 `conversation_id` 列
  - 增加 `(session_key, conversation_id, turn_seq)` 索引
- `ava/console/services/token_stats_service.py`
  - `TokenUsageRecord` / `record()` / 查询过滤增加 `conversation_id`
  - `get_by_session()` / `get_by_session_detailed()` 改为按 `conversation_id, turn_seq` 过滤 / 聚合
  - 保留 legacy 兼容：无 `conversation_id` 时仍可全局审计查询
- `ava/console/routes/token_routes.py`
  - 新增 `conversation_id` query param
- `ava/console/services/chat_service.py`
  - session list / create path 暴露当前 `conversation_id`
- `console-ui/src/pages/ChatPage/types.ts`
  - `SessionMeta`、`TurnTokenStats`、`IterationTokenStats` 增加 `conversation_id`
- `console-ui/src/pages/ChatPage/MessageArea.tsx`
  - 拉取 turn stats 时显式带当前 session 的 `conversation_id`
- `console-ui/src/pages/ChatPage/TokenInfoPopover.tsx`
  - 跳转 Token Stats 时携带 `conversation_id`
- `console-ui/src/pages/ChatPage/MessageBubble.tsx`
  - 右侧 token 快捷跳转携带 `conversation_id`
- `console-ui/src/pages/TokenStatsPage.tsx`
  - 读取并应用 `conversation_id`
  - 单 Session 调试模式下展示当前 conversation 视图，避免 `/new` 前后的同序号 turn 混合
- `tests/patches/test_loop_patch.py`
  - 新增 `/new` 后 conversation_id 轮换与 token record 分段测试
- `tests/console/*` 或 `tests/patches/*`
  - 补 token stats query / filter 的 conversation_id 合约测试

### 4.2 Signatures

- `TokenUsageRecord.conversation_id: str = ""`
- `TokenStatsCollector.record(..., conversation_id: str = "") -> int | None`
- `TokenStatsCollector.get_records(..., conversation_id: str | None = None) -> list[dict[str, Any]]`
- `TokenStatsCollector.get_by_session(session_key: str, conversation_id: str | None = None) -> list[dict[str, Any]]`
- `TokenStatsCollector.get_by_session_detailed(session_key: str, conversation_id: str | None = None) -> list[dict[str, Any]]`
- `SessionMeta.conversation_id?: string`

### 4.3 Implementation Checklist

- [x] 1. 确认 `loop_patch` 中 `/new` 前置轮换 `conversation_id` 的最小拦截点，并保证不改 `nanobot/`
- [x] 2. 扩展 `token_usage` schema 与 `TokenStatsCollector.record()`，把 `conversation_id` 写入所有新记录
- [x] 3. 扩展 token stats query / filter contract，支持 `conversation_id`
- [x] 4. 扩展 Chat session metadata 暴露，让前端拿到当前 `conversation_id`
- [x] 5. 修改 ChatPage token badge / popover / quick jump，统一携带 `conversation_id`
- [x] 6. 修改 TokenStatsPage 单 Session 调试模式，按 `conversation_id + turn_seq` 展示
- [x] 7. 增加 `/new` 回归测试：旧 Turn #0 与新 Turn #0 不再聚合到同一组
- [x] 8. 增加 legacy 兼容测试：无 `conversation_id` 旧记录仍可在全局审计中查看

## 5. Execute Log

- [x] 2026-04-05：Plan Approved，进入 Execute。按 `loop_patch → storage/token_stats → console-ui` 顺序落地 `conversation_id` 分段修复。
- [x] 2026-04-05：修复 `ava/storage/database.py` 的旧库升级顺序；将 `idx_tu_conv_turn` 改为 post-migration 创建，避免 legacy `token_usage` 尚未补列时初始化直接失败。
- [x] 2026-04-05：补齐 `tests/patches/test_loop_patch.py` 的 `/new` conversation 轮换 + legacy 审计兼容测试，以及 `tests/patches/test_storage_patch.py` 的 legacy DB 升级测试。
- [x] 2026-04-05：修复 `console-ui/src/pages/ChatPage/index.tsx` 在 WS 完成后先刷 session list 再带最新 meta 重载消息，避免 `/new` 后短时间仍拿旧 `conversation_id`。

## 6. Review Verdict

- Spec coverage: PASS
- Behavior check: PASS
- Regression risk: Medium-Low
- Module Spec 需更新: Yes
- Follow-ups:
  - `ava-patches-loop_patch.spec.md` 与 `ava-patches-storage_patch.spec.md` 已同步本次 `conversation_id` / legacy migration contract；若后续再扩展 Token Console 面，建议补独立 module spec

## 7. Plan-Execution Diff

- Plan 未显式写出的两个实现细节已在 Execute 中补齐：
  - legacy SQLite 升级必须先补 `conversation_id` 列，再建 `(session_key, conversation_id, turn_seq)` 索引，否则旧库初始化会直接失败
  - ChatPage 仅刷新 session list 还不够；若消息重载继续带旧 meta，会短暂回退到旧 `conversation_id`，所以改成“先拉最新 session meta，再按该 meta 重载消息”
