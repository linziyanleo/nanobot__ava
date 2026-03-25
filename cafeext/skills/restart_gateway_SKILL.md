---
name: restart-gateway
description: Schedule a delayed restart of the nanobot gateway with automatic Telegram status report. Uses system at command for reliable report scheduling and launchd watchdog for process monitoring.
metadata: {"nanobot":{"emoji":"🔄","os":["darwin","linux"],"requires":{"bins":["bash","at"]}}}
---

# restart_gateway

延迟重启 nanobot gateway，用于重新加载配置文件，**重启后通过系统 at 命令自动汇报状态**。

## 架构概述 (v3)

```
重启流程:
Agent exec → restart_gateway.sh → restart_wrapper.sh (立即返回)
                                          ↓
                                  restart_daemon.sh (后台运行)
                                          ↓
                          1. 保存状态 → 2. 创建 at 汇报任务 → 3. 延迟
                                          ↓
                          4. 关闭旧进程 → 5. 启动新进程 → 6. 验证
                                          ↓
                          [1 分钟后] at → at_report.sh → Telegram 汇报

看门狗流程 (每 5 分钟):
launchd → gateway_watchdog.sh → 检查进程数
                                  - 0 个: 自动启动 Gateway
                                  - 1 个: 正常
                                  - >1 个: 清理多余进程
```

### 核心设计原则

1. **重启不依赖 Gateway**: 守护脚本后台运行，不受 Gateway 关闭影响
2. **使用系统 at 命令**: 汇报任务由系统调度，不依赖 CronService
3. **看门狗自动恢复**: 进程异常退出时自动重启
4. **多进程自动清理**: 确保始终只有 1 个 Gateway 运行

## 使用方法

通过 `exec` 工具执行重启脚本：

```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 5000 --confirm")
```

### 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--delay` | 延迟时间（毫秒） | 5000 |
| `--confirm` | 确认标志（必须） | - |
| `--force` | 强制 kill（跳过优雅关闭） | - |
| `--no-report` | 禁用 Telegram 汇报 | - |

### 示例

**标准重启（5 秒延迟，自动汇报）：**
```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 5000 --confirm")
```

**快速重启（1 秒延迟）：**
```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 1000 --confirm")
```

**强制重启（Gateway 无响应时）：**
```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 1000 --confirm --force")
```

**禁用汇报：**
```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 5000 --confirm --no-report")
```

## 脚本架构

| 脚本 | 功能 |
|------|------|
| `restart_gateway.sh` | 入口脚本 |
| `restart_wrapper.sh` | 启动守护进程，立即返回 |
| `restart_daemon.sh` | 执行重启 + 创建 at 汇报任务 |
| `at_report.sh` | at 任务调用，发送 Telegram 汇报 |
| `gateway_watchdog.sh` | 看门狗，维持进程数为 1 |

## 自动汇报功能

### 工作原理

重启时守护脚本使用系统 `at` 命令创建汇报任务：
- **执行时间**: 延迟 + 30秒 + 10秒（向上取整到分钟）
- **执行内容**: 检查 Gateway 状态，发送 Telegram 汇报
- **不依赖 Gateway**: at 是系统级服务，Gateway 关闭不影响

### 汇报内容

```
🔄 Gateway 重启状态汇报

✅ 重启已完成！
📁 状态文件：/tmp/gateway_restart_state.json
⏰ 重启时间：2026-03-03T09:23:49+08:00
⏱️ 延迟：5000ms
🔧 模式：正常

📊 当前状态：
- Gateway: ✅ 运行中 (PID: 34980, 时长：01:30)
```

### 前置条件 (macOS)

at 服务需要手动启用（只需执行一次）：

```bash
sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.atrun.plist
```

## 看门狗功能

### 功能说明

看门狗脚本每 5 分钟检查 Gateway 进程状态：
- **0 个进程**: 自动启动 Gateway
- **1 个进程**: 正常，无操作
- **>1 个进程**: 清理多余进程，只保留最新的

### 启用看门狗

```bash
# 复制 plist 到 LaunchAgents
cp {baseDir}/scripts/com.nanobot.gateway.watchdog.plist ~/Library/LaunchAgents/

# 加载并启动
launchctl load ~/Library/LaunchAgents/com.nanobot.gateway.watchdog.plist
```

### 禁用看门狗

```bash
launchctl unload ~/Library/LaunchAgents/com.nanobot.gateway.watchdog.plist
```

### 查看状态

```bash
# 检查 launchd 状态
launchctl list | grep nanobot

# 查看日志
cat /tmp/gateway_watchdog.log
```

## 日志文件

| 文件 | 说明 |
|------|------|
| `/tmp/gateway_restart_daemon.log` | 重启守护进程日志 |
| `/tmp/gateway_at_report.log` | at 汇报任务日志 |
| `/tmp/gateway_watchdog.log` | 看门狗日志 |
| `/tmp/nanobot_gateway.log` | Gateway 进程日志 |
| `/tmp/gateway_restart_state.json` | 重启状态文件 |

## 安全机制

1. **确认标志**: 必须提供 `--confirm` 参数，防止意外触发
2. **延迟机制**: 默认 5 秒延迟，给用户时间取消
3. **优雅关闭**: 默认 SIGTERM，30 秒超时后 SIGKILL
4. **自动汇报**: 系统级 at 调度，确保汇报执行
5. **看门狗保护**: 进程异常退出自动恢复
6. **多进程清理**: 确保只有 1 个 Gateway 运行

## 故障排查

### 重启失败

```bash
# 检查重启日志
exec(command="cat /tmp/gateway_restart_daemon.log")

# 检查 Gateway 进程
exec(command="ps aux | grep -E 'nanobot.*gateway' | grep -v grep")

# 检查 Gateway 日志
exec(command="tail -100 /tmp/nanobot_gateway.log")
```

### 汇报未发送

```bash
# 检查 at 任务队列
exec(command="atq")

# 检查 at 服务状态
exec(command="launchctl list | grep atrun")

# 检查汇报日志
exec(command="cat /tmp/gateway_at_report.log")

# 手动测试汇报脚本
exec(command="{baseDir}/scripts/at_report.sh")
```

### 看门狗未工作

```bash
# 检查 launchd 状态
exec(command="launchctl list | grep nanobot")

# 检查日志
exec(command="cat /tmp/gateway_watchdog.log")

# 手动运行看门狗
exec(command="{baseDir}/scripts/gateway_watchdog.sh")
```

### 手动恢复

```bash
# 手动启动 Gateway
exec(command="nohup nanobot gateway >> /tmp/nanobot_gateway.log 2>&1 &")

# 验证启动
exec(command="ps aux | grep -E 'nanobot.*gateway' | grep -v grep")
```

## 配置说明

### at_report.sh 代理配置

默认使用 `http://127.0.0.1:7890` 代理访问 Telegram API。可通过环境变量覆盖：

- `ALL_PROXY`
- `HTTPS_PROXY`
- `HTTP_PROXY`

### 看门狗配置

launchd plist 文件位于 `{baseDir}/scripts/com.nanobot.gateway.watchdog.plist`：
- 执行间隔: 300 秒 (5 分钟)
- 系统启动时执行: 是
- 优先级: Nice 10 (低优先级)

## 注意事项

1. **at 服务必须启用**: macOS 默认禁用 atrun 服务
2. **代理配置**: 访问 Telegram 需要代理（中国大陆）
3. **看门狗是可选的**: 只在需要高可用时启用
4. **重启会中断会话**: 请在用户空闲时执行
5. **会话历史保留**: 存储在 sessions 目录，重启不丢失
