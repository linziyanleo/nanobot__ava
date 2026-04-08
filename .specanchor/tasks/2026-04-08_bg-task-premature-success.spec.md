---
specanchor:
  level: task
  task_name: "后台任务中途误标 SUCCESS"
  author: "@Ziyan Lin"
  assignee: "@Ziyan Lin"
  reviewer: ""
  created: "2026-04-08"
  status: "draft"
  last_change: "修正 PLAN：将 max_turns 收敛为 interrupted/resumable，移除对 auto_continue 的错误假设"
  related_modules:
    - ".specanchor/modules/claude_code_tool_spec.md"
  related_global:
    - ".specanchor/global/architecture.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "feat/0.1.1"
---

# SDD Spec: 后台任务中途误标 SUCCESS

## 0. Open Questions

- [x] SUCCESS 标记的来源 → **已确认**：`_execute_background` 未检查 `is_error`/`terminal_reason`，正常返回后 `_run()` 无条件标记 `succeeded`
- [x] CLI 在 `max_turns` 时的真实终止信号 → **已确认**：`subtype="error_max_turns"`、`is_error=true`、`terminal_reason="max_turns"`
- [x] `auto_continue` 是否等于 Claude session resume → **已确认否**：当前 `_trigger_continuation()` 只是把文本结果重新喂给主 Agent，不会带 `cli_session_id` 调 `claude --resume`
- [ ] 当前任务是否一并补 `cli_session_id -> claude --resume` 真续跑闭环（建议拆 follow-up；本任务先止血）

## 1. Requirements (Context)

- **Goal**: 修复后台任务（Background Task）在 `max_turns` 等中断场景下被误标为 `SUCCESS` 的问题，同时避免把“可恢复中断”错误收敛成通用 `ERROR`。
- **In-Scope**:
  - `BackgroundTaskStore` 的任务完成分类（`succeeded / interrupted / failed`）
  - `ClaudeCodeTool` 异步结果的终止原因识别
  - 完成回调文案与持久化内容，确保用户能看见真实终止原因
- **Out-of-Scope**:
  - 真正的 Claude session 自动续跑（消费 `cli_session_id` 并重新调用 `claude --resume`）
  - 同步模式（sync）的执行链
  - Console UI 独立展示改造（本任务只保证其消费到正确状态文本）

## 1.1 Context Sources

- Requirement Source: 用户在对话中报告的 bug（后台任务中途标记 SUCCESS）
- Design Refs: `.specanchor/modules/claude_code_tool_spec.md`
- Chat/Business Refs: 用户对话上下文
- Extra Context: 用户提到 "cc哥虽然标记SUCCESS，但实际上只是分析了文件结构，说要用Python脚本来做修改，但没真正执行完"

## 2. Research Findings

### 2.1 根因分析

**Bug 链路**：Claude CLI 用完 `max_turns` 后返回有效 JSON → `_execute_background` 未检查终止原因 → `_run()` 将状态标记为 `succeeded` → 用户看到 SUCCESS

详细链路：

1. `ClaudeCodeTool._execute_background()`（`claude_code.py:174-199`）启动 `claude` CLI 子进程
2. Claude CLI 达到 `max_turns` 上限后返回有效 JSON，其中 `subtype="error_max_turns"`、`is_error=true`、`terminal_reason="max_turns"`
3. `_execute_background` 只检查了两种失败条件：
   - `stderr and not stdout`（纯 stderr 失败）→ raise RuntimeError
   - `parsed.get("_parse_error")`（JSON 解析失败）→ raise RuntimeError
   - **未检查 `is_error`、`subtype`、`terminal_reason` 字段**
4. `_execute_background` 正常返回 `parsed` 字典
5. `BackgroundTaskStore._run()`（`bg_tasks.py:163-168`）收到正常返回，设置 `snapshot.status = "succeeded"`
6. `_on_complete` 输出 `[Background Task xxx SUCCESS]`

### 2.2 实证：Claude CLI JSON 完整输出字段

通过实际运行 `claude -p ... --output-format json --max-turns 1` 确认的完整字段列表：

| 字段 | 类型 | max_turns 退出时的值 | 说明 |
|------|------|---------------------|------|
| `type` | str | `"result"` | 消息类型 |
| `subtype` | str | `"error_max_turns"` | 结果子类型（**关键判断字段**） |
| `is_error` | bool | `True` | 是否报错（**关键判断字段**） |
| `result` | str/缺失 | 可能有最后一条 assistant 消息，也可能缺失 | 结果文本 |
| `stop_reason` | str | `"tool_use"` | 最后一个 turn 的停止原因（**不可靠**，非终止原因） |
| `terminal_reason` | str | `"max_turns"` | **真正的终止原因** |
| `errors` | list[str] | `["Reached maximum number of turns (1)"]` | 错误消息数组 |
| `session_id` | str | 有效值 | 可用于 `--resume` 续跑 |
| `num_turns` | int | 等于 max_turns | turn 计数 |
| `duration_ms` | int | 有效值 | 总耗时 |
| `duration_api_ms` | int | 有效值 | API 调用耗时 |
| `total_cost_usd` | float | 有效值 | 成本 |
| `usage` | dict | 有效值 | Token 使用统计 |
| `modelUsage` | dict | 有效值 | 按模型统计 |
| `permission_denials` | list | `[]` | 权限拒绝记录 |
| `fast_mode_state` | str | `"off"` | 快速模式状态 |
| `uuid` | str | 有效值 | 唯一标识 |

**关键纠正**：`stop_reason` 是最后一个 turn 的原因（如 `"tool_use"`），而 **`terminal_reason`** 才是整体终止原因。

### 2.3 续跑 reality：为什么不能直接改成 `failed`

- `_trigger_continuation()` 只在 `snapshot.status in ("succeeded", "failed")` 时触发。
- 该 continuation 只是构造一段 `[Background Task Completed — ...]` 文本，再调用 `loop.process_direct(...)`。
- 这条链路**不会**重新调用 `claude_code` 工具，也**不会**消费 `cli_session_id` 去执行 `claude --resume`。
- 因此，若把 `max_turns` 直接映射为 `failed`，结果只会变成：
  - 用户先收到一个假的终局 `ERROR`
  - 主 Agent 再基于这段文本继续聊下去
  - 但 Claude 原会话并没有真正续跑

### 2.4 实证：数据库中的问题任务记录

DB 中 task_id=`b1924ebc5232` 的记录：

- status: `succeeded`（错误！）
- result_preview: `"Now I have a complete understanding of the file structure..."`（134963ms）
- 这是 Claude 在 max_turns 用尽前的最后输出，不是任务完成的标志
- full_result 只有 256 字符，而同类成功任务（228be6ea893e）有详细的修改报告

### 2.5 CLI 中间过程与交互场景

**中间过程输出**：`--output-format json` 只输出最终 result（1 行 JSON）。`--output-format stream-json --verbose` 可输出中间事件流：

| 事件 type | subtype | 说明 |
|-----------|---------|------|
| `system` | `init` | 初始化，含 cwd/session_id/tools/model |
| `system` | `hook_started/hook_response` | Hook 生命周期事件 |
| `assistant` | (空) | 模型输出，content 含 text 和 tool_use blocks |
| `user` | (空) | 工具执行结果（tool_result） |
| `result` | `success`/`error_max_turns`/... | 最终结果 |

**交互式输入场景**：`-p`（print mode）下 CLI **不会** hang 等待用户输入。权限由 `--permission-mode` 控制，不足时继续执行直到 max_turns。

**`terminal_reason` 完整值域**（已验证）：

| terminal_reason | subtype | is_error | 场景 |
|----------------|---------|----------|------|
| `completed` | `success` | `false` | 正常完成 |
| `max_turns` | `error_max_turns` | `true` | 回合用尽 |
| （待验证） | `error_max_budget_usd` | `true` | 预算用尽 |
| （待验证） | `error_during_execution` | `true` | 执行中出错 |

### 2.6 共享状态机约束：不能把 Claude 字段当成通用 executor 契约

- `BackgroundTaskStore.submit_coding_task()` 是通用基础设施，不只给 `claude_code` 使用，`codex` 也复用了同一条 `_run()` / `_on_complete()` / `_trigger_continuation()` 链。
- 因此，本任务不能在通用 `_run()` 里无条件假设所有 executor 都返回 Claude 风格字段（`is_error` / `terminal_reason` / `subtype`）。
- 最小安全改法应是：
  - 仅对 `task_type == "claude_code"` 启用本次分类逻辑，或
  - 先引入内部归一化 helper，再为其他 task_type 保持现状

### 2.7 佐证：同步路径的判断不能直接照搬到后台状态机

`_format_output`（`claude_code.py:369`）的同步路径使用：

```python
status = "ERROR" if is_error else subtype.upper() or "SUCCESS"
```

这适合同步文本输出，但**不适合**直接拿来定义后台状态机，因为 `BackgroundTaskStore` 已经有更细的 `interrupted` 语义。

### 2.8 影响范围

- 所有异步后台任务（mode=fast/standard/readonly）均受影响
- 同步模式（mode=sync）不受影响
- 若在通用 `bg_tasks.py` 中做了 Claude 特定判断且未加 task_type 保护，还会误伤 `codex` 等其他 executor

### 2.9 风险与约束

- 修复不应破坏正常完成的任务（`terminal_reason="completed"` + `is_error=false`）
- 修复不应把 `max_turns` 从“误报 SUCCESS”变成“误报 ERROR”
- 在没有真 resume 闭环前，`max_turns` 只能标成 `interrupted/resumable`，不能假装 `auto_continue` 已闭环
- Claude 特定终止字段不能被当成 BackgroundTaskStore 的通用契约

## 2.10 Next Actions

- 在 `bg_tasks.py` 中引入 task-type-aware 的结果分类
- 将 `max_turns` 收敛为 `interrupted`，并在 completion 文本里明确暴露 `terminal_reason` / `cli_session_id`
- 将“真 resume”单列 follow-up task，不在当前任务里继续借用 `auto_continue` 概念

## 3. Innovate (Options & Decision)

### Option A: 将 `max_turns` 直接映射为 `failed`

- 在 `_run()` 中只要看到 `is_error=True` 就标记 `failed`
- Pros: 改动最小
- Cons: 会把 false SUCCESS 变成 false ERROR；还会继续误用 `auto_continue`，让人误以为已经具备 resume 能力

### Option B: 将 `max_turns` 映射为 `interrupted/resumable`，当前任务只做状态止血

- `_execute_background` 继续返回完整 parsed dict
- `_run()` 仅在 `task_type == "claude_code"` 时检查 `subtype` / `terminal_reason` / `is_error`
- `max_turns` → `interrupted`
- 真执行错误 → `failed`
- 正常完成 → `succeeded`
- `interrupted` 不走通用 `auto_continue`
- Pros: 与当前 runtime reality 一致；最小化止血；不再假装已实现 resume
- Cons: 不能自动续跑 Claude 原会话；若要补齐需单独 follow-up

### Option C: 在本任务内同时补齐真 resume 闭环

- 在 `interrupted` 后显式消费 `cli_session_id`，重新调用 `claude_code(..., session_id=...)`
- Pros: 用户体验最完整
- Cons: 已超出“修误标 SUCCESS”的最小范围；会碰到 continuation、任务去重、resume budget、嵌套 task 等额外设计问题

### Decision

- Selected: **Option B**
- Why: 这是当前最简有效方案。先把错误状态语义收正，再单独设计 `cli_session_id -> --resume` 闭环，比把两个问题揉在一起更稳。

## 4. Plan (Contract)

### 4.1 File Changes

- `ava/agent/bg_tasks.py`:
  - 为后台 executor 结果新增内部分类 helper（按 `task_type` 分流）
  - `claude_code` 的 `max_turns` 收敛为 `interrupted`
  - `_resolve_result_text` / `_on_complete` / `_build_continuation_message` 支持 `INTERRUPTED`
  - `extra` 持久化 CLI 元字段，便于后续 resume / 排障
- `tests/agent/test_bg_tasks.py`:
  - 新增 `claude_code max_turns -> interrupted`
  - 新增 `interrupted` completion 文案和“不中 generic continuation”的断言
  - 新增非 Claude task 不受新分类逻辑影响的回归用例
- `ava/tools/claude_code.py`: 当前任务无需修改（已返回完整 parsed dict，并已上报 `session_id`）

### 4.2 Signatures

- 无新增公开签名
- 允许在 `bg_tasks.py` 内新增私有 helper（如 `_classify_background_result()`）

### 4.3 Implementation Checklist

- [ ] 1. 修改 `bg_tasks.py` `_run()` 成功分支：引入 task-type-aware 的结果分类
  - `task_type != "claude_code"`：保持现有“正常返回即 succeeded、抛异常即 failed”语义
  - `task_type == "claude_code"`：
    - `terminal_reason == "max_turns"` 或 `subtype == "error_max_turns"` → `status="interrupted"`
    - 其他 `is_error=True` → `status="failed"`
    - 其余情况 → `status="succeeded"`
- [ ] 2. 将 Claude CLI 返回的关键元字段持久化到 `extra` JSON 中：`is_error`、`subtype`、`terminal_reason`、`stop_reason`、`errors`、`cli_session_id`
- [ ] 3. 修正 completion 文案与结果解析
  - `succeeded -> SUCCESS`
  - `interrupted -> INTERRUPTED`
  - `failed/cancelled -> ERROR`
  - 当 `result` 与 `error_message` 同时存在时，输出中要同时保留中间产物和真实终止原因
  - `interrupted` 时附带 `Session: <cli_session_id>`，便于后续手动/自动 resume
- [ ] 4. `interrupted` 不触发通用 `_trigger_continuation()`
  - 在未实现真 resume 前，禁止继续借用当前 `auto_continue` 语义
- [ ] 5. 补测试到 `tests/agent/test_bg_tasks.py`
  - `claude_code max_turns -> interrupted`
  - `interrupted` completion 文案包含终止原因
  - `interrupted` 不进入 generic continuation
  - 非 Claude task 不受影响

### 4.4 Out-of-Scope 增强方向（备忘）

- **真 resume 闭环**：显式消费 `cli_session_id`，将 `interrupted/resumable` 任务重新接回 `claude --resume`；这应是单独 follow-up task，不应继续借用 generic `auto_continue`
- **stream-json 实时进度追踪**：切换 `_build_command` 为 `--output-format stream-json --verbose`，在 `_run_subprocess` 中逐行解析中间事件（`assistant` 的 tool_use、text blocks），实时更新 snapshot 的 `phase`、`last_tool_name`、`todo_summary`。Module Spec §2.5 "streaming 增强" 已规划此方向。
- **permission_denials 处理**：当前 `-p` 模式不会 hang 等待用户输入，但 `permission_denials` 数组可以透出权限问题，供用户诊断。

## 5. Execute Log

- 待 Plan Approved 后填充

## 6. Review Verdict

- 待 Execute 完成后填充

## 7. Plan-Execution Diff

- 待 Execute 完成后填充
