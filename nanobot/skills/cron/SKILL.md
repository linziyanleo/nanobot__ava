---
name: cron
description: Schedule reminders and recurring tasks.
---

# Cron

Use the `cron` tool to schedule reminders or recurring tasks.

## Three Modes

1. **Reminder** - message is sent directly to user
2. **Task** - message is a task description, agent executes and sends result
3. **One-time** - runs once at a specific time, then auto-deletes

## Examples

Fixed reminder:
```
cron(action="add", message="Time to take a break!", every_seconds=1200)
```

Dynamic task (agent executes each time):
```
cron(action="add", message="Check HKUDS/nanobot GitHub stars and report", every_seconds=600)
```

One-time scheduled task (compute ISO datetime from current time):
```
cron(action="add", message="Remind me about the meeting", at="<ISO datetime>")
```

Timezone-aware cron:
```
cron(action="add", message="Morning standup", cron_expr="0 9 * * 1-5", tz="America/Vancouver")
```

Check status of all jobs (shows completion state):
```
cron(action="check_status")
```

Check a specific job:
```
cron(action="check_status", job_id="abc123")
```

Mark a job as done for the current cycle:
```
cron(action="mark_done", job_id="abc123")
```

List/remove:
```
cron(action="list")
cron(action="remove", job_id="abc123")
```

## Time Expressions

| User says | Parameters |
|-----------|------------|
| every 20 minutes | every_seconds: 1200 |
| every hour | every_seconds: 3600 |
| every day at 8am | cron_expr: "0 8 * * *" |
| weekdays at 5pm | cron_expr: "0 17 * * 1-5" |
| 9am Vancouver time daily | cron_expr: "0 9 * * *", tz: "America/Vancouver" |
| at a specific time | at: ISO datetime string (compute from current time) |

## Timezone

Use `tz` with `cron_expr` to schedule in a specific IANA timezone. Without `tz`, the server's local timezone is used.

## Task Completion Tracking

Recurring jobs support completion tracking per cycle (e.g. per day). After executing a task's goal, call `mark_done` so the system knows not to re-execute:

```
cron(action="check_status", job_id="abc123")  # check if already done
# ... do the work ...
cron(action="mark_done", job_id="abc123")     # mark this cycle as done
```

The system auto-computes the cycle ID based on the schedule type (daily cron → date, hourly cron → date-hour). If a job fires again within the same cycle, it will be automatically skipped.
