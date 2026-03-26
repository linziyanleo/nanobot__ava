# Module Spec: loop_patch — AgentLoop 属性注入与 Token 统计

> 文件：`ava/patches/loop_patch.py`
> 状态：✅ 已实现（Phase 2）
> 执行顺序：在 `a_schema_patch`、`b_config_patch` 之后，在 `storage_patch` 之前

---

## 1. 模块职责

为 `AgentLoop` 注入 ava 扩展属性（`db`、`token_stats`、`media_service`），并在每次消息处理后记录 token 使用量。

### 核心能力
- **属性注入**：在 `AgentLoop.__init__` 完成后，绑定 Database、TokenStatsCollector、MediaService 实例
- **Token 统计**：包装 `_process_message`，在每轮 LLM 调用后记录 token 用量
- **Database 共享**：通过 `set_shared_db()` 接口接收来自 `storage_patch` 的共享 Database 实例

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `AgentLoop.__init__` | 方法包装 | 在原始初始化后注入 `db`/`token_stats`/`media_service` |
| `AgentLoop._process_message` | 方法包装 | 在原始处理后记录 token usage |

### 2.1 __init__ 拦截

- **原始行为**：初始化 AgentLoop 的核心属性（provider、model、workspace、tools 等）
- **修改后行为**：
  1. 调用原始 `__init__`
  2. 创建/获取 Database 实例 → `self.db`
  3. 创建 TokenStatsCollector → `self.token_stats`（失败时设为 None）
  4. 创建 MediaService → `self.media_service`（失败时设为 None）

### 2.2 _process_message 拦截

- **原始行为**：处理一条入站消息，调用 LLM 生成回复
- **修改后行为**：
  1. 快照当前 `_last_usage`
  2. 调用原始 `_process_message`
  3. 比较 usage 变化，若有变化则记录到 `token_stats`
  4. 记录内容：model、provider、usage delta、session_key、model_role

---

## 3. Database 共享机制

```python
# 模块级共享变量
_shared_db = None

def set_shared_db(db) -> None:
    """由 storage_patch 调用，共享 Database 实例"""
    global _shared_db
    _shared_db = db

def _get_or_create_db(workspace_path):
    """优先使用共享 db，否则创建新实例"""
    if _shared_db is not None:
        return _shared_db
    return Database(workspace_path / "data" / "nanobot.db")
```

### 执行顺序说明
- `loop_patch`（`l`）在 `storage_patch`（`s`）之前执行（字母序）
- `loop_patch` 首次创建 fallback Database
- `storage_patch` 随后调用 `set_shared_db()` 共享其 Database 实例
- 后续创建的 `AgentLoop` 实例将获得共享的 Database

---

## 4. 依赖关系

### 上游依赖
- `nanobot.agent.loop.AgentLoop` — 拦截目标（`__init__` 和 `_process_message`）

### Sidecar 内部依赖
- `ava.storage.Database` — SQLite 数据库封装
- `ava.console.services.token_stats_service.TokenStatsCollector` — Token 统计收集器
- `ava.console.services.media_service.MediaService` — 媒体服务（图片管理）
- `ava.launcher.register_patch` — 自注册机制

### 被依赖
- `storage_patch.py` — 调用 `set_shared_db()` 共享 Database
- `tools_patch.py` — 依赖 `self.token_stats`、`self.media_service`、`self.db`

---

## 5. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| 属性注入 | `AgentLoop` 实例拥有 `db`、`token_stats`、`media_service` |
| TokenStats 失败 | TokenStatsCollector 初始化失败时 `self.token_stats = None` |
| MediaService 失败 | MediaService 初始化失败时 `self.media_service = None` |
| Token 记录 | `_process_message` 后 token usage 被记录 |
| Usage 无变化 | LLM 未调用时不记录 |
| shared_db | `set_shared_db()` 后新 AgentLoop 获得共享 db |
| fallback db | `_shared_db` 为 None 时创建独立 Database |
| 幂等性 | 多次调用不重复包装 |
