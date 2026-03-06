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

- Commands have a configurable timeout (default 300s)
  - Configure in `~/.nanobot/config.json`: `"tools": {"exec": {"timeout": 300}}`
  - Increase timeout for complex tasks (e.g., qodercli调研、网络爬虫等)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters
- `restrictToWorkspace` config can limit file access to the workspace

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

## Vision

### vision

Analyze an image from a URL or local file path (describe, OCR, answer questions).

```
vision(url: str, prompt: str = "描述这张图片的内容。") -> str
```

**Notes:**

- Accepts both remote URLs (`https://...`) and local file paths
- Local files are automatically base64-encoded for the API
- Uses the main conversation model (must support vision/multimodal)
- `prompt` controls the analysis: use `"请仅输出图像中的文本内容。"` for OCR, or ask specific questions about the image
- Returns the model's text response describing/analyzing the image

## Sticker

### send_sticker

Send a Telegram sticker from the configured sticker pack. Use to express emotions visually or add playful reactions.

```
send_sticker(sticker_id: int, chat_id: str = None) -> str
```

**Parameters:**

- `sticker_id` (int, required): Sticker number from the pack. Available IDs and their meanings are loaded from config.
- `chat_id` (str, optional): Telegram chat ID. If omitted, uses the current chat context automatically.

**Examples:**

```
send_sticker(sticker_id=4)                          # 发送表情到当前聊天
send_sticker(sticker_id=14, chat_id="12345678")     # 发送到指定聊天
```

**Notes:**

- Only works on the Telegram channel
- Sticker pack and emoji mappings are configured in `~/.nanobot/sticker.json`
- The tool reads pack data at startup and caches it; modify the config file to switch packs or update stickers
- When a sticker is sent, the agent suppresses the text reply for that turn (via `_sent_in_turn`)
- Choose stickers naturally based on conversation emotion; works best as a standalone reaction at the end of a reply

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

## cron — Scheduled Reminders

- Please refer to cron skill for usage.

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

See memory skill (loaded via skills directory). Prefer using `memory` tool to operate memory, do not directly edit files in `workspace/memory/`.

---

## Adding Custom Tools

To add custom tools:

1. Create a class that extends `Tool` in `nanobot/agent/tools/`
2. Implement `name`, `description`, `parameters`, and `execute`
3. Register it in `AgentLoop._register_default_tools()`
