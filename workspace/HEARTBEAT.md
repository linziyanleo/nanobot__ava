# Heartbeat Tasks

This file is checked every 30 minutes by the agent.
Add tasks below that you want the agent to work on periodically.

If this file has no tasks (only headers and comments), the agent will skip the heartbeat.

## 执行规则

⚠️ **重要**：心跳检查之后，除非在心跳任务中明确要求，否则**不发送消息**，只更新状态文件。

## Active Tasks

<!-- Add your periodic tasks below this line -->

### 体重提醒（每天）

**流程**:

1. 8:30 后执行 `skills/weight_reminder/check_reminder.py` 检查状态
2. 如果状态是 "active" 或 "pending"，等待用户主动报体重（不主动提醒）
3. 用户报体重后，将此任务移到 Completed
4. 第二天 7:00 后执行 `skills/weight_reminder/reset_reminder.py` 重置为 Active

**心跳检查逻辑**:

- 当前时间 < 7:00 → 跳过检查
- 7:00 <= 当前时间 < 8:30 → 执行 reset_reminder.py（如需重置）
- 当前时间 >= 8:30 → 执行 check_reminder.py 检查状态

## Completed

<!-- Move completed tasks here or delete them -->

- [x] 体重提醒任务 - 今日体重已记录（2026-02-28 已完成）
