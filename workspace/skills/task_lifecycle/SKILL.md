# Skill: task_lifecycle

## Purpose

标准化定时任务的完成状态管理流程。确保 agent 在完成周期性任务后主动标记状态，避免重复执行。

## Two Systems

nanobot 有两套定时任务系统，状态管理方式不同：

### 1. Cron 任务（通过 cron tool 管理）

**检查 → 执行 → 标记** 三步流程：

```
# Step 1: 检查任务当前状态
cron(action="check_status", job_id="<id>")
# 输出示例:
#   - Daily report (id: abc123, cron)
#     cycle: 2026-02-28 [PENDING]
#     next_run: 2026-02-28 08:00

# Step 2: 执行任务（如果 cycle 是 PENDING）
# ... 做实际的工作 ...

# Step 3: 标记完成
cron(action="mark_done", job_id="<id>")
# 输出: Marked job 'Daily report' (id: abc123) as done for cycle 2026-02-28
```

如果 `check_status` 显示 `[DONE]`，跳过执行。系统也会在 job 触发时自动检查并跳过已完成的周期。

### 2. Heartbeat 任务（通过 HEARTBEAT.md + 技能独立状态文件管理）

**说明**：

- 已删除全局的 `heartbeat_state.json`，避免状态同步复杂度
- 每个心跳任务在自己的技能目录管理独立状态文件
- HEARTBEAT.md 的 Active/Completed 区域是权威状态

**示例：体重提醒任务**

```
# Step 1: 读取技能状态文件
read_file("skills/weight_reminder/state.json")
# 检查 lastReset 字段判断今天是否已重置

# Step 2: 执行任务（如果需要）
# ... 做实际的工作 ...

# Step 3: 更新技能状态文件
# 更新 lastReset, lastReminderDate 等字段
```

#### 技能状态文件格式（示例：weight_reminder/state.json）

```json
{
  "lastReset": "2026-03-01",
  "lastReminderDate": "2026-03-01"
}
```

字段说明（根据技能需求自定义）：

- `lastReset`: 最后一次重置的日期（YYYY-MM-DD）
- `lastReminderDate`: 最后一次提醒的日期（YYYY-MM-DD）
- 其他字段由技能自行定义

#### 状态同步

Heartbeat 任务完成后，需要：

1. 更新技能自己的状态文件（如 `state.json`）
2. 将 HEARTBEAT.md 中的 checkbox 移到 Completed 区域（保持 markdown 与状态一致）

## Best Practices

1. **先检查再执行**：任何周期性任务执行前，先检查是否本周期已完成
2. **执行后立即标记**：完成任务后第一时间标记状态，不要等到最后
3. **Cron 任务用 cron tool**：`check_status` → 执行 → `mark_done`
4. **Heartbeat 任务用技能状态文件**：每个技能管理自己的状态文件（如 `weight_reminder/state.json`）
5. **同时更新 HEARTBEAT.md**：heartbeat 任务完成后，将 checkbox 移到 Completed 区域（保持 markdown 与状态一致）

## Task ID Convention

- Cron 任务：使用 cron job 的 `id`（系统生成）
- Heartbeat 任务：使用短横线分隔的小写字母 slug（如 `weight_reminder`, `aiway_check`）
