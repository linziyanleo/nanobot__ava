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

Send a sticker from the configured sticker pack. Use to express emotions visually or add playful reactions.

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

- Only works on the Telegram channel, do NOT call this tool on other channels (console, feishu, discord, etc.)
- Sticker pack and emoji mappings are configured in `~/.nanobot/sticker.json`
- The tool reads pack data at startup and caches it; modify the config file to switch packs or update stickers
- When a sticker is sent, the agent suppresses the text reply for that turn (via `_sent_in_turn`)
- Choose stickers naturally based on conversation emotion

## Image Generation

### image_gen

Generate or edit images using AI image generation capabilities.

```
image_gen(prompt: str, reference_image: str = None) -> str
```

**Parameters:**

- `prompt` (str, required): Text prompt describing the image to generate, or edit instruction when reference_image is provided
- `reference_image` (str, optional): File path to a reference image for editing. When provided, the prompt is treated as an edit instruction.

**Examples:**

```
image_gen(prompt="画一只在太空中飘浮的猫咪，赛博朋克风格")
image_gen(prompt="把背景改成蓝色海洋", reference_image="/Users/me/.nanobot/media/generated/abc123_0.png")
```

**Notes:**

- Generated images are saved to `~/.nanobot/media/generated/` and returned as file paths
- Use the `message` tool with `media` parameter to send generated images to the user:

  ```
  message(content="这是为你生成的图片", media=["/Users/me/.nanobot/media/generated/abc123_0.png"])
  ```

- Supports both pure generation (text → image) and editing (image + text → image)
- All generation records (prompt, output paths, status) are logged for the Console media gallery

## Claude Code — 远程代码执行

### claude_code

调用 Claude Code CLI 执行代码任务。**默认异步执行**，任务在后台运行，完成后通知。

```
claude_code(prompt: str, project_path: str = None, mode: str = "standard", session_id: str = None) -> str
```

**Parameters:**

- `prompt` (str, required): 任务描述。应该清晰、具体，包含文件路径、预期行为、约束条件。
- `project_path` (str, optional): 目标项目目录的绝对路径。省略则使用默认项目路径。
- `mode` (str, optional): 执行模式
  - `fast`: **异步**，最多 5 轮，120s 超时。适合简单任务
  - `standard` (默认): **异步**，最多 15 轮，600s 超时。适合复杂任务
  - `readonly`: **异步**，只读分析，不修改文件
  - `sync`: **同步**，阻塞等待结果返回（向后兼容）
- `session_id` (str, optional): 恢复之前的 Claude Code 会话

**异步 vs 同步模式：**

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| `fast/standard/readonly` | 异步，立即返回 task_id，完成后通知 | 复杂任务、多文件修改、长时间执行 |
| `sync` | 同步，阻塞等待结果 | 需要立即获取结果、简单查询 |

**什么时候用 claude_code vs 直接改：**

| 场景 | 选择 | 原因 |
|------|------|------|
| 用户发的消息很简短（“改一下 xxx”、“加个 yyy 功能”） | `claude_code` | 你无法直接操作项目文件，让 Claude Code 执行 |
| 多文件修改、复杂功能开发 | `claude_code(mode="standard")` | Claude Code 有完整的文件读写能力 |
| 只看代码不改（“帮我看看 xxx 有没有问题”） | `claude_code(mode="readonly")` | 安全的只读分析 |
| 简单的一行修改或快速查看 | `claude_code(mode="fast")` | 快进快出 |
| 修改 workspace 下的 nanobot 配置文件 | 直接用 `edit_file` / `write_file` | 这些是你自己的 workspace 文件 |
| 用户只是聊天、问问题、不涉及代码变更 | 不用 `claude_code` | 直接回答 |

**提示词最佳实践：**

- 包含具体文件路径：`在 src/api/auth.py 中...`
- 明确预期行为：`添加 JWT token 过期刷新逻辑，过期时自动刷新`
- 设定约束条件：`不要修改现有 API 签名`、`保持向后兼容`
- 复杂任务分步：先分析再实现，或拆分为多个小任务

**示例:**

```
# 异步执行（默认）- 任务在后台运行，完成后通知
claude_code(prompt="在 src/api/auth.py 中添加 JWT token 过期刷新逻辑", mode="standard")
claude_code(prompt="分析 nanobot/agent/loop.py 的架构设计，给出改进建议", mode="readonly")
claude_code(prompt="修复 login 页面的样式错位问题", project_path="/Users/me/myproject", mode="fast")

# 同步执行 - 阻塞等待结果
claude_code(prompt="查看 src/config.py 的内容", mode="sync")

# 恢复会话
claude_code(prompt="继续上次的任务，完成剩余的测试用例", session_id="a8e7f343-xxxx")
```

**Notes:**

- 异步模式返回任务启动确认（包含 task_id），完成后通过消息总线通知
- 同步模式返回结构化结果：状态（SUCCESS/ERROR）、Turns、Duration、Cost、结果文本
- Token 消耗自动记录到 token_stats（provider=claude-code-cli, model_role=claude_code）
- 需要 npx 在 PATH 中（Node.js 环境）
- 配置项在 `~/.nanobot/config.json` 的 `tools.claudeCode` 段

---

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
