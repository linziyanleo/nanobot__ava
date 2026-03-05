---
name: qodercli
version: 1.0.0
description: Use Qoder CLI for terminal-based AI-assisted development. Use when running qodercli commands, managing MCP servers, configuring permissions, creating subagents, working with AGENTS.md memory files, or automating tasks with worktree jobs.
---

# Qoder CLI

Terminal-based AI assistant for software development. Provides interactive chat, code analysis, and MCP integration.

## Installation

```bash
# cURL
curl -fsSL https://qoder.com/install | bash

# Homebrew (macOS, Linux)
brew install qoderai/qoder/qodercli --cask

# NPM
npm install -g @qoder-ai/qodercli
```

Verify: `qodercli --version`

## Authentication

**Browser login (recommended):**
```bash
qodercli
# In TUI, enter:
/login
```

**Environment variable (CI/CD):**
```bash
export QODER_PERSONAL_ACCESS_TOKEN="your_token_here"
```

Get token at: https://qoder.com/account/integrations

## Core Modes

### TUI Mode (Interactive)

```bash
qodercli                    # Start interactive session
qodercli -w /path/to/proj   # Specify workspace
qodercli -c                 # Continue last session
qodercli -r <session_id>    # Resume specific session
```

### Print Mode (Non-Interactive)

```bash
qodercli -p "Your prompt"              # Single prompt, text output
qodercli -p "prompt" -f json           # JSON output
qodercli -p "prompt" -f stream-json    # Streaming JSON (recommended)
qodercli -p "prompt" --max-turns 10    # Limit iterations
qodercli -p "prompt" --yolo            # Skip permission checks
```

**推荐使用 `stream-json` 格式**：可观察完整的工具调用过程（Shell 执行、文件读写等），便于调试和监控。

### Output Format Details

| Format | Description | Use Case |
|--------|-------------|----------|
| `text` | 仅输出最终文本结果 | 简单查询、管道处理 |
| `json` | 完整 JSON 结构 | API 集成 |
| `stream-json` | 流式 JSON 事件序列 | **调试推荐**，观察完整执行过程 |

**stream-json 事件类型：**

```jsonl
{"type":"system","subtype":"init",...}       # 初始化信息
{"type":"assistant","message":{...}}         # AI 回复/工具调用
{"type":"user","message":{...}}              # 工具执行结果
{"type":"result","done":true,...}            # 最终结果
```

**示例：观察工具调用过程**

```bash
# 可以看到 Shell 命令的实际执行和输出
qodercli -p "列出当前目录的文件" -f stream-json --yolo

# 管道处理流式输出
qodercli -p "分析这段代码" -f stream-json | jq 'select(.type=="assistant")'
```

## Input Modes (TUI)

| Prefix | Mode | Description |
|--------|------|-------------|
| `>` | Dialog | Default chat mode |
| `!` | Bash | Execute shell commands |
| `/` | Slash | Run built-in commands |
| `#` | Memory | Edit AGENTS.md |
| `\ Enter` | Multiline | Multi-line input |

## Slash Commands

| Command | Description |
|---------|-------------|
| `/login` | Sign in to Qoder |
| `/logout` | Sign out |
| `/init` | Generate AGENTS.md memory file |
| `/memory` | Edit memory files |
| `/review` | Review local git changes |
| `/quest` | Spec-driven delegated task |
| `/agents` | Manage subagents |
| `/resume` | List and resume sessions |
| `/clear` | Clear context history |
| `/compact` | Summarize context |
| `/config` | Show configuration |
| `/status` | Show CLI status |
| `/usage` | Show credit usage |
| `/bashes` | List background jobs |
| `/vim` | Open external editor |
| `/quit` | Exit TUI |

## Model Selection

```bash
qodercli --model auto         # Auto select (default)
qodercli --model efficient    # Cost-effective
qodercli --model lite         # Lightweight
qodercli --model performance  # High performance
qodercli --model ultimate     # Maximum capability
```

## MCP Integration

```bash
# Add MCP server
qodercli mcp add playwright -- npx -y @playwright/mcp@latest
qodercli mcp add context7 -- npx -y @upstash/context7-mcp@latest

# List servers
qodercli mcp list

# Remove server
qodercli mcp remove playwright
```

Server types: stdio, sse, streamable-http

Config files:
- User: `~/.qoder.json`
- Project: `${project}/.mcp.json`

## Permissions

Config files (precedence low to high):
- `~/.qoder/settings.json`
- `${project}/.qoder/settings.json`
- `${project}/.qoder/settings.local.json`

```json
{
  "permissions": {
    "allow": [
      "Read(/path/to/project/**)",
      "Edit(/path/to/project/**)"
    ],
    "ask": [
      "Read(!/path/to/project/**)"
    ],
    "deny": []
  }
}
```

Permission types:
- `Read(pattern)` - File reading (Grep, Glob, LS)
- `Edit(pattern)` - File editing
- `WebFetch(domain:example.com)` - Network fetch
- `Bash(command)` - Shell commands

## Worktree Jobs

Run concurrent tasks in isolated git worktrees:

```bash
# Create worktree job
qodercli --worktree "Your task description"
qodercli --worktree "task" --branch feature-x    # Specific branch
qodercli --worktree "task" -p                    # Non-interactive

# List jobs
qodercli jobs --worktree

# Remove job
qodercli rm <jobId>
```

## Memory (AGENTS.md)

Auto-loaded context for development guidance.

Locations:
- User: `~/.qoder/AGENTS.md`
- Project: `${project}/AGENTS.md`

```bash
# Generate via TUI
/init

# Edit via TUI
/memory
# or type # to enter memory mode
```

## Subagents

Specialized AI agents for specific tasks.

### Built-in Subagents

| Name | Purpose |
|------|---------|
| `code-reviewer` | Code review |
| `design-agent` | Software design |
| `general-purpose` | General tasks |
| `task-executor` | Execute designs |

### Create Subagent

Location:
- User: `~/.qoder/agents/<name>.md`
- Project: `${project}/.qoder/agents/<name>.md`

```markdown
---
name: api-reviewer
description: Review API designs for RESTful compliance
tools: Read,Grep,Glob
---

You are an API design reviewer...
```

### Use Subagent

```bash
# Explicit
Use the code-reviewer subagent to review this code

# Implicit (auto-selected)
Review this code for security issues

# Chained
First use design-agent for design, then code-reviewer for review
```

## Skills

Task-specific guides auto-loaded by context.

Location:
- User: `~/.qoder/skills/<name>/SKILL.md`
- Project: `.qoder/skills/<name>/SKILL.md`

```markdown
---
name: log-analyzer
description: Analyze log files for errors and patterns
---

# Log Analyzer
...
```

Manage via `/skills` command.

## Commands

Custom slash commands as markdown files.

Location:
- User: `~/.qoder/commands/<name>.md`
- Project: `.qoder/commands/<name>.md`

```markdown
---
name: git-commit
description: Generate commit message from changes
---

Analyze git changes and generate commit message...
```

Execute: `/git-commit`

## ACP (Agent Client Protocol)

Run as ACP server for IDE integration:

```bash
qodercli --acp
```

Zed IDE config (`~/.config/zed/settings.json`):
```json
{
  "agent_servers": {
    "Qoder CLI": {
      "type": "custom",
      "command": "qodercli",
      "args": ["--acp"]
    }
  }
}
```

## GitHub Actions

Use Qoder Action for automated PR reviews:

```yaml
- name: Run Qoder Code Review
  uses: QoderAI/qoder-action@v0
  with:
    qoder_personal_access_token: ${{ secrets.QODER_PERSONAL_ACCESS_TOKEN }}
    prompt: |
      /review-pr
      REPO:${{ github.repository }} PR_NUMBER:${{ github.event.pull_request.number }}
```

Setup: Run `/setup-github` in TUI.

## Workflows

### Code Review

```bash
qodercli -p '/review'
# or in TUI
/review Focus on security vulnerabilities
```

### Generate Commit Message

```bash
qodercli
# Then:
Review staged changes and generate commit message
```

### Debug Analysis

```bash
qodercli -p 'Analyze this error and suggest fix: [error message]'
```

### Batch Processing (CI)

```bash
export QODER_PERSONAL_ACCESS_TOKEN=$TOKEN
# 推荐 stream-json 便于观察执行过程
qodercli -p 'Run security audit' -f stream-json --yolo
```

## CLI Flags Reference

| Flag | Description |
|------|-------------|
| `-p, --print` | Non-interactive mode |
| `-f, --output-format` | Output: text, json, **stream-json (推荐)** |
| `-w, --workspace` | Working directory |
| `-c, --continue` | Continue last session |
| `-r, --resume` | Resume specific session |
| `--model` | Model level |
| `--max-turns` | Max agent iterations |
| `--yolo` | Skip permissions |
| `--allowed-tools` | Whitelist tools |
| `--disallowed-tools` | Blacklist tools |
| `--attachment` | Attach files |
| `--worktree` | Git worktree job |
| `--branch` | Branch for worktree |
| `--acp` | ACP server mode |

## Update

```bash
# Auto-update (default enabled)
qodercli update

# Manual
curl -fsSL https://qoder.com/install | bash -s -- --force
# or
brew update && brew upgrade
# or
npm install -g @qoder-ai/qodercli
```

Disable auto-update in `~/.qoder.json`:
```json
{ "autoUpdates": false }
```
