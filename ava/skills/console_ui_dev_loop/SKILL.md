---
name: console_ui_dev_loop
description: Console-UI 前端开发-回归闭环。先生成 testing_task 和 master_checklist，再用 claude_code(sync) 实现，随后基于 page_agent 做 deterministic-first 回归，并在最终放行前执行完整 checklist。当用户说“修这个 console-ui 页面并自己回归”“做完后继续测直到通过”时触发。
metadata: {"nanobot":{"emoji":"🔁"}}
---

# Console UI Dev Loop

这是当前仓库里处理 `console-ui` 前端开发任务的唯一 user-facing 闭环 skill。

- 不要把它当成通用前端测试框架
- 不要把 `page_agent_test` 或 `console_ui_regression` 当并列主入口
- 默认目标是：`需求 -> testing_task -> coding -> regression -> retry -> final pass`

## 先读

- `references/testing-task.md`
- `references/loop-contract.md`
- 如需决定测试范围：`references/page-selection.md`
- 如需决定断言方式：`references/verifier-policy.md`

## 默认约束

- v1 默认 `coding_tool=claude_code`
- 调用方式固定为 `claude_code(mode="sync")`
- `codex` 不进入 v1 主路径；只保留为后续 TODO
- `page_agent` 在本 skill 内统一使用 `response_format="json"`
- `vision` 只用于 `assertion_mode=visual|hybrid`
- 默认 `rerun_policy=full_before_pass`

## 执行流程

### 1. Round 0：生成测试任务

先压缩需求意图，再生成 `testing_task`：

- 提炼 `target_outcomes`
- 提炼 `primary_risks`
- 标明 `excluded_scope`
- 生成 `master_checklist`
- 为每个 checkpoint 分配稳定 `check_id`

如果用户已经给了 `explicit_pages` 或明确验收点，优先纳入 checklist；不要重新发明目标。

### 2. Coding Round

使用 `claude_code(mode="sync")` 执行实现或修复。

给 coder 的输入至少包含：

- `goal`
- `changed_files`
- 当前 `failed_checks`
- 失败证据与 `failure_taxonomy`
- 只允许修改的目录范围

### 3. Regression Round

按 `references/page-selection.md` 选择范围。

- 中间轮次默认跑 `impacted_subset + baseline_smoke`
- 准备宣告 `PASS` 前必须跑 `full_checklist`

每个 checkpoint 都按 `references/verifier-policy.md` 执行：

- 先用 `page_agent` 的 URL / Page State / DOM 事实判断
- 只有视觉问题才升级到 `screenshot + vision`

### 4. Checklist Reverse Sync

执行中允许更新 checklist，但必须带理由：

- 新增 checkpoint：`checklist_delta.added`
- 废弃 checkpoint：`checklist_delta.deprecated`
- 未变化项：`checklist_delta.unchanged`

不要重命名既有 `check_id`。

### 5. 输出

每轮必须返回：

- `checklist_snapshot`
- `completed_checks`
- `pending_checks`
- `failed_checks`
- `deprecated_checks`
- `regression_report`
- `verdict`

只有执行过 `full_checklist` 的轮次，才允许返回最终 `verdict=pass`。

## 禁止事项

- 不要把 `vision` 当成默认主判据
- 不要每轮都默认跑完整 checklist，除非用户显式要求 `full_each_round`
- 不要依赖 `/task` 作为 loop 子步骤
- 不要把 console 的 WS 推送事件当成普通 `page_agent` tool 返回
- 不要把这个 skill 扩展成“任意项目通用前端闭环”

## 失败升级

遇到以下情况直接 `escalate`：

- 同一 `check_id + failure_taxonomy` 连续两轮失败
- 登录态 / 权限要求无法自动满足
- 问题属于 tooling/runtime，而不是当前页面实现

## 结果格式提醒

结果不是自由发挥的文字总结。优先输出结构化 round report，再补简短中文结论。
