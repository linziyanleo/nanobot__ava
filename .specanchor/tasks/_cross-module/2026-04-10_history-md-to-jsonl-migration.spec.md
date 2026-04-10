---
specanchor:
  level: task
  task_name: "HISTORY.md 迁移到 history.jsonl"
  author: "@ZiyanLin"
  assignee: "@ZiyanLin"
  reviewer: "@ZiyanLin"
  created: "2026-04-10"
  status: "draft"
  last_change: "初始创建 Task Spec"
  related_modules:
    - ".specanchor/modules/ava-agent-categorized_memory.spec.md"
  related_global:
    - ".specanchor/global/architecture.spec.md"
    - ".specanchor/global/patch-governance.spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "RESEARCH"
  branch: ""
---

# SDD Spec: HISTORY.md 迁移到 history.jsonl

## 0. Open Questions
- [ ] person 级别的 `HISTORY.md` 是否也应迁移为 JSONL 格式，还是保持 Markdown 追加模式？
- [ ] `console-ui` MemoryPage 的 History Tab 应展示什么数据源（history.jsonl 或 session 搜索）？

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

### 2.3 风险与不确定项
- **Person history 格式决策**: 将 person `HISTORY.md` 也迁移为 JSONL 会增加改动范围，但保持与全局一致性更好
- **前端兼容**: MemoryPage 需要能解析 JSONL 并友好展示
- **测试覆盖**: 搜索逻辑变更需要配套测试更新

## 2.1 Next Actions
- 确认 person history 迁移策略（保持 Markdown vs 迁移到 JSONL）后进入 Plan 阶段

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

### Decision
- Selected: 待用户确认
- Why: —

## 4. Plan (Contract)

*(待 Research + Innovate 确认后填充)*

### 4.1 File Changes

### 4.2 Signatures

### 4.3 Implementation Checklist
- [ ] 1. ...

## 5. Execute Log

## 6. Review Verdict

## 7. Plan-Execution Diff
