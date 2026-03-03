---
name: qodercli
description: "使用 Qoder CLI 进行专业代码编程。遇到复杂代码问题、架构设计、大规模重构或主人明确要求时，调用 qodercli 解决。默认使用 Ultimate 模型，自动加载 skills。"
metadata: {"nanobot":{"emoji":"🚀","requires":{"bins":["qodercli"]}}}
---

# Qodercli 编程技能

当遇到需要专业代码能力的任务时，使用 Qoder CLI 进行解决。

## 何时使用

**主动使用场景**：

- 复杂代码问题（多文件修改、架构调整、大规模重构）
- 需要深度代码理解和分析的任务
- 调试困难的 bug（需要跨文件追踪）
- 主人明确要求使用 qodercli

**不需要使用的场景**：

- 简单的单文件修改
- 查询信息、聊天等非代码任务
- 已经能够直接解决的简单问题

## 默认配置

- **模型**：Ultimate（最强代码能力）
- **工作目录**：项目根目录
- **自动加载**：skills（技能增强）

## 基础用法

### 交互模式（TUI）

```bash
# 在项目目录启动 qodercli
cd /path/to/project
qodercli
```

### 非交互模式（Print Mode）

```bash
# 直接执行任务并获取结果
qodercli -p "你的任务描述"

# 指定输出格式
qodercli -p "任务描述" --output-format=json
```

### 指定工作目录

```bash
qodercli -w /path/to/project -p "任务描述"
```

## 常用命令

### TUI 输入模式

| 模式 | 触发 | 说明 |
|------|------|------|
| 对话 | `>` | 默认模式，直接输入任务 |
| Bash | `!` | 执行 shell 命令 |
| 斜杠 | `/` | 内置命令 |
| 记忆 | `#` | 编辑 AGENTS.md |

### 斜杠命令

| 命令 | 用途 |
|------|------|
| `/help` | 显示帮助 |
| `/init` | 初始化项目记忆文件 |
| `/memory` | 编辑记忆文件 |
| `/quest` | 基于 Spec 的任务委派 |
| `/review` | 代码评审 |
| `/resume` | 恢复会话 |
| `/clear` | 清除上下文 |
| `/compact` | 压缩上下文 |
| `/status` | 查看状态 |

## 高级参数

```bash
# 继续上次会话
qodercli -c

# 恢复指定会话
qodercli -r <session-id>

# 限制工具
qodercli --allowed-tools=READ,WRITE
qodercli --disallowed-tools=BASH

# 限制对话轮数
qodercli --max-turns=10

# 跳过权限检查（谨慎使用）
qodercli --yolo
```

## MCP 集成

```bash
# 添加 MCP 服务
qodercli mcp add <name> -- <command>

# 推荐的 MCP 工具
qodercli mcp add context7 -- npx -y @upstash/context7-mcp@latest
qodercli mcp add deepwiki -- npx -y mcp-deepwiki@latest

# 列出/移除 MCP
qodercli mcp list
qodercli mcp remove <name>
```

## 并行任务（Worktree）

```bash
# 创建并行任务（隔离的 worktree）
qodercli --worktree "任务描述"

# 查看所有任务
qodercli jobs --worktree

# 删除任务
qodercli rm <jobId>
```

## 执行示例

当主人说 "帮我重构这个模块" 或遇到复杂代码问题时：

```bash
# 方式1：交互模式
cd /path/to/project
qodercli

# 方式2：直接执行
qodercli -w /path/to/project -p "重构 xxx 模块，要求：..."

# 方式3：带上下文的任务
qodercli -p "分析并修复 xxx 文件中的 bug，错误信息：..."
```

## 注意事项

1. **项目路径**：确保在正确的项目目录下执行，或使用 `-w` 指定
2. **权限控制**：qodercli 有细粒度权限控制，敏感操作会询问确认
3. **会话管理**：使用 `/resume` 可恢复之前的会话继续工作
4. **记忆文件**：AGENTS.md 会被自动加载为上下文，可用 `/init` 生成
