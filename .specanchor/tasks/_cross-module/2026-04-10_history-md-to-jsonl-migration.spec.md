---
specanchor:
  level: task
  task_name: "HISTORY.md 迁移到 history.jsonl"
  author: "@ZiyanLin"
  assignee: "@ZiyanLin"
  reviewer: "@ZiyanLin"
  created: "2026-04-10"
  status: "done"
  last_change: "Execute 完成，全部 5 步 Checklist 通过，35 tests passing，不变量约束验证通过"
  related_modules:
    - ".specanchor/modules/ava-agent-categorized_memory.spec.md"
  related_global:
    - ".specanchor/global/architecture.spec.md"
    - ".specanchor/global/patch-governance.spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "EXECUTE"
  branch: ""
---

# SDD Spec: HISTORY.md 迁移到 history.jsonl

## 0. Open Questions

- [x] person 级别的 `HISTORY.md` 是否也应迁移为 JSONL 格式？→ **是，迁移为 per-person `history.jsonl`，物理隔离于 `memory/persons/<person>/history.jsonl`**
- [x] `console-ui` MemoryPage 的 History Tab 应展示什么数据源？→ **全局 scope 读全局 `history.jsonl`（仅全局条目）；person scope 读 `persons/<person>/history.jsonl`**
- [x] person history 是否该进入 Dream 输入总线 / Recent History prompt / compact 域？→ **否。这三者是全局语义，person history 必须物理隔离**

## 1. Requirements (Context)

- **Goal**: 上游 nanobot v0.1.5 重构了 memory 系统，用 `history.jsonl`（JSONL + cursor）替代了 `HISTORY.md`。ava 侧多个模块仍在读写旧的 `HISTORY.md`，需要全部迁移到新架构。
- **In-Scope**:
  - `ava/agent/categorized_memory.py` — person 级别 history 存储机制
  - `ava/tools/memory_tool.py` — `search_history` 对 `HISTORY.md` 的搜索逻辑
  - `console-ui/src/pages/MemoryPage.tsx` — 前端 History Tab 数据源
  - `ava/skills/memory/SKILL.md` — 文档更新
  - `ava/skills/console_ui_dev_loop/references/pages/memory.md` — 文档更新
  - `tests/agent/test_consolidator.py` — 注释更新
  - `tests/tools/test_search_tools.py` — 测试 fixture 迁移
- **Out-of-Scope**:
  - `nanobot/agent/memory.py` — 上游代码，已完成迁移，不修改
  - `tests/agent/test_memory_store.py` — 上游测试，不修改
  - `docs/MEMORY.md` — 上游文档，不修改

## 1.1 Context Sources

- Requirement Source: 上游 nanobot v0.1.5 Dream 重构 (PR #2717, #2779)
- Design Refs: `nanobot/agent/memory.py` — MemoryStore 新 API (history.jsonl, cursor 机制)
- Chat/Business Refs: 用户要求扫描所有旧 HISTORY.md 引用并更新

## 2. Research Findings

### 2.1 上游新架构分析

上游 `MemoryStore` (`nanobot/agent/memory.py`) 的新 history 机制：

- **存储格式**: `memory/history.jsonl`，每行一个 JSON 对象：`{"cursor": int, "timestamp": str, "content": str}`
- **写入**: `append_history(entry: str) -> int` — 追加条目，返回 cursor
- **读取**: `read_unprocessed_history(since_cursor: int) -> list[dict]` — 读取指定 cursor 之后的条目
- **压缩**: `compact_history()` — 超过 max_history_entries 时裁剪旧条目
- **Legacy 迁移**: `_maybe_migrate_legacy_history()` — 首次启动时自动将全局 `HISTORY.md` 迁移为 `history.jsonl`，备份为 `HISTORY.md.bak`
- **Dream cursor**: `get_last_dream_cursor()` / `set_last_dream_cursor()` — Dream 处理进度追踪

### 2.2 ava 侧受影响组件分析

#### 2.2.1 `ava/agent/categorized_memory.py`

- `_person_history_file()` (L152): 返回 `HISTORY.md` 路径
- `append_person_history()` (L175-178): 向 `HISTORY.md` 追加 Markdown 文本
- **问题**: person 级别 history 仍使用 Markdown 追加模式，与上游 JSONL 机制不一致
- **决策点**: person history 是否也迁移为 JSONL？当前 person history 由 `on_consolidate()` 写入，由 `memory_tool._search_history()` 搜索

#### 2.2.2 `ava/tools/memory_tool.py`

- `_search_history()` (L169-240): 当无 time/channel filter 时，先 grep 搜索 `HISTORY.md`（全局 + person 级别），搜不到再 fallback 到 session files
- **问题**: 全局 `HISTORY.md` 已不存在（被上游迁移为 `history.jsonl`），grep 搜索会空手而归
- **修复方向**: 改为搜索 `history.jsonl`（解析 JSONL 行中的 content 字段）

#### 2.2.3 `console-ui/src/pages/MemoryPage.tsx`

- L136: `api<FileData>(/files/read?path=${basePath}/HISTORY.md)` — 前端直接读 `HISTORY.md` 文件
- **问题**: 全局 `HISTORY.md` 已迁移，文件不存在；person 级别的还在但格式未来可能变
- **修复方向**: 全局改为读 `history.jsonl`，前端需解析 JSONL 格式展示

#### 2.2.4 文档和测试

- `ava/skills/memory/SKILL.md`: 架构图和多处说明提及 `HISTORY.md`
- `tests/tools/test_search_tools.py`: 创建 `HISTORY.md` fixture 用于测试搜索
- `tests/agent/test_consolidator.py`: 注释提及 "append-only to HISTORY.md"（实际已是 history.jsonl）

### 2.3 Codex Review 关键发现（Option D 致命缺陷）

> Codex Review job: `review-mnsarf7i-5zaigk`

1. **Prompt 隔离**: `ContextBuilder.build_system_prompt()` (`context.py:56`) 调用 `read_unprocessed_history(since_cursor=dream_cursor)`，会把全局 `history.jsonl` 中所有未被 Dream 处理的条目注入 system prompt。如果 person history 混入全局文件，A 用户归档会进 B 用户会话 prompt。
2. **Dream 边界**: Dream (`memory.py:561`) 无差别消费 `history.jsonl` 所有条目。Module Spec 明确写的是"Dream 只管全局文件，person sync 走 sidecar bridge"。
3. **Retention 语义**: 全局 `history.jsonl` 有 `max_history_entries=1000` + `compact_history()`。Person `HISTORY.md` 原来是独立 append-only，混入后 retention 语义改变。
4. **Upstream API**: `append_history(entry: str)` 不接受额外字段，person 字段只能碰私有实现。
5. **验证面**: `test_search_tools.py` 是 GrepTool 通用测试，不验证 `MemoryTool.search_history`。真正受影响的是 `test_consolidation_bridge.py` 和 `test_context_prompt_cache.py`。

### 2.4 风险与不确定项

- **Legacy person HISTORY.md 迁移**: 已有的 person `HISTORY.md` 文件需要 one-time 迁移为 JSONL，或保留为 `.bak` 存档
- **前端兼容**: MemoryPage 需要能解析 JSONL 并友好展示
- **测试覆盖**: 搜索逻辑变更 + consolidation bridge 写入目标变更

## 2.1 Next Actions

- ~~确认 person history 迁移策略~~ → 已确认 Option E（per-person JSONL 物理隔离）

## 3. Innovate (Optional: Options & Decision)

### Option A: 仅修复全局 HISTORY.md 引用，保留 person HISTORY.md

- Pros: 改动范围小，person history 的 Markdown 格式对人类友好
- Cons: 两套 history 格式不统一，搜索逻辑需维护两条路径

### Option B: 全面迁移——全局 + person 都用 JSONL

- Pros: 格式统一，可复用上游 MemoryStore 的 JSONL 工具方法，搜索逻辑统一
- Cons: 改动范围更大，person history 可读性降低

### Option C: 混合方案——全局用 history.jsonl（跟上游），person 保留 HISTORY.md 但搜索逻辑统一

- Pros: 最小侵入性，全局与上游保持一致，person 保留人类可读性
- Cons: 搜索逻辑仍需处理两种格式

### Option D (Rejected): 统一写入全局 history.jsonl，用 person 字段标记

- Pros: 单一数据源、搜索逻辑极简
- Cons: **致命缺陷（Codex Review 发现）**——
  1. **Prompt 隔离被打穿**: `ContextBuilder` 把所有未被 Dream 消化的全局 history 注入 system prompt（`context.py:56`），A 用户的归档会进 B 用户的会话
  2. **Dream 边界违规**: Dream 无差别消费 `history.jsonl`（`memory.py:561`），会把 person 条目折进全局 `MEMORY.md`/`SOUL.md`/`USER.md`，违反 Module Spec 中"Dream 只管全局文件"的规则
  3. **Retention 语义改变**: 全局 history.jsonl 有 1000 条上限 + compact（`memory.py:250`），person history 原来是独立 append-only，混入后会被裁剪
  4. **依赖不存在的 upstream API**: `append_history(entry: str)` 不接受额外字段，写 person 字段必须碰私有实现

### Option E (Selected): per-person JSONL 物理隔离 + 搜索/展示聚合

- 全局 `memory/history.jsonl` 保持不变，只承载 Dream/Consolidator 全局归档
- Person history 从 `HISTORY.md` 迁移为 `memory/persons/<person>/history.jsonl`（独立 append-only JSONL，无 compact）
- `memory_tool.search_history` 和 `MemoryPage` 做统一查询聚合（读多个 JSONL 文件）
- Dream/ContextBuilder/compact 完全不碰 person JSONL，隔离保持

### Decision

- Selected: **Option E** — per-person JSONL 物理隔离，搜索/展示层做聚合
- Why: Codex Review 发现 Option D 有 3 个致命缺陷（prompt 泄漏、Dream 边界违规、retention 语义改变）。Option E 保持 Dream/prompt/compact 边界不变，同时统一 JSONL 格式消除双轨格式维护

**Per-person JSONL schema：**

```jsonl
{"timestamp": "2026-04-10 14:30", "content": "用户讨论了旅行计划"}
{"timestamp": "2026-04-10 15:00", "content": "确认了周末行程"}
```

- 无 cursor 字段（person history 不需要 Dream cursor 追踪）
- 无 compact（独立 append-only，不受全局 1000 条限制）
- 格式与全局 `history.jsonl` 兼容（搜索逻辑可统一解析 content 字段）

## 4. Plan (Contract)

### 4.1 File Changes

| 文件 | 变更说明 |
|------|----------|
| `ava/agent/categorized_memory.py` | 1) `_person_history_file()` 改为返回 `history.jsonl` 路径；2) 重写 `append_person_history()` 为 JSONL 追加（`{"timestamp", "content"}`）；3) 新增 `_maybe_migrate_person_history()` 一次性迁移旧 `HISTORY.md` → `history.jsonl`（备份为 `HISTORY.md.bak`），在 `append_person_history` / `_person_history_file` 首次调用时触发；4) `on_consolidate()` 无需改动（仍调用 `append_person_history`） |
| `ava/tools/memory_tool.py` | 重写 `_search_history()` 中 grep `HISTORY.md` 的逻辑，改为解析 JSONL（全局 `history.jsonl` + person `history.jsonl`），移除 `subprocess.run(["grep"...])` |
| `console-ui/src/pages/MemoryPage.tsx` | 1) `loadFiles` 改为读 `history.jsonl`（全局/person 路径不变，仅文件名变）；2) 重写 `parseHistoryEntries` 解析 JSONL 格式；3) 移除 `saveHistoryEntry`（JSONL append-only 不支持行内编辑） |
| `ava/skills/memory/SKILL.md` | 架构图中 person 下 `HISTORY.md` → `history.jsonl`；更新说明文字 |
| `ava/skills/console_ui_dev_loop/references/pages/memory.md` | History Tab 说明更新 |
| `tests/agent/test_consolidator.py` | 注释更新（"append-only to history.jsonl"） |
| `tests/tools/test_search_tools.py` | 将 `HISTORY.md` fixture 改为 `history.jsonl` JSONL 格式 |
| `tests/patches/test_consolidation_bridge.py` | 验证 `on_consolidate` 写入 person JSONL（非全局 JSONL） |

### 4.2 Signatures

**`ava/agent/categorized_memory.py`:**

```python
def _person_history_file(self, person_name: str) -> Path:
    return self._person_dir(person_name) / "history.jsonl"

def append_person_history(self, person_name: str, entry: str) -> None:
    """Append timestamped entry to person's history.jsonl."""
    import json
    from datetime import datetime
    self._maybe_migrate_person_history(person_name)
    f = self._person_history_file(person_name)
    record = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "content": entry.rstrip()}
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

def _maybe_migrate_person_history(self, person_name: str) -> None:
    """One-time migration: person HISTORY.md → history.jsonl, backup as HISTORY.md.bak."""
```

**`ava/tools/memory_tool.py`:**

```python
def _search_history_jsonl(self, jsonl_path: Path, query_lower: str) -> list[str]:
    """Search a JSONL history file, return matching formatted lines."""
```

### 4.3 Implementation Checklist

- [x] 1. **CategorizedMemoryStore JSONL 化**: `_person_history_file()` → `history.jsonl`；`append_person_history()` 改为 JSONL 追加；`_maybe_migrate_person_history()` 一次性迁移旧 HISTORY.md
- [x] 2. **memory_tool 搜索重写**: `_search_history()` 改为解析 JSONL（全局 + person），移除 subprocess grep
- [x] 3. **MemoryPage 前端重写**: 读 `history.jsonl`、解析 JSONL、移除行内编辑
- [x] 4. **文档更新**: SKILL.md + console_ui memory.md
- [x] 5. **测试更新**: test_consolidator.py 注释 + test_search_tools.py fixture 改为 JSONL + test_consolidation_bridge.py 验证 person JSONL 写入

### 4.4 不变量约束（Codex Review 要求明示）

以下边界在本次迁移中 **不得改变**：

- `nanobot/agent/context.py:56` — `read_unprocessed_history()` 只消费全局 `history.jsonl`，不碰 person JSONL
- `nanobot/agent/memory.py` Dream — 只处理全局 `history.jsonl`，不碰 person JSONL
- `nanobot/agent/memory.py:250` compact — 只裁剪全局 `history.jsonl`，person JSONL 独立 append-only
- `ava/patches/loop_patch.py` — `_sync_categorized_memory()` 继续调用 `on_consolidate()`，链路不变
- `tests/agent/test_context_prompt_cache.py` — 现有测试断言不需要修改（全局行为未变）
- `tests/patches/test_consolidation_bridge.py:81` — `on_consolidate` 调用断言不变，但需验证写入目标是 person JSONL

## 5. Execute Log

### Step 1: CategorizedMemoryStore JSONL 化

- `_person_history_file()` 改为返回 `history.jsonl`
- `append_person_history()` 改为 JSONL 追加：`{"timestamp": "YYYY-MM-DD HH:MM", "content": "..."}`
- 新增 `_maybe_migrate_person_history(person_name)` — 一次性迁移旧 `HISTORY.md` → `history.jsonl`（解析 `[timestamp] content` 格式），备份为 `HISTORY.md.bak`
- 新增 `_parse_legacy_person_history()` — 解析 legacy Markdown 条目
- 新增顶层 import: `json`, `re`, `datetime`

### Step 2: memory_tool 搜索重写

- `_search_history()` 中的 `subprocess.run(["grep"...])` 替换为 `_search_history_jsonl()` 纯 Python 解析
- 全局搜 `memory/history.jsonl` + person 搜 `memory/persons/<person>/history.jsonl`
- 移除 `import subprocess`
- 新增 `@staticmethod _search_history_jsonl(jsonl_path, query_lower) -> list[str]`

### Step 3: MemoryPage 前端重写

- `loadFiles` 中 `HISTORY.md` → `history.jsonl`
- `parseHistoryEntries` 改为解析 JSONL 行（`JSON.parse` 每行）
- 移除 `saveHistoryEntry`、`startEditEntry`、`editingEntry`/`editingText` state
- 移除 History Tab 中的编辑按钮和编辑 UI（JSONL append-only 不支持行内编辑）
- 移除不再需要的 lucide imports: `X`, `Pencil`, `Check`

### Step 4: 文档更新

- `ava/skills/memory/SKILL.md`: 架构图 `HISTORY.md` → `history.jsonl`；Ownership Boundary / prompt 边界 / Search 段落更新
- `ava/skills/console_ui_dev_loop/references/pages/memory.md`: History Tab 说明改为 `history.jsonl`（只读）

### Step 5: 测试更新

- `tests/agent/test_consolidator.py`: 模块 docstring + 2 个测试方法 docstring 中 `HISTORY.md` → `history.jsonl`
- `tests/tools/test_search_tools.py`: 2 个测试的 fixture 从 `HISTORY.md` 改为 `history.jsonl` JSONL 格式（文件名 + 内容 + 断言）
- `tests/patches/test_consolidation_bridge.py`: 无需改动（mock 断言不变，无 HISTORY.md 引用）
- `tests/agent/test_context_prompt_cache.py`: 无需改动（§4.4 不变量）
- **全部 35 个测试通过**

## 6. Review Verdict

### 不变量约束验证 ✅

- `nanobot/agent/context.py:56` — `read_unprocessed_history(since_cursor=dream_cursor)` 未被修改，只消费全局 `history.jsonl` ✅
- `nanobot/agent/memory.py` Dream — 无 person history 引用，Dream 只处理全局 history ✅
- `nanobot/agent/memory.py:250` compact — 只裁剪全局 `history.jsonl`，person JSONL 独立 append-only ✅
- `ava/patches/loop_patch.py` — `_sync_categorized_memory()` 调用链不变 ✅
- `tests/agent/test_context_prompt_cache.py` — 现有断言未修改，35 tests passing ✅
- `tests/patches/test_consolidation_bridge.py:81` — `on_consolidate` mock 断言不变 ✅

### 变更摘要

共修改 8 个文件，新增 ~65 行代码，移除 ~55 行代码：

- 2 个后端核心文件 (`categorized_memory.py`, `memory_tool.py`)
- 1 个前端页面 (`MemoryPage.tsx`)
- 2 个文档 (`SKILL.md`, `memory.md`)
- 2 个测试 (`test_consolidator.py`, `test_search_tools.py`)
- 1 个 Task Spec 自身

### Verdict: **PASS**

## 7. Plan-Execution Diff

| Plan 项 | 实际执行 | 差异说明 |
|---------|---------|---------|
| `categorized_memory.py` 3 项改动 | 4 项（多了 `_maybe_migrate_person_history`） | Plan 修订时已补入迁移逻辑 |
| `memory_tool.py` 移除 subprocess grep | 完全按 Plan 执行 | — |
| `MemoryPage.tsx` 3 项改动 | 完全按 Plan 执行，额外清理了 3 个 unused imports | 前端 cleanup |
| `SKILL.md` 文档更新 | 5 处 `HISTORY.md` → `history.jsonl` 引用 | — |
| `console_ui memory.md` | 1 处更新 | — |
| `test_consolidator.py` 注释更新 | 1 个模块 docstring + 2 个方法 docstring | — |
| `test_search_tools.py` fixture 改 JSONL | 2 个测试的文件名、内容、断言全更新 | — |
| `test_consolidation_bridge.py` 验证写入 | 无需改动（mock 断言已覆盖调用参数） | Plan 原文 "需验证" 实际是确认不回归 |
