# Module Spec: categorized_memory — 分类记忆系统

> 状态：🟡 已复制到 `ava/agent/categorized_memory.py`，未接入 AgentLoop
> 原始来源：`feat/0.0.1` 分支 `nanobot/agent/categorized_memory.py`（+247 行）

---

## 1. 模块职责

基于身份的分类记忆系统。通过 `identity_map.yaml` 将 channel:chat_id 映射到人名，为每个用户维护独立的记忆存储，实现个性化交互。

### 核心能力
- **身份解析**：`IdentityResolver` 根据 channel + chat_id 解析用户身份
- **分类存储**：`CategorizedMemoryStore` 按用户分类存储和检索记忆
- **记忆管理**：支持记忆的增删改查操作

---

## 2. 文件位置

| 类型 | 路径 |
|------|------|
| 当前实现 | `ava/agent/categorized_memory.py` ✅ 已复制 |
| Patch 文件（待创建） | `ava/patches/memory_patch.py` 或扩展 `loop_patch.py` |
| 配置文件 | `{workspace}/identity_map.yaml` |

---

## 3. 接入方案（下一步）

需要在 `loop_patch.py` 中扩展 `patched_init`，添加以下逻辑：

```python
# 在 AgentLoop.__init__ patch 中追加：
from ava.agent.categorized_memory import CategorizedMemoryStore, IdentityResolver

identity_resolver = IdentityResolver(workspace / "identity_map.yaml")
self.categorized_memory = CategorizedMemoryStore(
    workspace=workspace,
    identity_resolver=identity_resolver,
)
```

### 拦截点

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `AgentLoop.__init__`（已有 patch） | 扩展 | 在 loop_patch 中追加 `self.categorized_memory` 赋值 |
| `ContextBuilder.build_system_prompt` | 方法包装（新增） | 在系统提示词中注入用户记忆 |

---

## 4. 依赖关系

### 上游依赖
- `nanobot.agent.loop.AgentLoop` — 绑定记忆存储实例
- `nanobot.agent.context.ContextBuilder` — 注入记忆到系统提示词

### Sidecar 内部依赖
- `ava.tools.memory_tool.MemoryTool` — 已在 `tools_patch` 中条件注册，依赖 `self.categorized_memory`
- `ava.storage.Database` — 可选，记忆持久化到 SQLite

### 外部依赖
- `PyYAML` — 解析 `identity_map.yaml`

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 身份解析 | channel:chat_id 正确映射到用户名 |
| 未知用户 | 未在 identity_map 中的用户返回 None |
| 记忆隔离 | 不同用户的记忆互不干扰 |
| 记忆 CRUD | 增删改查操作正确 |
| 系统提示词注入 | 记忆内容正确出现在系统提示词中 |
| 配置文件缺失 | identity_map.yaml 不存在时优雅降级 |
| MemoryTool 联动 | categorized_memory 存在时 MemoryTool 被注册 |
