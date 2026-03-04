# Skill: weight_reminder

## Purpose

追踪主人的每日体重记录状态。逻辑极简：早晨提醒由 `早晨日常提醒` cron 任务负责，本 skill 只管状态。

## 流程

1. **早上 8:30** — `早晨日常提醒` cron 发送天气 + 体重提醒
2. **主人报体重** — Ava 更新 `state.json` + 写入 person memory
3. 完事。没了。

## state.json

```json
{
  "date": "2026-03-04",
  "recorded": true
}
```

- `date`: 当前日期
- `recorded`: 今天是否已记录体重

每天第一次交互时，如果 `date` 不是今天，自动重置 `recorded` 为 `false`。

## 体重历史

体重数据记录在 Leo 的 person memory 中，格式：
```
[YYYY-MM-DD] 体重记录：XX.Xkg（较上次 XX.Xkg 变化 ±X.Xkg）
```

## 注意

- 不再有 `check_reminder.py` / `reset_reminder.py`
- 不再操作 HEARTBEAT.md
- 不再需要 `weight_reset` / `weight_check` cron 任务
