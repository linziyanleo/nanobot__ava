---
name: claude-code-bridge
description: "通过 Claude Code CLI 远程执行代码修改、功能添加和调试任务。当用户想要修改代码、添加功能、修复 bug、调试问题时使用此 skill。触发词包括：用 Claude Code 做、帮我改代码、远程编码、claude code、cc 执行、代码修改、添加功能、修 bug、调试。即使用户只是简单说'改一下 xxx'或'加个 yyy 功能'，只要涉及代码变更且不是当前对话就能完成的，都应该触发此 skill。"
metadata: {"nanobot":{"emoji":"🔧","requires":{"bins":["npx"]}}}
---

# Claude Code Bridge

通过 Claude Code CLI 远程执行代码任务。nanobot 负责理解意图和报告结果，Claude Code 负责真正的代码分析、规划和修改。

## 快速使用

用户说"帮我给 auth 模块加 JWT 刷新 token"，你应该：

1. 确认目标项目路径
2. 构建提示词
3. 调用 Claude Code 执行
4. 解析结果并报告

## 工作流

### 阶段 1: 意图理解（你来做）

从用户消息中提取：
- **目标项目**: 用户指定的路径，或从配置文件中读取默认项目
- **任务描述**: 用户想做什么
- **约束条件**: 不要改什么、有什么特殊要求

读取配置获取默认项目路径：
```bash
exec("cat ~/.nanobot/workspace/claude-code-bridge-config.json")
```

如果用户未指定项目且配置中没有默认项目，**必须追问**。

### 阶段 2: 提示词构建（你来做）

先读取提示词模板：
```bash
exec("cat {skill_path}/references/prompt-templates.md")
```

根据任务选择合适模板，填充变量，生成最终提示词。

提示词应指导 Claude Code：
- 理解任务目标
- 分析相关代码
- 规划修改方案
- 执行修改
- 输出结构化的修改摘要

### 阶段 3: 执行（调用 Claude Code）

根据任务复杂度选择执行模式：

#### 快速模式（简单任务）

适用于：单文件修改、样式调整、小 bug 修复、配置变更。

将提示词写入临时文件，然后同步执行：
```bash
exec("cat > /tmp/cc-prompt.txt << 'PROMPT_EOF'\n{prompt}\nPROMPT_EOF")
exec("cd {project_path} && npx @anthropic-ai/claude-code -p \"$(cat /tmp/cc-prompt.txt)\" --output-format json --max-turns 5 --model claude-sonnet-4-20250514 --allowedTools 'Read,Edit,Bash,Glob,Grep' 2>/dev/null | tail -1")
```

#### 标准模式（复杂任务）

适用于：多文件修改、新功能开发、架构调整、需要深度分析的任务。

将提示词写入文件，然后后台执行：
```bash
exec("cat > /tmp/cc-prompt-{task_id}.txt << 'PROMPT_EOF'\n{prompt}\nPROMPT_EOF")
exec("bash {skill_path}/scripts/run_claude_code.sh {task_id} {project_path} /tmp/cc-prompt-{task_id}.txt 15 'Read,Edit,Bash,Glob,Grep' claude-sonnet-4-20250514")
```

然后每隔 10-15 秒轮询一次状态：
```bash
exec("cat /tmp/claude-code-{task_id}.status")
```

等状态变为 `done` 后读取结果：
```bash
exec("cat /tmp/claude-code-{task_id}.json")
```

如果等待超过 5 分钟，告知用户任务仍在执行，让用户决定是否继续等待。

#### task_id 生成

使用当前时间戳作为 task_id：
```bash
exec("date +%Y%m%d%H%M%S")
```

### 阶段 4: 结果解析（你来做）

从 Claude Code 的 JSON 输出中提取关键信息：

```json
{
  "result": "...(Claude Code 的文本输出)...",
  "session_id": "...",
  "usage": {
    "input_tokens": 12345,
    "output_tokens": 6789
  }
}
```

向用户报告：
1. **修改摘要**: 从 `result` 字段提取修改了哪些文件、做了什么
2. **Token 消耗**: 从 `usage` 字段计算（input + output tokens）
3. **Session ID**: 记下来，后续可用 --resume 继续

格式化为简洁的 Telegram 消息，避免过长。如果 result 超过 2000 字符，做摘要。

### 阶段 5: 跟进（如果用户要求修改）

如果用户对结果不满意或要求继续：
```bash
exec("cd {project_path} && npx @anthropic-ai/claude-code -p \"{follow_up_prompt}\" --resume {session_id} --output-format json --max-turns 10 --model claude-sonnet-4-20250514 --allowedTools 'Read,Edit,Bash,Glob,Grep' 2>/dev/null | tail -1")
```

## 项目管理

### 设置默认项目

当用户说"设置项目为 /path/to/project"或"切换项目到 xxx"时：

```bash
exec("cat ~/.nanobot/workspace/claude-code-bridge-config.json")
```

然后用 `edit_file` 更新 `default_project` 字段。

### 添加项目别名

当用户说"添加项目 myapp 路径 /path/to/myapp"时，更新 `projects` 对象。

用户可以用别名指定项目："用 myapp 项目，帮我..."

### 查看已配置项目

```bash
exec("cat ~/.nanobot/workspace/claude-code-bridge-config.json | python3 -c \"import sys,json; c=json.load(sys.stdin); print('默认:', c.get('default_project','未设置')); [print(f'  {k}: {v}') for k,v in c.get('projects',{}).items()]\"")
```

## 执行模式选择指南

| 特征 | 快速模式 | 标准模式 |
|------|----------|----------|
| 任务复杂度 | 简单 | 复杂 |
| 预计文件数 | 1-2 个 | 3+ 个 |
| max-turns | 5 | 15 |
| 执行方式 | 同步 exec | 后台 nohup + 轮询 |
| 用户等待 | 即时结果 | 需轮询等待 |
| 触发词 | 快速/简单/小改/>> | 默认 |

## 注意事项

- 提示词通过临时文件传递，避免命令行参数中的引号转义问题
- 标准模式下结果文件可能很大，读取时注意 exec 的 10k 字符截断限制，必要时分段读取
- Claude Code 每次调用都消耗 API tokens，复杂任务成本可能较高，始终报告 token 消耗
- 如果 npx 首次运行需要下载包，可能需要额外 30-60 秒

## 提示词模板

详见 `references/prompt-templates.md`，包含通用模板、bug 修复模板、功能添加模板等。
