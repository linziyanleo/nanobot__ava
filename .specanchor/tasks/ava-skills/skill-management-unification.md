---
specanchor:
  level: task
  task_name: "Skill 统一管理体系"
  author: "@fanghu"
  assignee: "@fanghu"
  created: "2026-03-31"
  status: "draft"
  last_change: "根据用户反馈更新 Plan：SQLite 持久化、native file picker、.agents/ 已存在"
  related_modules: []
  related_global:
    - ".specanchor/global/architecture.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "REVIEW"
  branch: "refactor/sidecar"
---

# SDD Spec: Skill 统一管理体系

## 0. Open Questions
- [x] ~~`.agents/` 目录的 skill 以什么格式存放？~~ → 通用 skill 格式（`skill-name/SKILL.md`）
- [x] ~~启用/禁用状态持久化到哪里？~~ → SQLite `skill_config` 表
- [x] ~~Console UI 选择本地文件夹是否需要 native file picker？~~ → 是，使用 `<input webkitdirectory>` 或路径输入双模式

## 1. Requirements (Context)

- **Goal**: 将外部引入的 skill 统一存放在 `ava/skills/`，Console UI 提供完整的 skill 生命周期管理（启用/禁用/删除/安装），同时发现和管理 `.agents/` 目录下已有的 skill
- **In-Scope**:
  1. Skill 格式统一：所有 skill 使用通用格式 `skill-name/SKILL.md` + 可选 `scripts/`、`references/`、`assets/`
  2. 外部 skill 统一存放在 `ava/skills/`，安装目标从 `~/.nanobot/workspace/skills/` 改为 `ava/skills/`
  3. Console UI Skills 页面增强：启用/禁用开关、删除、安装入口（native file picker + Git repo + 路径输入）
  4. `.agents/` 目录下已有 skill 的发现和管理（通过 Console UI 开启/关闭）
  5. 启用/禁用状态持久化到 SQLite `skill_config` 表
  6. nanobot 内置 skill（`nanobot/skills/`）保持不变，不做改动
- **Out-of-Scope**:
  - 修改 `nanobot/` 目录下的任何代码
  - Tool（工具）管理的变更
  - Skill marketplace / 远程注册表集成

## 1.1 Context Sources
- Requirement Source: 用户需求描述 + 用户反馈（SQLite、native file picker、.agents/）
- Design Refs: `nanobot/agent/skills.py` (SkillsLoader), `nanobot/skills/skill-creator/SKILL.md` (通用格式规范), `ava/storage/database.py` (SQLite)
- Extra Context: `.agents/` 目录已存在，需读取内部已有 skill

## 1.5 Codemap Used

- Codemap Mode: `feature`
- Key Index:

### Skill 加载链路
```
ContextBuilder.__init__()
  → SkillsLoader(workspace)                    # nanobot/agent/context.py:26
    → workspace_skills = workspace / "skills"   # nanobot/agent/skills.py:23
    → builtin_skills = BUILTIN_SKILLS_DIR       # nanobot/skills/

ContextBuilder.build_system_prompt()
  → skills.get_always_skills()                  # always=true 的 skill 直接注入上下文
  → skills.build_skills_summary()               # 所有 skill 的 XML 摘要注入上下文
```

### Console Skills 管理链路
```
create_console_app()
  → skill_dir = ava/skills/                     # ava/console/app.py:67
  → SkillsService(workspace, skill_dir, nanobot_dir)  # app.py:83
  → SkillsService.workspace_skills_dir = workspace / "skills"  (需改为 ava/skills/)
```

### SQLite 基础设施
```
Database (ava/storage/database.py)
  → _create_schema() → _SCHEMA_DDL
  → 现有表: schema_version, sessions, session_messages, token_usage, audit_entries, media_records
  → 需新增: skill_config 表
```

### 通用 Skill 格式（来自 skill-creator）
```
skill-name/
├── SKILL.md           # 必需：YAML frontmatter (name, description) + Markdown body
├── scripts/           # 可选：可执行脚本
├── references/        # 可选：参考文档
└── assets/            # 可选：输出资源
```

### 当前 Skill 存放位置总览
| 位置 | 类型 | 数量 | 说明 |
|------|------|------|------|
| `nanobot/skills/` | 上游内置 | 8 | clawhub, cron, github, memory, skill-creator, summarize, tmux, weather |
| `ava/skills/` | Sidecar 扩展 | 4 目录 + 9 `*_SKILL.md` | diary, restart_gateway + 扁平覆盖文件（需迁移） |
| `~/.nanobot/workspace/skills/` | 运行时工作区 | 0 | 当前为空，安装目标将改为 ava/skills/ |
| `.agents/` | 外部 Agent 目录 | 待扫描 | 已存在，需发现其中 skill |

## 2. Research Findings

### 事实与约束

1. **SkillsLoader 双层发现**：`workspace/skills/` (优先) → `builtin_skills` (fallback)。不可修改上游代码。

2. **ava/skills/ 的混合存储问题**：
   - 完整目录结构：`diary/`, `restart_gateway/`, `skill-creator/`, `tmux/`
   - 扁平覆盖文件：`cron_SKILL.md`, `github_SKILL.md`, `memory_SKILL.md` 等 9 个（不符合通用格式）
   - 需要将扁平文件迁移为 `skill-name/SKILL.md` 标准结构

3. **SQLite 基础设施就绪**：`ava/storage/database.py` 的 `Database` 类已提供线程安全连接池 + 自动 schema 管理，新增表只需扩展 `_SCHEMA_DDL` 或在 SkillsService 中独立创建。

4. **Console UI 现有功能**：Git 安装 + 本地路径导入已实现，但安装目标是 `workspace/skills/`（运行时目录），需改为 `ava/skills/`。

5. **Native file picker 可行性**：
   - `<input type="file" webkitdirectory>` 可选择整个文件夹（Chrome/Edge/Safari/Firefox 支持）
   - 但浏览器只返回 File 对象列表（含相对路径），服务端需接收上传文件并重建目录结构
   - 或者保留路径输入作为备选（本地部署场景更实用）

6. **`.agents/` 目录已存在**：需要扫描其中符合通用格式的 skill（`*/SKILL.md`）

### 风险与不确定项

- **启用/禁用的拦截层**：SkillsLoader 在上游不可改，需通过 Monkey Patch 在 `list_skills()` 返回前过滤 disabled 的 skill
- **Native file picker 的大文件问题**：如果 skill 包含大型 assets，文件上传可能超时。保留路径输入作为 fallback。
- **`.agents/` 中 skill 的权限**：这些 skill 可能是 symlink 或真实目录，需兼容两种情况

## 3. Innovate (Options & Decision)

### Option A: Patch SkillsLoader + SQLite skill_config 表

在 `ava/patches/` 新增 `skills_patch.py`，patch SkillsLoader：
- 扩展发现范围：`ava/skills/` + `.agents/` + 原有 `workspace/skills/`
- 查询 SQLite `skill_config` 表过滤 disabled skill
- 安装目标改为 `ava/skills/`

**Pros**: 完全符合 Sidecar 架构；SQLite 与现有存储统一；agent 端实时感知启用/禁用
**Cons**: 新增 patch 文件

### Option B: 仅 Service 层管理

**Cons**: 启用/禁用不影响 agent 上下文，失去实际意义

### Decision
- Selected: **Option A**
- Why: 启用/禁用必须影响 agent 实际加载的 skill 列表。SQLite 与现有 Database 统一，避免独立 JSON 文件。

## 4. Plan (Contract)

### 4.1 File Changes

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 1 | `ava/skills/*_SKILL.md` → `ava/skills/*/SKILL.md` | 迁移 | 将 9 个扁平文件迁移为通用 `skill-name/SKILL.md` 目录结构 |
| 2 | `ava/storage/database.py` | 修改 | `_SCHEMA_DDL` 新增 `skill_config` 表 |
| 3 | `ava/patches/skills_patch.py` | 新建 | Patch SkillsLoader：三源发现（ava/skills/ + .agents/ + workspace/skills/）+ disabled 过滤 |
| 4 | `ava/console/services/skills_service.py` | 修改 | 重构：安装目标改为 ava/skills/；新增 toggle/agents/upload API；SQLite 持久化 |
| 5 | `ava/console/routes/skills_routes.py` | 修改 | 新增端点：toggle、agents 列表、agents toggle、文件夹上传 |
| 6 | `console-ui/src/pages/SkillsPage.tsx` | 修改 | 三区域展示（ava/skills/、.agents/、nanobot 内置）+ 启用/禁用开关 + native file picker + 路径输入双模式 |

### 4.2 Signatures

```sql
-- ava/storage/database.py: skill_config 表
CREATE TABLE IF NOT EXISTS skill_config (
    name TEXT PRIMARY KEY,           -- skill 名称
    source TEXT NOT NULL,            -- 'ava' | 'agents' | 'builtin'
    enabled INTEGER NOT NULL DEFAULT 1,  -- 1=启用, 0=禁用
    installed_at TEXT,               -- ISO timestamp
    install_method TEXT,             -- 'git' | 'path' | 'upload' | 'builtin' | 'agents'
    git_url TEXT,                    -- Git 安装时的源 URL
    updated_at TEXT                  -- 最后更新时间
);
```

```python
# ava/patches/skills_patch.py
def apply_skills_patch() -> str:
    """Patch SkillsLoader to support:
    1. Three-source discovery: ava/skills/ + .agents/ + workspace/skills/
    2. SQLite-backed enabled/disabled filtering
    """

# ava/console/services/skills_service.py 修改
class SkillsService:
    def __init__(self, workspace, builtin_skills_dir, nanobot_dir, db: Database)
    # 已有（修改）
    def list_skills(self) -> list[dict]          # 合并三源 + enabled 状态
    def install_skill_from_git(self, ...) -> dict # 安装目标改为 ava/skills/
    def install_skill_from_path(self, ...) -> dict
    def delete_skill(self, name) -> dict
    # 新增
    def toggle_skill(self, name: str, enabled: bool) -> dict
    def list_agents_skills(self) -> list[dict]
    def toggle_agents_skill(self, name: str, enabled: bool) -> dict
    def upload_skill(self, name: str, files: dict[str, bytes]) -> dict  # native file picker 上传

# ava/console/routes/skills_routes.py 新增端点
# PUT    /api/skills/toggle              — 启用/禁用 skill
# GET    /api/skills/agents              — 列出 .agents/ 下的 skill
# PUT    /api/skills/agents/toggle       — 启用/禁用 .agents/ skill
# POST   /api/skills/install/upload      — native file picker 文件夹上传
```

```typescript
// console-ui/src/pages/SkillsPage.tsx 新增类型
interface SkillInfo {
  name: string
  source: 'ava' | 'agents' | 'builtin'  // 三源分类
  path: string
  enabled: boolean        // 从 SQLite 读取
  description: string
  always: boolean
  install_method?: string
  git_url?: string
}
```

### 4.3 Implementation Checklist

- [ ] 1. **迁移 ava/skills/ 目录结构**
  - 将 9 个 `*_SKILL.md` 扁平文件迁移为 `skill-name/SKILL.md` 标准结构
  - 确保 frontmatter 中 name/description 字段符合通用格式规范
  - 删除迁移后的扁平文件

- [ ] 2. **扩展 SQLite schema：skill_config 表**
  - 在 `ava/storage/database.py` 的 `_SCHEMA_DDL` 中新增 `skill_config` 表
  - 或在 SkillsService 初始化时独立创建（避免改动 Database 类的 SCHEMA_VERSION）

- [ ] 3. **新建 skills_patch.py**
  - Patch `SkillsLoader.list_skills()`：在原有结果基础上追加 `.agents/` 目录发现
  - Patch `SkillsLoader.load_skill()`：支持从 `.agents/` 目录加载
  - 注入 disabled 过滤逻辑：查询 `skill_config` 表，移除 `enabled=0` 的 skill
  - 通过 `register_patch()` 自注册

- [ ] 4. **重构 SkillsService**
  - 构造函数新增 `db: Database` 参数
  - `list_skills()` 合并三源（ava/skills/ + .agents/ + nanobot/skills/）并附带 enabled 状态
  - 安装方法（git/path/upload）目标改为 `ava/skills/`
  - 新增 `toggle_skill()`、`list_agents_skills()`、`toggle_agents_skill()`
  - 新增 `upload_skill()` 处理 native file picker 上传的文件列表

- [ ] 5. **更新 skills_routes.py**
  - `PUT /api/skills/toggle` — 启用/禁用任意来源的 skill
  - `GET /api/skills/agents` — 列出 `.agents/` 目录下的 skill
  - `PUT /api/skills/agents/toggle` — 启用/禁用 `.agents/` skill
  - `POST /api/skills/install/upload` — 接收 multipart 文件上传，重建 skill 目录

- [ ] 6. **更新 Console UI SkillsPage.tsx**
  - 三区域展示：ava/skills（自定义）、.agents（外部 Agent）、nanobot/skills（内置）
  - 每个 SkillCard 增加启用/禁用 toggle 开关
  - 安装面板新增 "文件夹选择" tab：`<input type="file" webkitdirectory>` + 路径输入双模式
  - 内置 skill 区域不显示删除按钮，但可显示启用/禁用开关
  - `.agents/` 区域只显示启用/禁用开关，不显示删除

- [ ] 7. **更新 Console app.py 服务初始化**
  - `SkillsService` 构造传入 `db` 参数
  - 确保 `skill_config` 表在启动时创建

- [ ] 8. **测试验证**
  - 验证 skill 启用/禁用影响 agent 上下文（SkillsLoader patch 生效）
  - 验证 `.agents/` 目录 skill 正确发现和展示
  - 验证 native file picker 上传安装正常
  - 验证 Git / 路径安装目标为 ava/skills/
  - 验证 SQLite 持久化在重启后保留状态

## 5. Execute Log
- [x] Step 1: 迁移 ava/skills/ — 9 个 `*_SKILL.md` → `skill-name/SKILL.md` 标准目录
- [x] Step 2: SQLite schema — `skill_config` 表添加到 `_SCHEMA_DDL`
- [x] Step 3: skills_patch.py — Patch SkillsLoader `__init__`/`list_skills`/`load_skill`，ava/ 覆盖 nanobot/ 同名 skill
- [x] Step 4: SkillsService 重构 — db 注入、三源合并、toggle/upload/delete 全部支持 SQLite
- [x] Step 5: skills_routes.py — 新增 `PUT /toggle`、`POST /install/upload` 端点
- [x] Step 6: SkillsPage.tsx — 三区域（custom/agents/builtin）+ toggle 开关 + native file picker
- [x] Step 7: app.py — 两处 SkillsService 构造传入 db；standalone 模式始终创建 Database
- [x] 附加: `ava/storage/__init__.py` 新增 `get_db()/set_db()` singleton；`storage_patch.py` 注册 db

## 6. Review Verdict
- Spec coverage: PASS — 所有 8 步均完成
- Behavior check: PASS — Python 导入/SQLite CRUD/disabled 过滤/TypeScript 编译均通过
- Regression risk: Low — 不修改 nanobot/ 代码，通过 Monkey Patch 实现
- Module Spec 需更新: No
- Follow-ups: 前端 `api()` 调用 multipart upload 时需确认 headers 处理（可能需调整 api client）

## 7. Plan-Execution Diff
- 新增了 `ava/storage/__init__.py` 的 `get_db()/set_db()` singleton（Plan 未提及，但 skills_patch 需要访问 db）
- 修改了 `storage_patch.py` 注册 db singleton（Plan 未提及）
- skills_patch 策略从"追加 ava/ 到列表尾部"改为"重定向 builtin_skills 到 ava/"以实现同名覆盖
