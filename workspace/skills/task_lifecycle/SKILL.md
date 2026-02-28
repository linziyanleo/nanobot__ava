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

### 2. Heartbeat 任务（通过 HEARTBEAT.md + heartbeat_state.json 管理）

**读状态 → 执行 → 写状态** 三步流程：

```
# Step 1: 读取 heartbeat_state.json
read_file("heartbeat_state.json")
# 检查对应任务的 cycle 是否是今天

# Step 2: 执行任务（如果未完成）
# ... 做实际的工作 ...

# Step 3: 更新 heartbeat_state.json
# 读取现有内容，更新对应任务的状态，写回文件
```

#### heartbeat_state.json 格式

```json
{
  "version": 1,
  "tasks": {
    "task_id": {
      "completed_at": "2026-02-28T09:30:00+08:00",
      "cycle": "2026-02-28",
      "next_cycle": "2026-03-01"
    }
  }
}
```

字段说明：
- `completed_at`: 本轮完成的 ISO 时间戳
- `cycle`: 当前完成的周期标识（日周期用 `YYYY-MM-DD`，小时周期用 `YYYY-MM-DDTHH:00`）
- `next_cycle`: 下一个周期标识（用于判断何时可以重新执行）

#### 完成任务后更新示例

```python
# 假设完成了 weight_reminder 任务
import json
from datetime import datetime, timedelta

state = json.loads(read_file("heartbeat_state.json"))
today = datetime.now().strftime("%Y-%m-%d")
tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

state["tasks"]["weight_reminder"] = {
    "completed_at": datetime.now().isoformat(),
    "cycle": today,
    "next_cycle": tomorrow
}
write_file("heartbeat_state.json", json.dumps(state, indent=2, ensure_ascii=False))
```

## Best Practices

1. **先检查再执行**：任何周期性任务执行前，先检查是否本周期已完成
2. **执行后立即标记**：完成任务后第一时间标记状态，不要等到最后
3. **Cron 任务用 cron tool**：`check_status` → 执行 → `mark_done`
4. **Heartbeat 任务用文件**：读 `heartbeat_state.json` → 执行 → 写 `heartbeat_state.json`
5. **同时更新 HEARTBEAT.md**：heartbeat 任务完成后，也要将 checkbox 移到 Completed 区域（保持 markdown 与 json 状态一致）

## Task ID Convention

- Cron 任务：使用 cron job 的 `id`（系统生成）
- Heartbeat 任务：使用短横线分隔的小写字母 slug（如 `weight_reminder`, `aiway_check`）
