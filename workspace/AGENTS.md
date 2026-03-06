# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Scheduled Reminders

Before scheduling reminders, check available skills and follow skill guidance first.
Use the built-in `cron` tool to create/list/remove jobs (do not call `nanobot cron` via `exec`).
Get USER_ID and CHANNEL from the current session (e.g., `8281248569` and `telegram` from `telegram:8281248569`).

**Do NOT just write reminders to MEMORY.md** — that won't trigger actual notifications.

## Heartbeat Tasks

`HEARTBEAT.md` is checked on the configured heartbeat interval. Use file tools to manage periodic tasks:

- **Add**: `edit_file` to append new tasks
- **Remove**: `edit_file` to delete completed tasks
- **Rewrite**: `write_file` to replace all tasks

When the user asks for a recurring/periodic task, update `HEARTBEAT.md` instead of creating a one-time cron reminder.

## Task Completion Tracking

Mark completion status to prevent re-execution. See `skills/task_lifecycle/SKILL.md` for full protocol.

- **Cron**: `cron(action="check_status")` before, `cron(action="mark_done")` after.
- **Heartbeat**: Read/update `heartbeat_state.json` with `completed_at`, `cycle`, `next_cycle`.

## Memory Governance

Memory files must be kept concise to avoid token waste.

### MEMORY.md Rules

- **Only store stable facts**: preferences, relationships, agreements, identity information
- **Prohibit content**: historical event details, timeline entries, technical environment memos, scheduled task lists
- **Line count limit**: keep under 80 lines
- If content does not meet the above rules, it should be moved to HISTORY.md or deleted
