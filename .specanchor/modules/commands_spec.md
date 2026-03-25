# Module Spec: commands — 统一命令系统（Phase 2.4）

> 状态：🔶 待迁移
> 优先级：Phase 2.4
> 预估工时：2h

---

## 1. 模块职责

跨平台统一斜杠命令管理系统。替代上游的 `CommandRouter`，提供可扩展的命令注册、分发和执行能力。

### 核心能力
- **命令注册**：`CommandRegistry` 管理所有可用命令
- **命令数据类**：`SlashCommand` 封装命令元数据（名称、描述、handler、权限等）
- **内置命令**：归档快照、记忆管理、任务管理等
- **pre_dispatch 模式**：支持在消息进入 Agent 前拦截命令

---

## 2. 源文件位置

| 类型 | 路径 |
|------|------|
| 源码（feat/0.0.1） | `nanobot/agent/commands.py`（+371 行，纯新增） |
| 计划实现位置 | `cafeext/agent/commands.py` |
| Patch 文件 | `cafeext/patches/commands_patch.py`（新建） |

---

## 3. 拦截点设计

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `AgentLoop._process_inbound` 或等效入口 | 方法包装 | 在消息处理前检查是否为斜杠命令 |
| 上游 `CommandRouter`（如存在） | 类替换 | 用 `CommandRegistry` 替换旧命令路由 |

### 拦截逻辑

1. 在消息进入 `AgentLoop` 处理流程前，检查消息是否以 `/` 开头
2. 若是斜杠命令，交由 `CommandRegistry.dispatch()` 处理
3. `pre_dispatch` 命令在消息到达 Agent 前执行（如 `/archive`），不消耗 LLM 调用
4. 非 `pre_dispatch` 命令将命令信息附加到消息上下文中

---

## 4. 接口设计

```python
@dataclass
class SlashCommand:
    """斜杠命令定义"""
    name: str                          # 命令名（不含 /）
    description: str                   # 命令描述
    handler: Callable                  # 命令处理函数
    pre_dispatch: bool = False         # 是否在消息分发前执行
    admin_only: bool = False           # 是否仅管理员可用
    channels: list[str] | None = None  # 限定可用渠道

class CommandRegistry:
    """统一命令注册中心"""

    def __init__(self, agent_loop: AgentLoop):
        ...

    def register(self, command: SlashCommand) -> None:
        """注册一个斜杠命令"""
        ...

    def unregister(self, name: str) -> bool:
        """注销一个斜杠命令"""
        ...

    def dispatch(self, message: InboundMessage) -> CommandResult | None:
        """分发命令，返回执行结果或 None（非命令消息）"""
        ...

    def list_commands(self, channel: str | None = None) -> list[SlashCommand]:
        """列出可用命令"""
        ...

def apply_commands_patch() -> str:
    """注册统一命令系统"""
    ...
```

### 内置命令列表

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
- `cafeext.agent.categorized_memory.CategorizedMemoryStore` — `/memory` 命令依赖
- `cafeext.storage.Database` — `/archive` 命令依赖

### 外部依赖
- 无

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
