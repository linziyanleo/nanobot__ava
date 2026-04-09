---
specanchor:
  level: module
  module_name: "SQLite 存储 Patch"
  module_path: "ava/patches/storage_patch.py"
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
    - "ava/launcher.py"
    - "ava/storage/__init__.py"
    - "nanobot/session/manager.py"
    - "ava/storage/database.py"
    - "ava/session/backfill_turns.py"
---

# SQLite 存储 Patch (storage_patch)

## 1. 模块职责
- 将 nanobot 的 Session 持久化从 JSONL 文件替换为 SQLite，并把共享 `Database` 实例传给 loop_patch。
- 负责 save/load/list 三条核心链路的存储语义收口，以及 active conversation 级别的读写边界。
- 兼容旧库 schema 升级与 session backfill，但不承担整库迁移脚本职责。

## 2. 业务规则
- **原始行为**：将 session 序列化为 JSON 并追加到 JSONL 文件
- **修改后行为**：将 session 写入 SQLite 的 sessions 表和 session_messages 表
- **2026-04-07 更新**：写入范围从“整 session”收窄为“当前 active conversation”；/new 后只清理当前 conversation_id 的消息，不再删除同一 session_key 下其他 conversation 历史
- **数据库路径**：{workspace}/data/nanobot.db

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `apply_storage_patch()` | `apply_storage_patch() -> str` | Patch SessionManager to use SQLite instead of JSONL for session storage. |
| `Database` | `class` | Thread-safe SQLite database with WAL mode, schema management, and JSONL migration. |
| `Database.execute()` | `execute(sql: str, params: tuple = ()) -> sqlite3.Cursor` | 公共方法 |
| `backfill_workspace_sessions()` | `backfill_workspace_sessions(workspace: Path, dry_run: bool = False) -> dict[str, int]` | 公共函数 |
| `main()` | `main() -> int` | 公共函数 |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| _lock | instance | Database 运行时字段 |
| _SAFE_TOKEN_USAGE_COLUMNS | module | 模块级共享状态或常量 |
| _SAFE_POST_MIGRATION_SQL | module | 模块级共享状态或常量 |
| _SCHEMA_DDL | module | 模块级共享状态或常量 |
| PLACEHOLDER_TEXT | module | 模块级共享状态或常量 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.session.manager.SessionManager — 拦截目标（3 个方法）
- nanobot.session.manager.Session — 数据类
- nanobot.config.paths.get_workspace_path — 工作区路径
- ava.storage.Database — SQLite 数据库封装类

## 5. 已知约束 & 技术债
- [ ] 共享失败时仅 warning（loop_patch 已有 fallback 机制自行创建 Database）
- [ ] `SessionManager` 缺少目标方法时必须优雅降级，不能影响主流程启动。

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/storage_patch.py`
- **核心链路**: `storage_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/storage_patch.py` | 模块主入口 |
| `ava/storage/database.py` | 关联链路文件 |
| `ava/session/backfill_turns.py` | 关联链路文件 |
- **外部依赖**: `ava/launcher.py`、`ava/storage/__init__.py`、`nanobot/session/manager.py`、`ava/storage/database.py`、`ava/session/backfill_turns.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-storage_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
