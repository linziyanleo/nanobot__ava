---
specanchor:
  level: module
  module_name: "分类记忆系统"
  module_path: "ava/agent/categorized_memory.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-03-26"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "按 SpecAnchor 最新 Module Spec 模板重生，合并 legacy spec 与当前代码扫描结果"
  status: "active"
  depends_on:
    - "nanobot/utils/helpers.py"
    - "nanobot/agent/tools/base.py"
    - "ava/tools/memory_tool.py"
    - "ava/patches/loop_patch.py"
    - "ava/patches/context_patch.py"
    - "ava/patches/tools_patch.py"
---

# 分类记忆系统 (categorized_memory)

## 1. 模块职责
- **身份解析**：IdentityResolver 根据 channel + chat_id 解析用户身份
- **分类存储**：CategorizedMemoryStore 按用户分类存储和检索记忆
- **记忆管理**：支持记忆的增删改查操作

## 2. 业务规则
- loop_patch 会在 AgentLoop 初始化后尝试创建 `self.categorized_memory`，失败时降级为 `None`
- context_patch 仅在 `categorized_memory` 可用时向系统提示词注入个人记忆，缺失时不阻塞消息构建
- tools_patch 仅在 `categorized_memory` 已初始化时注册 `MemoryTool`
- `identity_map.yaml` 缺失、身份无法解析或持久化失败时必须优雅降级，不能影响主对话链路

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `IdentityResolver` | `class` | Resolves channel:chat_id pairs to a person name using identity_map.yaml. |
| `CategorizedMemoryStore` | `class` | Per-person memory store with identity resolution and source-level tracking. |
| `MemoryTool` | `class` | Tool for the agent to recall, remember, and manage categorized memory. |
| `MemoryTool.execute()` | `execute(action: str, **kwargs) -> str` | 公共方法 |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| 运行时状态 | — | 当前模块以局部变量和调用方注入对象为主 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.agent.loop.AgentLoop — 绑定记忆存储实例
- nanobot.agent.context.ContextBuilder — 注入记忆到系统提示词
- ava.tools.memory_tool.MemoryTool — 已在 tools_patch 中条件注册，依赖 self.categorized_memory
- ava.storage.Database — 可选，记忆持久化到 SQLite

## 5. 已知约束 & 技术债
- [ ] 当前接入依赖 `loop_patch`、`context_patch` 与 `tools_patch` 的协同；任一链路改名都要同步更新 Spec。
- [ ] `identity_map.yaml` 仍是运行时外部依赖，工作区缺少映射文件时只能退化为无个性化记忆。
- [ ] 记忆注入文案与 `MemoryTool` 行为尚未抽成统一契约，后续若调整提示词格式需要同步 console / task spec。

## 6. TODO
- [ ] 按当前 task / execute 计划补齐尚未闭环的实现与验证。 @ZiyanLin
- [ ] 后续实现变更时同步修正文档中的职责、规则与关键文件表 @ZiyanLin
- [ ] 收口当前遗留的集成缺口并补回归验证 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/agent/categorized_memory.py`
- **核心链路**: `categorized_memory.py` → 核心处理逻辑 → 调用方/上游集成点
- **数据流**: 输入上下文 → 模块处理/存储/压缩 → 输出给调用方或后续链路
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/agent/categorized_memory.py` | 模块主入口 |
| `ava/tools/memory_tool.py` | 关联链路文件 |
- **外部依赖**: `nanobot/utils/helpers.py`、`nanobot/agent/tools/base.py`、`ava/tools/memory_tool.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-agent-categorized_memory.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
