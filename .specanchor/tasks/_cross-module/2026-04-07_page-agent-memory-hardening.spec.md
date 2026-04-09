---
specanchor:
  level: task
  task_name: "PageAgent 与后台任务内存硬化"
  author: "@fanghu"
  created: "2026-04-07"
  status: "in_progress"
  last_change: "Execute 完成：page_agent/runner/bg_tasks/loop_patch 内存硬化已落地，定向验证通过（83 passed）"
  related_modules:
    - ".specanchor/modules/ava-tools-page_agent.spec.md"
    - ".specanchor/modules/ava-patches-loop_patch.spec.md"
    - ".specanchor/modules/ava-tools-claude_code.spec.md"
    - ".specanchor/modules/ava-patches-tools_patch.spec.md"
    - ".specanchor/modules/console-ui-src-pages-BrowserPage.spec.md"
  related_tasks:
    - ".specanchor/tasks/2026-04-03_generic-page-agent-tool.md"
    - ".specanchor/tasks/2026-04-04_lifecycle-and-frontend-hotupdate.md"
    - ".specanchor/tasks/2026-04-05_self-improvement-loop-e2e-closure.md"
  related_global:
    - ".specanchor/global-patch-spec.md"
    - ".specanchor/global/architecture.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "REVIEW"
  branch: "feat/0.1.1"
---

# SDD Spec: PageAgent 与后台任务内存硬化

## 0. Open Questions

- [x] **Q1: `page_agent` 未显式传入 `session_id` 时，是否改成每次执行后自动关闭 session？**
  - **结论：本轮不改默认 contract。**
  - 原因：这会改变当前 tool 的隐式会话复用语义，并可能影响依赖返回 `session=` 继续操作的 caller。
  - 本轮改为：保留现有 session 语义，但增加 **bounded retention**（runner 侧 session idle 回收 / 压力淘汰 + Python 侧缓存清扫）。

- [x] **Q2: `loop_patch._agent_loop_ref` 的修法是显式清空还是 `weakref`？**
  - **结论：优先改为 `weakref.ref`。**
  - 原因：`console_patch` 只需要“尽量取到当前 loop”，不需要延长 `AgentLoop` 生命周期；`weakref` 比额外设计 teardown hook 更窄。

- [x] **Q3: `BackgroundTaskStore._finished` 是否保留全量内存历史？**
  - **结论：不保留。SQLite 是真相源。**
  - 本轮改为：内存中仅保留最近完成任务窗口（数量上限 + 时间窗口），超出部分只走 DB 查询。

- [x] **Q4: 本轮目标是“证明真实泄漏”还是“先做风险收敛”？**
  - **结论：先做风险收敛。**
  - 当前代码里已有至少两处真实强引用/无上限增长点；无需先引入 profiler 才开始修。

## 1. Requirements

### 1.1 Goal

对 `page_agent` 运行链路和当前 sidecar patch 做一次**内存硬化**，收敛以下两类问题：

1. **真实对象滞留**：对象被全局注册表或强引用链长期持有，正常业务结束后也无法释放。
2. **无上限缓存增长**：历史/帧/完成任务等数据已落盘，但内存层仍无限累积。

目标不是“把所有内存都降到最低”，而是优先消掉当前最明显、最可验证的泄漏/滞留点，让长跑 gateway 不会因为 `page_agent`、`loop_patch`、`BackgroundTaskStore` 持续涨内存。

### 1.2 In-Scope

- `ava/tools/page_agent.py`
  - 去掉实例级 `atexit.register(self._sync_cleanup)` 带来的强引用滞留
  - 在 runner 退出 / restart / idle shutdown / session close 时清扫 Python 侧缓存
  - 清理失效订阅者/会话态，避免旧 frame/activity 数据残留
- `console-ui/e2e/page-agent-runner.mjs`
  - 为 runner-held Playwright sessions 增加 bounded retention
  - 避免 session 只靠显式 `close_session` 或全局 runner idle timeout 才释放
- `ava/patches/loop_patch.py`
  - 将 `_agent_loop_ref` 改为不延长 `AgentLoop` 生命周期的弱引用持有
- `ava/agent/bg_tasks.py`
  - 为 `_finished` 内存缓存增加 pruning 策略，避免完成任务无限增长
  - 明确“DB 为真相源，内存只保留热窗口”
- 定向测试与相关 module spec 同步

### 1.3 Out-of-Scope

- 不修改 `nanobot/`
- 不引入 repo 级 profiler 基础设施
- 不重做 `page_agent` 工具协议、`session=` 返回格式或 BrowserPage UI
- 不改变显式 `session_id` 的复用语义
- 不把 `page_agent` 改造成“每步操作后都自动关浏览器”的无状态工具
- 不顺手改无关的 console lifecycle / restart 体系

### 1.4 Success Criteria

- `PageAgentTool` 不再因实例级 `atexit` 注册而把旧 tool 实例长期挂到进程退出
- Python 侧 `_event_buffer` / `_last_frame` 不会在 runner 重启或 session 消失后无限保留旧数据
- runner-held Playwright session 会在明确的 bounded retention 策略下被释放，而不是只依赖人工 `close_session`
- `loop_patch` 不再通过模块级强引用长期持有历史 `AgentLoop`
- `BackgroundTaskStore._finished` 内存占用受上限控制，历史查询仍可从 DB 获取
- 以上行为有窄测试覆盖，不把验证扩成整仓库回归

### 1.5 Context Sources

- Requirement Source: 用户要求“检查当前 patch 是否有内存泄漏问题，以及 page agent 相关流程的内存问题；生成修复以上主要问题的 task spec”
- Design Refs:
  - `.specanchor/modules/ava-tools-page_agent.spec.md`
  - `.specanchor/modules/ava-patches-loop_patch.spec.md`
  - `.specanchor/modules/ava-tools-claude_code.spec.md`
- Code Refs:
  - `ava/tools/page_agent.py`
  - `console-ui/e2e/page-agent-runner.mjs`
  - `ava/patches/loop_patch.py`
  - `ava/agent/bg_tasks.py`
  - `ava/console/routes/page_agent_routes.py`
- Verification Refs:
  - `tests/tools/test_page_agent.py`
  - `tests/tools/test_page_agent_runner_contract.py`
  - `tests/agent/test_bg_tasks.py`
  - `tests/patches/test_loop_patch.py`

## 2. Research Findings

### 2.1 当前真实问题

1. **`PageAgentTool` 实例级 `atexit.register()` 会把实例挂到进程退出**
   - 现状：每个 `PageAgentTool` 在 `__init__` 里注册一次 `self._sync_cleanup`
   - 风险：`atexit` 内部强持有 bound method，等价于强持有整个 tool 实例；若 `AgentLoop` 重建多次，旧 tool 即使不再被 `ToolRegistry` 使用，也仍被 `atexit` 持有
   - 性质：真实对象滞留，不是“缓存太多”的软问题

2. **`PageAgentTool` Python 侧缓存只在显式 `close_session` 时清理**
   - 现状：
     - `_event_buffer[session_id]` 保留最近 activity/status
     - `_last_frame[session_id]` 保留最后一帧 base64 图片
     - runner idle shutdown / restart / 异常退出时，这些缓存不会统一 sweep
   - 风险：旧 session 已经在 Node/Playwright 侧消失，但 Python 仍持有 frame/activity 历史，尤其 frame 是大对象

3. **runner-held Playwright sessions 缺少 session 级回收策略**
   - 现状：session 只在以下场景释放：
     - 调用 `close_session`
     - `shutdown`
     - 整个 runner idle timeout 触发
   - 风险：长时间使用 `page_agent` 时，即使调用方不再关心旧 session，浏览器 page/context 也会一直留在 runner 内存里
   - 注：`MAX_SESSIONS=5` 只是硬上限，不是回收策略

4. **`loop_patch._agent_loop_ref` 是模块级强引用**
   - 现状：最近创建的 `AgentLoop` 被全局变量直接持有
   - 风险：这会增加 teardown 复杂度，并让旧 loop 的释放依赖于显式覆盖而不是 GC 自然回收

5. **`BackgroundTaskStore._finished` 无上限保留完成任务**
   - 现状：完成任务会从 `_active` 移到 `_finished`，无 TTL、无数量上限
   - 风险：每个 snapshot 都带 `timeline` / preview / metadata；长跑网关会持续增长，而这些数据其实已经同步写入 SQLite

### 2.2 当前不是主问题的点

- `page_agent_routes.py` 的 WS finally 已有 `unsubscribe + stop_screencast`，正常断链不会把订阅永远挂住
- runner 的 `close_session()` / `shutdown()` 已明确关闭 `page` / `context` / `browser`
- `TokenStatsCollector` / `MediaService` 当前主存储在 DB，不是这次的主要内存增长源

### 2.3 风险排序

| 级别 | 问题 | 原因 |
|------|------|------|
| P1 | `PageAgentTool` 实例级 `atexit` 强持有 | 真实对象滞留 |
| P1 | `BackgroundTaskStore._finished` 无上限 | 长跑网关必涨 |
| P2 | `PageAgentTool` 缓存未在 runner/session 消失时 sweep | frame/activity 可持续累积 |
| P2 | runner session 缺少 session 级 eviction | 浏览器资源滞留 |
| P3 | `_agent_loop_ref` 强引用 | teardown 不干净，但影响面较窄 |

### 2.4 Next Actions

- 先收敛 Python 侧真实滞留点：`atexit`、`_finished`、`_agent_loop_ref`
- 再给 runner session 增加 bounded retention，而不是改 tool contract
- 最后补定向测试，确保清理逻辑不会误伤现有 `/browser` 预览链路

## 3. Innovate

### Option A: 只做 Python 侧内存硬化

- Pros:
  - 改动最窄
  - 直接解决最明显的真实泄漏点
  - 对现有 page-agent tool contract 几乎零影响
- Cons:
  - Node/Playwright session 仍可能长期驻留
  - 只能缓解，不算彻底收住 page agent 资源面

### Option B: Python 侧硬化 + runner 侧 bounded retention

- Pros:
  - 同时收住“真实泄漏”和“资源长期驻留”两类问题
  - 不需要改变 `session=` 协议或强制 auto-close
  - 对 BrowserPage / console 预览仍兼容
- Cons:
  - 会触及 Python + Node 两侧
  - 需要更清晰地定义 session idle / eviction 规则

### Option C: 改成无状态 page_agent，每次执行后强制关 session

- Pros:
  - 内存面最简单
  - 不需要 runner session 管理
- Cons:
  - 直接改变当前 tool 语义
  - 会破坏显式/隐式 session 复用链路
  - 与已有 `session=` 解析和 BrowserPage 调试链不一致

### Decision

- Selected: **Option B**
- Why:
  - 当前问题不只在 Python 侧，也包括 runner session 驻留
  - 但不值得用“改成无状态工具”这种高破坏性手段来止血
  - 最合适的修法是：**保持当前 tool contract，不改调用面；在实现层补 bounded retention 和缓存清扫**

### Skip

- Skipped: false
- Reason: 这是跨 `page_agent + loop_patch + bg_tasks` 的多模块任务，且已经命中多个高价值内存问题，不适合跳过方案比较

## 4. Plan (Contract)

### 4.1 File Changes

- `ava/tools/page_agent.py`
  - 将实例级 `atexit` 注册改为进程级单次注册或弱引用清理机制
  - 为 runner shutdown / runner exit / restart / session close 增加统一缓存清扫入口
  - 对 `_subscribers` / `_event_buffer` / `_last_frame` 做 stale session sweep
- `console-ui/e2e/page-agent-runner.mjs`
  - 为 session 增加 `lastTouched` / `createdAt` 等元数据
  - 增加 session idle eviction 或 oldest-inactive eviction
  - 保证 eviction 与 `start_screencast` / `close_session` / `shutdown` 路径兼容
- `ava/patches/loop_patch.py`
  - 把 `_agent_loop_ref` 改成 `weakref.ref`
  - 调整 `get_agent_loop()` 返回解引用后的实例或 `None`
- `ava/agent/bg_tasks.py`
  - 增加 `_finished` pruning 机制（数量上限 + 可选时间窗口）
  - 迁移完成任务时调用 prune，必要时对 timeline 做内存侧裁剪
- `tests/tools/test_page_agent.py`
  - 补 `PageAgentTool` 清理逻辑测试
  - 补 runner shutdown / restart 后 Python 缓存被清扫的测试
- `tests/agent/test_bg_tasks.py`
  - 补 `_finished` pruning 行为测试
- `tests/patches/test_loop_patch.py`
  - 补 weakref 生命周期行为测试
- `.specanchor/modules/ava-tools-page_agent.spec.md`
  - 同步 session retention / cache cleanup 行为
- `.specanchor/modules/ava-patches-loop_patch.spec.md`
  - 同步 `_agent_loop_ref` 生命周期语义
- `.specanchor/modules/ava-tools-claude_code.spec.md`
  - 同步 `BackgroundTaskStore` 的 in-memory retention policy

### 4.2 Signatures

- `ava.tools.page_agent.PageAgentTool`
  - `_register_process_cleanup() -> None`
  - `_clear_session_state(session_id: str | None = None) -> None`
  - `_sweep_stale_sessions(active_session_ids: set[str] | None = None) -> None`
- `ava.agent.bg_tasks.BackgroundTaskStore`
  - `_prune_finished() -> None`
- `ava.patches.loop_patch`
  - `get_agent_loop() -> object | None`（实现改为 weakref 解引用）

### 4.3 Implementation Checklist

- [x] 1. `PageAgentTool` 去实例级 `atexit` 强引用，改为不持有历史 tool 实例的清理机制
- [x] 2. 为 `PageAgentTool` 增加统一 session/cache 清扫逻辑，并接入 `close_session`、`_shutdown_runner()`、runner exit 分支
- [x] 3. 为 runner session 增加 bounded retention（idle eviction 或 oldest-inactive eviction），不改显式 `session_id` 语义
- [x] 4. 将 `loop_patch._agent_loop_ref` 改成 weakref 持有，避免旧 `AgentLoop` 被模块级强引用滞留
- [x] 5. 为 `BackgroundTaskStore._finished` 增加 pruning 机制，确保内存只保留热窗口，SQLite 继续作为历史真相源
- [x] 6. 补齐定向测试，覆盖：对象不再被强持有、缓存在 shutdown/restart 后被清扫、完成任务缓存受上限控制
- [x] 7. 同步相关 Module Spec，避免 task spec / module spec 与实现再次漂移

## 5. Execute Log

- [x] Step 1: 创建 Task Spec，固化 page_agent / loop_patch / bg_tasks 的主要内存问题与修复边界
- [x] Step 2: 用户确认 `Plan Approved`，切换到 Execute 阶段
- [x] Step 3: 实现 `PageAgentTool` 的 atexit 去强引用与 Python 侧缓存清扫
- [x] Step 4: 实现 runner session bounded retention
- [x] Step 5: 实现 `loop_patch` weakref 与 `BackgroundTaskStore` finished pruning
- [x] Step 6: 补定向测试并同步 module spec

## 6. Review Verdict

- Spec coverage: PASS
- Behavior check: PASS
- Regression risk: Low-Medium
- Module Spec 需更新: No（已同步）
- Follow-ups:
  - 若本轮上线后仍观察到浏览器内存长期升高，再决定是否增加更强的 session pressure policy（例如显式 max idle ms + force close oldest）
  - 若后续需要真实 heap 证据，再补轻量 profiler / metrics，不作为本轮前置条件

## 7. Plan-Execution Diff

- Execute 基本遵循原 Plan：按 `page_agent` → runner → `loop_patch` → `bg_tasks` 顺序落地
- 额外补了一条 `BackgroundTaskStore.get_status(task_id=...)` 的 DB fallback，避免 `_finished` prune 之后 console 单任务详情丢失
- runner 侧额外发出 `session_closed` 事件，确保 Python 侧能在 session 被 eviction/close/shutdown 时即时清缓存，而不是只靠下次 RPC 猜测
