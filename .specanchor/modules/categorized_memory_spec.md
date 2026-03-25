# Module Spec: categorized_memory — 分类记忆系统（Phase 2.1）

> 状态：🔶 待迁移
> 优先级：Phase 2.1
> 预估工时：1h

---

## 1. 模块职责

基于身份的分类记忆系统。通过 `identity_map.yaml` 将 channel:chat_id 映射到人名，为每个用户维护独立的记忆存储，实现个性化交互。

### 核心能力
- **身份解析**：`IdentityResolver` 根据 channel + chat_id 解析用户身份
- **分类存储**：`CategorizedMemoryStore` 按用户分类存储和检索记忆
- **记忆管理**：支持记忆的增删改查操作

---

## 2. 源文件位置

| 类型 | 路径 |
|------|------|
| 源码（feat/0.0.1） | `nanobot/agent/categorized_memory.py`（+247 行，纯新增） |
| 计划实现位置 | `ava/agent/categorized_memory.py` |
| Patch 文件 | `ava/patches/memory_patch.py`（新建） |
| 配置文件 | `{workspace}/identity_map.yaml` |

---

## 3. 拦截点设计

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `ContextBuilder.build_system_prompt` | 方法包装 | 在系统提示词中注入用户记忆 |
| `AgentLoop.__init__` | 方法包装 | 在初始化时创建 `CategorizedMemoryStore` 实例并绑定到 `self.categorized_memory` |

### 拦截逻辑

1. 在 `AgentLoop.__init__` 完成后，根据配置创建 `CategorizedMemoryStore` 实例
2. 在 `ContextBuilder.build_system_prompt` 中，根据当前 channel/chat_id 解析用户身份，注入对应记忆

---

## 4. 接口设计

```python
class IdentityResolver:
    """从 identity_map.yaml 解析 channel:chat_id → 人名映射"""

    def __init__(self, config_path: Path):
        ...

    def resolve(self, channel: str, chat_id: str) -> str | None:
        """返回用户名称，未找到返回 None"""
        ...

class CategorizedMemoryStore:
    """按用户分类的记忆存储"""

    def __init__(self, workspace: Path, identity_resolver: IdentityResolver):
        ...

    def get_memories(self, user: str) -> list[str]:
        """获取指定用户的所有记忆"""
        ...

    def add_memory(self, user: str, content: str) -> None:
        """为指定用户添加记忆"""
        ...

    def remove_memory(self, user: str, index: int) -> bool:
        """删除指定用户的某条记忆"""
        ...

def apply_memory_patch() -> str:
    """注册分类记忆到 AgentLoop 和 ContextBuilder"""
    ...
```

---

## 5. 依赖关系

### 上游依赖
- `nanobot.agent.loop.AgentLoop` — 绑定记忆存储实例
- `nanobot.agent.context.ContextBuilder` — 注入记忆到系统提示词

### Sidecar 内部依赖
- `ava.tools.memory_tool.MemoryTool` — 已在 `tools_patch` 中注册，依赖 `categorized_memory`
- `ava.storage.Database` — 可选，记忆持久化到 SQLite

### 外部依赖
- `PyYAML` — 解析 `identity_map.yaml`

---

## 6. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 身份解析 | channel:chat_id 正确映射到用户名 |
| 未知用户 | 未在 identity_map 中的用户返回 None |
| 记忆隔离 | 不同用户的记忆互不干扰 |
| 记忆 CRUD | 增删改查操作正确 |
| 系统提示词注入 | 记忆内容正确出现在系统提示词中 |
| 配置文件缺失 | identity_map.yaml 不存在时优雅降级 |
