# Skill: weight_reminder

## Purpose

管理体重提醒的状态检查和重置逻辑。通过 cron 定时任务管理，每天早上 7:00 重置状态，8:30 检查状态。

## How to Use

### 检查并更新体重提醒状态

```bash
cd /Users/leolin/Desktop/Work/nanobot__ava/workspace/skills/weight_reminder
python check_reminder.py
```

### 重置体重提醒状态

```bash
cd /Users/leolin/Desktop/Work/nanobot__ava/workspace/skills/weight_reminder
python reset_reminder.py
```

## Logic

### check_reminder.py

**执行时机**: 每天 8:30 (cron 任务 `weight_check`)

**逻辑流程**:
1. 读取 `state.json` 文件
2. 检查当前时间是否 >= 8:30
3. 检查 `lastReminderDate` 是否是今天
4. 如果今天已报体重：
   - 输出 "今日已完成，等待明日重置"
   - 返回状态码 0（正常）
5. 如果今天还没报体重：
   - 输出 "待提醒状态，等待用户报体重"
   - 返回状态码 0（正常）

### reset_reminder.py

**执行时机**: 每天 7:00 (cron 任务 `weight_reset`)

**逻辑流程**:
1. 读取 `state.json` 文件
2. 检查当前日期是否是新的日期（相比上次重置）
3. 检查当前时间是否 >= 7:00
4. 如果是新的一天且时间 >= 7:00：
   - 更新 `state.json` 中的 `lastReset` 为今天
   - 输出 "已重置为待提醒状态"
5. 如果今天已经重置过：
   - 输出 "今日已重置，跳过"
   - 返回状态码 0（正常）

## State Management

### 状态文件

**技能自己的状态文件**：`skills/weight_reminder/state.json`

- ✅ 每个体重提醒任务管理自己的状态文件
- ✅ `state.json` 是权威状态

### state.json 格式

```json
{
  "lastReset": "2026-03-02",
  "lastReminderDate": "2026-03-01"
}
```

字段说明：
- `lastReset`: 最后一次重置的日期（YYYY-MM-DD）
- `lastReminderDate`: 最后一次提醒（用户报体重）的日期（YYYY-MM-DD）

### 状态同步流程

**重置时**（reset_reminder.py）：
1. 更新 state.json 的 `lastReset` 为今天

**用户报体重后**：
1. 更新 state.json 的 `lastReminderDate` 为今天

**检查时**（check_reminder.py）：
1. 读取 state.json 判断今天是否已报体重

## Cron 任务配置

### 已配置的 cron 任务

| 任务名称 | Cron 表达式 | 执行时间 | 说明 |
|---------|------------|---------|------|
| `weight_reset` | `0 7 * * *` | 每天 7:00 | 重置体重提醒状态 |
| `weight_check` | `30 8 * * *` | 每天 8:30 | 检查体重提醒状态 |

### 添加 cron 任务

```bash
# 重置任务（每天 7:00）
nanobot cron add --name "weight_reset" --message "重置体重提醒状态" --cron "0 7 * * *"

# 检查任务（每天 8:30）
nanobot cron add --name "weight_check" --message "检查体重提醒状态" --cron "30 8 * * *"
```

## Files

- `check_reminder.py` - 检查提醒状态
- `reset_reminder.py` - 重置提醒状态
- `state.json` - 存储上次重置的时间戳（避免重复重置）

## Notes

- 不主动发送提醒消息（Leo 不喜欢频繁汇报）
- 只在用户主动询问时报告状态
- 状态变更记录到 HISTORY.md
- **已迁移到 cron 管理**（2026-03-02）
