---
specanchor:
  level: module
  module_name: "统一命令系统"
  module_path: "ava/agent/commands.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-03-26"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "按 SpecAnchor 最新 Module Spec 模板重生，合并 legacy spec 与当前代码扫描结果"
  status: "draft"
  depends_on:
    - "nanobot/agent/memory.py"
    - "nanobot/session/manager.py"
---

# 统一命令系统 (commands)

## 1. 模块职责
- **命令注册**：CommandRegistry 管理所有可用命令
- **命令数据类**：SlashCommand 封装命令元数据（名称、描述、handler、权限等）
- **内置命令**：归档快照、记忆管理、任务管理等
- **pre_dispatch 模式**：支持在消息进入 Agent 前拦截命令

## 2. 业务规则
- CommandRegistry 构造函数需要 AgentLoop 实例
- 与 InboundMessage 的集成需要验证字段兼容性
- 运行时对象按需初始化，避免 import 时产生重副作用
- 调用方注入的 loop / db / service 缺失时需要可降级

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `SlashCommand` | `class` | A registered slash command. |
| `CommandRegistry` | `class` | Registry of slash commands available across all channels. |
| `register_builtin_commands()` | `register_builtin_commands(registry: CommandRegistry, agent: AgentLoop) -> None` | Register the built-in slash commands. |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| _boot_time | module | 模块级共享状态或常量 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.agent.loop.AgentLoop — 消息处理入口
- nanobot.bus.events.InboundMessage — 消息数据结构
- ava.agent.categorized_memory.CategorizedMemoryStore — /memory 命令依赖
- ava.storage.Database — /archive 命令依赖

## 5. 已知约束 & 技术债
- [ ] 当前状态为 `draft`，仍需继续收口实现或接入边界。
- [ ] 当前代码仍未替换上游 `CommandRouter`，真实运行时主入口还不经过本模块。
- [ ] 仍需补 `ava/patches/commands_patch.py` 或在现有 loop patch 中明确接入点。
- [ ] `/memory`、`/archive`、`/tasks` 等命令依赖的下游对象尚未做端到端集成验证。

## 6. TODO
- [ ] 按当前 task / execute 计划补齐尚未闭环的实现与验证。 @ZiyanLin
- [ ] 后续实现变更时同步修正文档中的职责、规则与关键文件表 @ZiyanLin
- [ ] 收口当前遗留的集成缺口并补回归验证 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/agent/commands.py`
- **核心链路**: `commands.py` → 核心处理逻辑 → 调用方/上游集成点
- **数据流**: 输入上下文 → 模块处理/存储/压缩 → 输出给调用方或后续链路
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/agent/commands.py` | 模块主入口 |
- **外部依赖**: `nanobot/agent/memory.py`、`nanobot/session/manager.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-agent-commands.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
