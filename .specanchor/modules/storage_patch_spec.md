# Module Spec: storage_patch — SQLite 存储层替换

> 文件：`ava/patches/storage_patch.py`
> 状态：✅ 已实现（Phase 1 创建，Phase 2 新增 db 共享）

---

## 1. 模块职责

将 nanobot 的 Session 持久化从 JSONL 文件存储替换为 SQLite 数据库存储，提供更好的查询能力、并发安全和数据完整性。同时将 Database 实例共享给 `loop_patch`。

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| `SessionManager.save` | 方法替换 | 将 session 保存到 SQLite |
| `SessionManager._load` | 方法替换 | 从 SQLite 加载 session |
| `SessionManager.list_sessions` | 方法替换 | 从 SQLite 列出所有 session |

### 2.1 Save 拦截

- **原始行为**：将 session 序列化为 JSON 并追加到 JSONL 文件
- **修改后行为**：将 session 写入 SQLite 的 `sessions` 表和 `session_messages` 表
- **2026-04-07 更新**：写入范围从“整 session”收窄为“当前 active conversation”；`/new` 后只清理当前 `conversation_id` 的消息，不再删除同一 `session_key` 下其他 conversation 历史
- **数据库路径**：`{workspace}/data/nanobot.db`

### 2.2 Load 拦截

- **原始行为**：从 JSONL 文件读取并反序列化 session
- **修改后行为**：从 SQLite 查询 session 数据，重建 `Session` 对象
- **消息还原**：从 `session_messages` 表按 `seq` 顺序还原消息列表
- **2026-04-07 更新**：只装载 `sessions.metadata["conversation_id"]` 对应的 active conversation，避免旧历史重新进入 live 上下文

### 2.3 List 拦截

- **原始行为**：扫描文件系统中的 session 文件
- **修改后行为**：查询 `sessions` 表，返回按更新时间倒序排列的 session 列表

---

## 3. 数据库 Schema

### sessions 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| key | TEXT UNIQUE | Session 标识符 |
| created_at | TEXT | 创建时间（ISO 格式） |
| updated_at | TEXT | 更新时间（ISO 格式） |
| metadata | TEXT | JSON 元数据 |
| last_consolidated | INTEGER | 最后整合位置 |
| last_completed | INTEGER | 最后完成轮次 |
| token_stats | TEXT | Token 统计（JSON） |

### session_messages 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| session_id | INTEGER FK | 关联 sessions.id |
| seq | INTEGER | 消息序号 |
| conversation_id | TEXT | 同一 session_key 下的逻辑会话分段 |
| role | TEXT | 消息角色 |
| content | TEXT | 消息内容 |
| tool_calls | TEXT | 工具调用（JSON） |
| tool_call_id | TEXT | 工具调用 ID |
| name | TEXT | 工具名称 |
| reasoning_content | TEXT | 推理内容 |
| timestamp | TEXT | 消息时间戳 |

---

## 4. 依赖关系

### 上游依赖
- `nanobot.session.manager.SessionManager` — 拦截目标（3 个方法）
- `nanobot.session.manager.Session` — 数据类
- `nanobot.config.paths.get_workspace_path` — 工作区路径

### Sidecar 内部依赖
- `ava.storage.Database` — SQLite 数据库封装类
- `ava.launcher.register_patch` — 自注册机制
- `ava.patches.loop_patch.set_shared_db` — 共享 Database 实例给 loop_patch

---

## 5. 关键实现细节

### 5.1 数据库初始化
- 数据库在 patch 应用时立即创建（`Database(db_path)`）
- 路径：`{workspace}/data/nanobot.db`
- Database 类负责建表和连接管理

### 5.2 Save 策略
- 使用 `INSERT OR REPLACE` 实现 upsert
- 先写 session 主记录，再按 active `conversation_id` 做 scoped rewrite / append
- 事务提交后更新内存缓存 `self._cache`
- `mem_count < db_count` 或首条消息时间戳不一致时，只删除当前 active conversation 的历史，不触碰其他 conversation

### 5.3 消息序列化
- `content` 字段：字符串直接存储，非字符串序列化为 JSON
- `tool_calls` 字段：列表序列化为 JSON
- `metadata` 和 `token_stats`：整体序列化为 JSON

### 5.4 Database 共享
- Patch 末尾调用 `loop_patch.set_shared_db(db)` 将 Database 实例共享给 loop_patch
- 共享失败时仅 warning（loop_patch 已有 fallback 机制自行创建 Database）
- 确保后续创建的 `AgentLoop` 实例获得同一个 Database 连接

### 5.5 token_usage 兼容升级
- `Database._create_schema()` 对 legacy `token_usage` 表采用“先 `ALTER TABLE` 补列，再创建新索引”的顺序
- `2026-04-05` 新增 `conversation_id TEXT DEFAULT ''` 与索引 `idx_tu_conv_turn(session_key, conversation_id, turn_seq)`，用于区分同一 `session_key` 下被 `/new` 切开的多段逻辑会话
- 该顺序不能反过来：若旧库尚未补出 `conversation_id`，提前创建索引会导致 SQLite 初始化直接报错

### 5.6 集成 Session Backfill
- `patched_load` 在从 SQLite 加载 session 后，直接调用 `ava.session.backfill_turns._backfill_messages()` 执行回填
- Backfill 逻辑从 `channel_patch` 移入 `storage_patch`，解决了两者对 `SessionManager._load` 的冲突
- Backfill 失败时仅 warning，不影响 session 返回

### 5.7 session_messages conversation 兼容升级
- `Database._create_schema()` 会为 legacy `session_messages` 表补 `conversation_id TEXT DEFAULT ''`
- 同步补索引 `idx_msg_session_conv_seq(session_id, conversation_id, seq)`，让 active conversation load / save 与 conversation 列表聚合都能按分段读取
- 对旧历史，空字符串 `conversation_id=''` 继续作为 legacy conversation 保留

---

## 6. 注意事项

- **数据迁移**：从 JSONL 迁移到 SQLite 需要单独的迁移脚本（不在本 patch 范围内）
- **并发安全**：SQLite 单写者模型，高并发写入场景需注意
- **内存缓存**：`self._cache` 仍由上游 `SessionManager` 管理，patch 在 save 时更新

---

## 7. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| Save 完整性 | Session 所有字段正确写入 SQLite |
| Load 完整性 | 从 SQLite 加载的 Session 与原始数据一致 |
| 消息序列化 | content/tool_calls 等字段的序列化和反序列化正确 |
| List 排序 | 返回结果按更新时间倒序 |
| 空数据库 | Load 不存在的 key 返回 None |
| Upsert | 同 key 多次 save 只保留最新版本 |
| conversation scoped rewrite | `/new` 后新 conversation 不删除旧 conversation 消息 |
| active-only load | `_load()` 只恢复 active conversation，不把旧 conversation 一起装回内存 |
| 缓存同步 | Save 后 `_cache` 正确更新 |
| db 共享 | `set_shared_db()` 成功调用 |
| db 共享失败 | `loop_patch` 不可用时仅 warning |
| 拦截点缺失 | `SessionManager` 缺少目标方法时优雅降级 |
