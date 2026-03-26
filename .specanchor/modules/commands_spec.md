# Module Spec: commands — 统一命令系统

> 状态：🟡 已复制到 `ava/agent/commands.py`，未接入 AgentLoop
> 原始来源：`feat/0.0.1` 分支 `nanobot/agent/commands.py`（+371 行）

---

## 1. 模块职责

跨平台统一斜杠命令管理系统。替代上游的 `CommandRouter`，提供可扩展的命令注册、分发和执行能力。

### 核心能力
- **命令注册**：`CommandRegistry` 管理所有可用命令
- **命令数据类**：`SlashCommand` 封装命令元数据（名称、描述、handler、权限等）
- **内置命令**：归档快照、记忆管理、任务管理等
- **pre_dispatch 模式**：支持在消息进入 Agent 前拦截命令

---

## 2. 文件位置

| 类型 | 路径 |
|------|------|
| 当前实现 | `ava/agent/commands.py` ✅ 已复制 |
| Patch 文件（待创建） | `ava/patches/commands_patch.py` |

---

## 3. 接入方案（下一步）

需要 patch `AgentLoop.__init__` 将 `self.commands`（当前为 `CommandRouter`）替换为 `CommandRegistry`。

### 拦截点

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `AgentLoop.__init__`（已有 patch） | 扩展 | 替换 `self.commands` 为 `CommandRegistry` |
| `AgentLoop._process_inbound` 或等效入口 | 方法包装 | 在消息处理前检查是否为斜杠命令 |

### 依赖说明
- `CommandRegistry` 构造函数需要 `AgentLoop` 实例
- 与 `InboundMessage` 的集成需要验证字段兼容性

---

## 4. 内置命令列表

| 命令 | 功能 | pre_dispatch |
|------|------|:------------:|
| `/archive` | 归档当前对话快照 | ✅ |
| `/memory` | 查看/管理用户记忆 | ✅ |
| `/tasks` | 查看后台任务状态 | ✅ |
| `/help` | 显示可用命令列表 | ✅ |

---

## 5. 依赖关系

### 上游依赖
- `nanobot.agent.loop.AgentLoop` — 消息处理入口
- `nanobot.bus.events.InboundMessage` — 消息数据结构

### Sidecar 内部依赖
- `ava.agent.categorized_memory.CategorizedMemoryStore` — `/memory` 命令依赖
- `ava.storage.Database` — `/archive` 命令依赖

---

## 6. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 命令注册 | 注册后可通过 dispatch 调用 |
| 命令注销 | 注销后 dispatch 不再识别 |
| pre_dispatch | pre_dispatch 命令在消息分发前执行 |
| 非命令消息 | 普通消息透传不被拦截 |
| 未知命令 | 未注册的 `/xxx` 返回友好错误 |
| 渠道限制 | 限定渠道的命令在其他渠道不可用 |
| admin 权限 | admin_only 命令检查权限 |
| 命令列表 | list_commands 正确过滤渠道 |
