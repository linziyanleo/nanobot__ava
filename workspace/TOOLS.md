# Available Tools

This document describes the tools available to nanobot.

## File Operations

### read_file

Read the contents of a file.

```
read_file(path: str) -> str
```

### write_file

Write content to a file (creates parent directories if needed).

```
write_file(path: str, content: str) -> str
```

### edit_file

Edit a file by replacing specific text.

```
edit_file(path: str, old_text: str, new_text: str) -> str
```

### list_dir

List contents of a directory.

```
list_dir(path: str) -> str
```

## Shell Execution

### exec

Execute a shell command and return output.

```
exec(command: str, working_dir: str = None) -> str
```

**Safety Notes:**

- Commands have a configurable timeout (default 60s)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters
- Optional `restrictToWorkspace` config to limit paths

## Web Access

### web_search

Search the web using Brave Search API.

```
web_search(query: str, count: int = 5) -> str
```

Returns search results with titles, URLs, and snippets. Requires `tools.web.search.apiKey` in config.

### web_fetch

Fetch and extract main content from a URL.

```
web_fetch(url: str, extractMode: str = "markdown", maxChars: int = 50000) -> str
```

**Notes:**

- Content is extracted using readability
- Supports markdown or plain text extraction
- Output is truncated at 50,000 characters by default

## Communication

### message

Send a message to the user (used internally).

```
message(content: str, channel: str = None, chat_id: str = None) -> str
```

## Background Tasks

### spawn

Spawn a subagent to handle a task in the background.

```
spawn(task: str, label: str = None) -> str
```

Use for complex or time-consuming tasks that can run independently. The subagent will complete the task and report back when done.

## Scheduled Reminders (Cron)

Use the `exec` tool to create scheduled reminders with `nanobot cron add`:

### Set a recurring reminder

```bash
# Every day at 9am
nanobot cron add --name "morning" --message "Good morning! ☀️" --cron "0 9 * * *"

# Every 2 hours
nanobot cron add --name "water" --message "Drink water! 💧" --every 7200
```

### Set a one-time reminder

```bash
# At a specific time (ISO format)
nanobot cron add --name "meeting" --message "Meeting starts now!" --at "2025-01-31T15:00:00"
```

### Manage reminders

```bash
nanobot cron list              # List all jobs
nanobot cron remove <job_id>   # Remove a job
```

## Heartbeat Task Management

The `HEARTBEAT.md` file in the workspace is checked every 30 minutes.
Use file operations to manage periodic tasks:

### Add a heartbeat task

```python
# Append a new task
edit_file(
    path="HEARTBEAT.md",
    old_text="## Example Tasks",
    new_text="- [ ] New periodic task here\n\n## Example Tasks"
)
```

### Remove a heartbeat task

```python
# Remove a specific task
edit_file(
    path="HEARTBEAT.md",
    old_text="- [ ] Task to remove\n",
    new_text=""
)
```

### Rewrite all tasks

```python
# Replace the entire file
write_file(
    path="HEARTBEAT.md",
    content="# Heartbeat Tasks\n\n- [ ] Task 1\n- [ ] Task 2\n"
)
```

---

## Categorized Memory

### memory

用于“按自然人聚合”的长期记忆（跨渠道共享）。**优先用 `memory` 工具**，除非你在做“整理/重构记忆文件”，否则不要直接改 `workspace/memory/` 里的文件。

```text
memory(action: str, content: str = None, person: str = None, scope: str = "person", display_name: str = None) -> str
```

#### 写入位置（你需要知道的最小集合）

- **Global（共享）**: `memory/MEMORY.md`, `memory/HISTORY.md`
- **Identity Map**: `memory/identity_map.yaml`（`id` 支持数组，同渠道可多账号）
- **Person（聚合）**: `memory/persons/<person>/MEMORY.md`, `memory/persons/<person>/HISTORY.md`
- **Source（渠道笔记）**: `memory/persons/<person>/sources/<channel>_<id>.md`

#### 创建/更新规约（最短可执行）

- **建立身份映射**（用户自报/你已确认身份）：调用 `map_identity`，把“当前会话的 channel+chat_id”挂到某个 `person` 上（会自动追加到 `id` 数组）。
- **记住长期事实**（稳定偏好/身份/项目背景）：调用 `remember`，`scope="person"`，内容用**短句/要点**，避免流水账。
- **记住渠道特定信息**（只在某群/某渠道有意义）：调用 `remember`，`scope="source"`。
- **召回/排错**：`recall`（看当前或指定 person 的记忆），`search_history`（按关键词搜历史）。

#### identity_map.yaml 示例

```yaml
persons:
  leo:
    display_name: "Leo / 方壶"
    ids:
      - channel: telegram
        id: ["12345678", "87654321"]
      - channel: cli
        id: ["direct"]
```

（更完整的结构说明见 `memory/CATEGORIZED_MEMORY_TEMPLATE.md`，不要把它整份复制进 prompt。）

---

## Adding Custom Tools

To add custom tools:

1. Create a class that extends `Tool` in `nanobot/agent/tools/`
2. Implement `name`, `description`, `parameters`, and `execute`
3. Register it in `AgentLoop._register_default_tools()`
