# Heartbeat Tasks

This file is checked every 30 minutes by the agent.
Add tasks below that you want the agent to work on periodically.

If this file has no tasks (only headers and comments), the agent will skip the heartbeat.

## Active Tasks

<!-- Add your periodic tasks below this line -->

### 体重提醒（每天）

**流程**:

1. 8:30 后执行 `skills/weight_reminder/check_reminder.py` 检查状态
2. 如果状态是 "active"，等待用户主动报体重（不主动提醒）
3. 用户报体重后，将此任务移到 Completed
4. 第二天 7:00 后执行 `skills/weight_reminder/reset_reminder.py` 重置为 Active

- [ ] 检查用户是否已报今日体重（8:30 后）

## Completed

<!-- Move completed tasks here or delete them -->

- [x] 检查用户是否已报今日体重（2026-02-28 已完成）
