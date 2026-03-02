---
name: restart-gateway
description: Schedule a delayed restart of the nanobot gateway to reload configuration. Use when user requests to restart, reload config, or apply configuration changes.
metadata: {"nanobot":{"emoji":"🔄","os":["darwin","linux"],"requires":{"bins":["bash"]}}}
---

# restart_gateway

延迟重启 nanobot gateway，用于重新加载配置文件。

## 功能描述

在指定的延迟时间后重启 nanobot gateway 服务，使配置更改生效。重启过程会：

1. 优雅地关闭当前运行的 gateway 进程
2. 等待进程完全退出
3. 重新启动新的 gateway 实例

## 使用方法

通过 `exec` 工具执行重启脚本（`{baseDir}` 会自动替换为技能目录路径）：

```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 5000 --confirm")
```

### 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--delay` | 延迟时间（毫秒），重启前等待的时间 | 60000 (60 秒) |
| `--confirm` | 确认标志，必须提供此标志才能执行重启 | 无 |
| `--force` | 强制重启，跳过优雅关闭直接 kill | 无 |

### 示例

**标准重启（60秒后）：**

```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 60000 --confirm")
```

**快速重启（10秒后）：**

```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 10000 --confirm")
```

**延迟重启（300秒后）：**

```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 300000 --confirm")
```

**强制重启（用于 gateway 无响应时）：**

```bash
exec(command="{baseDir}/scripts/restart_gateway.sh --delay 10000 --confirm --force")
```

## 使用 cron 调度定时重启

如果需要在未来某个时间点重启，可以使用 cron 工具：

```python
# 在指定时间重启
cron(action="add", message="exec bash /path/to/restart_gateway.sh --delay 1000 --confirm", at="2026-03-02T10:00:00")

# 每天凌晨3点重启以应用配置更新
cron(action="add", message="exec bash /path/to/restart_gateway.sh --delay 1000 --confirm", cron_expr="0 3 * * *", tz="Asia/Shanghai")
```

## 重启流程

```
用户请求 -> 确认检查 -> 延迟等待 -> 发送 SIGTERM -> 等待退出 -> 重新启动
                |                           |
                v                           v (超时)
            拒绝执行                     发送 SIGKILL
```

## 安全机制

1. **确认标志**：必须提供 `--confirm` 参数才能执行重启，防止意外触发
2. **延迟机制**：默认 60 秒延迟，给用户充足的时间取消或准备
3. **优雅关闭**：默认使用 SIGTERM 信号，让 gateway 有时间保存状态
4. **超时保护**：如果进程 30 秒内未退出，自动强制终止

## 注意事项

- 重启会导致当前所有会话中断，请在用户空闲时执行
- 重启后会话历史会保留（存储在 sessions 目录）
- 如果 gateway 是通过 systemd/supervisor 管理的，建议使用对应的服务管理命令
- 脚本会自动检测 gateway 的 PID，如果检测失败会报错

## 错误处理

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| "Confirmation required" | 未提供 --confirm 参数 | 添加 --confirm 参数 |
| "Gateway not running" | 找不到 gateway 进程 | 确认 gateway 正在运行 |
| "Restart failed" | 启动失败 | 检查配置文件是否正确 |

## 配合其他命令

**检查 gateway 状态：**

```bash
exec(command="ps aux | grep 'nanobot gateway' | grep -v grep")
```

**查看配置：**

```bash
exec(command="cat ~/.nanobot/config.json")
```

**验证配置：**

```bash
exec(command="nanobot status")
```
