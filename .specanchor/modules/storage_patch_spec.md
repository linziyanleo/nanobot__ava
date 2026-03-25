# Module Spec: storage_patch — SQLite 存储层替换

> 文件：`cafeext/patches/storage_patch.py`
> 状态：✅ 已实现（Phase 1）

---

## 1. 模块职责

将 nanobot 的 Session 持久化从 JSONL 文件存储替换为 SQLite 数据库存储，提供更好的查询能力、并发安全和数据完整性。

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
- **数据库路径**：`{workspace}/data/nanobot.db`

### 2.2 Load 拦截

- **原始行为**：从 JSONL 文件读取并反序列化 session
- **修改后行为**：从 SQLite 查询 session 数据，重建 `Session` 对象
- **消息还原**：从 `session_messages` 表按 `seq` 顺序还原消息列表

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
- `cafeext.storage.Database` — SQLite 数据库封装类
- `cafeext.launcher.register_patch` — 自注册机制

---

## 5. 关键实现细节

### 5.1 数据库初始化
- 数据库在 patch 应用时立即创建（`Database(db_path)`）
- 路径：`{workspace}/data/nanobot.db`
- Database 类负责建表和连接管理

### 5.2 Save 策略
- 使用 `INSERT OR REPLACE` 实现 upsert
- 先写 session 主记录，再删除旧消息，最后批量插入新消息
- 事务提交后更新内存缓存 `self._cache`

### 5.3 消息序列化
- `content` 字段：字符串直接存储，非字符串序列化为 JSON
- `tool_calls` 字段：列表序列化为 JSON
- `metadata` 和 `token_stats`：整体序列化为 JSON

### 5.4 与 channel_patch 的交互
- `storage_patch` 替换 `SessionManager._load` → `channel_patch` 再次替换 `SessionManager._load`
- 最终效果：从 SQLite 加载 → 执行 backfill → 返回
- **执行顺序依赖**：`storage_patch` 必须先于 `channel_patch` 执行

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
| 缓存同步 | Save 后 `_cache` 正确更新 |
| 拦截点缺失 | `SessionManager` 缺少目标方法时优雅降级 |
