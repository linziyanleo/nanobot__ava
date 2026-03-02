---
name: restart-gateway
description: Schedule a delayed restart of the nanobot gateway with automatic status report. Use when user requests to restart, reload config, or apply configuration changes. Uses daemon-based architecture for reliable restart.
metadata: {"nanobot":{"emoji":"🔄","os":["darwin","linux"],"requires":{"bins":["bash"]}}}
---

# restart_gateway

延迟重启 nanobot gateway，用于重新加载配置文件，**重启后自动汇报状态**。

## 功能描述

在指定的延迟时间后重启 nanobot gateway 服务，使配置更改生效。

### 新版架构 (v2) - 独立守护进程模式

新版本使用独立守护进程模式，**确保重启流程不受 Gateway 进程关闭影响**：

```
Agent 调用 exec
    ↓
restart_gateway.sh
    ↓
restart_wrapper.sh (立即返回)
    ↓ 启动独立进程
restart_daemon.sh (完全脱离 Gateway)
    ↓
延迟等待 → 关闭旧进程 → 启动新进程 → 汇报
```

重启过程会：

1. **启动独立守护进程**（完全脱离 Gateway 进程树）
2. **立即返回**（Agent 可以继续响应用户）
3. **延迟等待**（根据 delay 参数）
4. **优雅关闭**当前 Gateway 进程
5. **启动新** Gateway 实例
6. **自动汇报**（30 秒后执行，向用户发送状态报告）

## 使用方法

通过 `exec` 工具执行重启脚本（`{baseDir}` 会自动替换为技能目录路径）：

```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 5000 --confirm")
```

重要：此脚本会立即返回，实际重启流程在后台独立进程中执行。

### 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--delay` | 延迟时间（毫秒），重启前等待的时间 | 5000 (5 秒) |
| `--confirm` | 确认标志，必须提供此标志才能执行重启 | 无 |
| `--force` | 强制重启，跳过优雅关闭直接 kill | 无 |
| `--no-report` | **禁用自动汇报**（默认启用） | 无 |
| `--legacy` | 使用旧版内联重启模式（不推荐） | 无 |

### 示例

**标准重启（5 秒后，自动汇报）：**

```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 5000 --confirm")
```

**快速重启（1 秒后，自动汇报）：**

```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 1000 --confirm")
```

**禁用自动汇报：**

```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 5000 --confirm --no-report")
```

**强制重启（用于 gateway 无响应时）：**

```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 1000 --confirm --force")
```

## 自动汇报功能

### 默认行为

默认情况下，守护脚本会在重启前自动创建一个**一次性 cron 任务**，该任务会在：
- **执行时间**：重启完成后约 30 秒
- **执行内容**：检查 gateway 状态并向 Leo 发送汇报消息
- **自动删除**：汇报完成后任务自动删除

注意：由于使用独立守护进程，汇报任务直接写入 `jobs.json`，
不依赖 Gateway 进程，确保重启后能正确执行。

### 汇报内容

汇报消息包含：
- ✅ 重启完成状态
- 📁 状态文件路径（`/tmp/gateway_restart_state.json`）
- ⏰ 重启时间
- ⏱️ 延迟配置
- 🔧 运行模式（普通/强制）

### 禁用汇报

如果不需要自动汇报（例如测试环境），可以使用 `--no-report` 参数：

```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 10000 --confirm --no-report")
```

## 使用 cron 调度定时重启

如果需要在未来某个时间点重启，可以使用 cron 工具：

```python
# 在指定时间重启
cron(action="add", message="exec bash /path/to/restart_gateway.sh --delay 1000 --confirm", at="2026-03-02T10:00:00")

# 每天凌晨 3 点重启以应用配置更新
cron(action="add", message="exec bash /path/to/restart_gateway.sh --delay 1000 --confirm", cron_expr="0 3 * * *", tz="Asia/Shanghai")
```

## 重启流程

```
用户请求 -> Agent exec -> restart_gateway.sh -> restart_wrapper.sh
                                                            |
                                                            v
                                                     启动独立守护进程
                                                            |
                                                            v
                                                   restart_daemon.sh
                                                   (完全脱离 Gateway)
                                                            |
                                                            v
     +----------------------------------------------------------+
     |                                                          |
     v                                                          v
创建汇报任务                                            延迟等待
(jobs.json)                                                   |
                                                            v
                                        发送 SIGTERM -> 等待退出 -> 重新启动
                                              |                           |
                                              v (超时)                    v
                                         发送 SIGKILL               验证成功
                                                                        |
                                                                        v
                                                         30秒后汇报任务执行
                                                                        |
                                                                        v
                                                                   任务自动删除
```

## 安全机制

1. **确认标志**：必须提供 `--confirm` 参数才能执行重启，防止意外触发
2. **延迟机制**：默认 5 秒延迟，给用户充足的时间取消或准备
3. **优雅关闭**：默认使用 SIGTERM 信号，让 gateway 有时间保存状态
4. **超时保护**：如果进程 30 秒内未退出，自动强制终止
5. **自动汇报**：重启后自动汇报状态，让用户知道重启成功
6. **独立守护进程**：重启流程不受 Gateway 关闭影响，确保完整执行

## 日志文件

| 文件 | 说明 |
|------|------|
| `/tmp/gateway_restart_daemon.log` | 守护进程详细日志 |
| `/tmp/nanobot_gateway.log` | Gateway 进程日志 |
| `/tmp/gateway_restart_state.json` | 重启状态文件 |

## 注意事项

- 重启会导致当前所有会话中断，请在用户空闲时执行
- 重启后会话历史会保留（存储在 sessions 目录）
- 如果 gateway 是通过 systemd/supervisor 管理的，建议使用对应的服务管理命令
- **脚本会立即返回**，实际重启在后台独立进程中执行
- 可通过查看日志文件跟踪重启进度

## 错误处理

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| "Confirmation required" | 未提供 --confirm 参数 | 添加 --confirm 参数 |
| "Gateway not running" | 找不到 gateway 进程 | 脚本将直接启动新进程 |
| "Restart failed" | 启动失败 | 检查 /tmp/nanobot_gateway.log |
| "守护进程启动失败" | 脚本执行错误 | 检查 /tmp/gateway_restart_daemon.log |
| "汇报任务未执行" | jobs.json 写入失败 | 手动检查 Gateway 状态 |

## 配合其他命令

**检查 gateway 状态：**

```bash
exec(command="ps aux | grep 'nanobot gateway' | grep -v grep")
```

**查看守护进程日志：**

```bash
exec(command="cat /tmp/gateway_restart_daemon.log")
```

**查看 Gateway 日志：**

```bash
exec(command="tail -50 /tmp/nanobot_gateway.log")
```

**查看状态文件：**

```bash
exec(command="cat /tmp/gateway_restart_state.json")
```

**查看 cron 任务（确认汇报任务已创建）：**

```bash
nanobot cron list
```

## 故障恢复

如果重启失败（Gateway 未启动）：

```bash
# 1. 检查守护进程日志
exec(command="cat /tmp/gateway_restart_daemon.log")

# 2. 检查 Gateway 日志
exec(command="tail -100 /tmp/nanobot_gateway.log")

# 3. 手动启动 Gateway
exec(command="nohup nanobot gateway > /tmp/nanobot_gateway.log 2>&1 &")

# 4. 验证启动
exec(command="ps aux | grep 'nanobot gateway' | grep -v grep")
```
