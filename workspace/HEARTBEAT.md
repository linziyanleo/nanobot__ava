# Heartbeat Tasks

This file is checked every 30 minutes by the agent.
Add tasks below that you want the agent to work on periodically.

If this file has no tasks (only headers and comments), the agent will skip the heartbeat.

## Active Tasks

### 每日天气与体重提醒 (08:30)

- [ ] 检查是否到早上 8:30 左右，如果是则：
  - 获取杭州天气：`curl -s "wttr.in/Hangzhou?format=%l:+%c+%t+%h+%w"`
  - 提供穿衣建议
  - 提醒 Leo 称体重并发送结果
  - Channel: telegram, Chat ID: -5172087440

### 体重记录追踪

- [ ] 当 Leo 发送体重数据时，记录到 `memory/persons/leo/weight_tracker.md`

## Completed

<!-- Move completed tasks here or delete them -->