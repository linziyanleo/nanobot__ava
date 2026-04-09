---
specanchor:
  level: task
  task_name: "post-merge follow-up：Dream 同步通道、shadow skills 治理与 Batch C 复核"
  author: "@Codex"
  assignee: "@Codex"
  reviewer: "@Ziyan Lin"
  created: "2026-04-08"
  updated: "2026-04-09"
  status: "done"
  last_change: "v4：选定 A0=(a)+(d)；落地 Consolidator→categorized_memory bridge 与 USER.md/MEMORY/Personal Memory 去重；收窄/删除 shadow skills；补 provider_prefix 弃用标记并完成 Dream/skills/Batch C 定向验证"
  related_modules:
    - ".specanchor/modules/ava-agent-categorized_memory.spec.md"
    - ".specanchor/modules/ava-patches-context_patch.spec.md"
    - ".specanchor/modules/ava-patches-loop_patch.spec.md"
    - ".specanchor/modules/ava-patches-skills_patch.spec.md"
    - ".specanchor/modules/ava-patches-tools_patch.spec.md"
    - ".specanchor/modules/ava-patches-channel_patch.spec.md"
    - ".specanchor/modules/ava-patches-provider_prefix_patch.spec.md"
    - ".specanchor/modules/ava-patches-transcription_patch.spec.md"
  related_global:
    - ".specanchor/global/architecture.md"
    - ".specanchor/global-patch-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "EXECUTE"
  branch: "codex/upstream-v0.1.5-merge-analysis"
---

# SDD Spec: post-merge follow-up：Dream 同步通道、shadow skills 治理与 Batch C 复核

## 0. Open Questions

- [x] 这三项 follow-up 是拆成 3 份 spec，还是先收在一份 cross-module spec
  - 结论：收在一份 cross-module spec。Batch C 与 delete 类 skills 可并行，memory skill 重写须等 Dream 同步完成
- [x] Dream 真源统一默认以哪一侧为基准
  - 结论：**不做主从重定义**。Dream 和 categorized_memory 是两个正交维度（全局 vs 个人），不是竞争真源。真正的问题是两者之间缺少同步通道。方案改为"补同步 hook"而非"重建三层存储"
- [x] shadow skills 的默认处理规则是什么
  - 结论：同内容直接删除；仅保留 sidecar 增量的做收窄；语义已实质分叉的继续保留，但必须重新写清与 upstream 的边界
- [x] `memory` skill / `memory` tool 在 Dream 同步后是否继续保留现有 person/source 双作用面
  - 结论：**保留**。理由：person/source 维度和 Dream 的全局维度正交，不存在语义冲突。MemoryTool 的 recall/remember/map_identity/search_history 都是面向个人维度的操作，Dream 不提供这些能力。只需在 SKILL.md 中明确"Dream 管全局，memory tool 管个人"的边界
- [x] person attribution 信息从哪里来（v3 新增，由 Codex review 触发）
  - 结论：**当前 history.jsonl 不携带 channel/chat_id**（仅 `{cursor, timestamp, content}`）。`Consolidator.archive()` 签名也不接收会话参数。Dream cron 入口（`commands.py:701` `agent.dream.run()`）完全没有会话级上下文。因此 A1/A2 不能按 v2 描述直接落地，必须先在 A0 前置 gate 中定义 person attribution contract 并选定实现路径

## 1. Requirements (Context)

- **Goal**: 在已完成 `upstream/main` merge 且运行闭环已验证通过的基础上，推进三项 post-merge 收口工作：1）为 Dream/Consolidator 与 categorized_memory 之间补建同步通道；2）治理 shadow skills；3）复核 Batch C 增益区。确保 sidecar patch / tools / skills 仍能正常运行。
- **In-Scope**:
  - **Dream 同步通道**（带前置 gate）：
    - **A0 前置 gate**：定义 person attribution contract——确定 channel/chat_id 信息如何在归档/梦境路径中被保留或重建，输出明确的技术方案后才进入 A1-A3
    - A1：在 Consolidator 归档路径中桥接 `on_consolidate()`（方案取决于 A0 结论）
    - A2：在 Dream 后处理路径中桥接 `on_consolidate()`（方案取决于 A0 结论）
    - A3：收窄 `context_patch` prompt 注入边界，对 `USER.md` + `memory/MEMORY.md`（Global）+ Personal Memory 三者做去重/冲突检测
    - **不改** categorized_memory 的数据结构（person/source 分层本身合理）
    - **不改** memory_tool 的读写语义（recall/remember 面向 person 维度，与 Dream 全局维度互补）
  - **Shadow skills 治理**：
    - 直接删除（无行为差异，可回落 upstream）：`github`、`summarize`、`weather`、`skill-creator`
    - 收窄（保留 sidecar 增量部分）：`cron`（+49 行：check_status/mark_done/timezone）、`tmux`（+108 行：BackgroundTaskStore 指导/防错建议）
    - 保留并重写边界说明：`memory`（完全不同的多用户/身份解析架构）
  - **Batch C 复核**（逐 patch 具体判断标准）：
    - `channel_patch`：清理已过时的 stream_id 注释；验证 MessageBatcher / typing 修复 / fallback 仍为纯 sidecar 功能
    - `transcription_patch`：确认仍为纯 SOCKS5 代理注入，上游无替代方案
    - `provider_prefix_patch`：评估是否定义弃用时间线（依赖旧配置迁移进度）
  - 跑与上述三条工作线直接相关的最小必要回归
  - 更新治理工件（patch_map.md、TODO.md、相关 module spec）
- **Out-of-Scope**:
  - 不重新做一次 `upstream/main` merge
  - 不重构 page-agent / console-ui / claude_code / codex / gateway lifecycle
  - 不把所有 sidecar 定制一次性改写成纯上游接口；仅处理本 spec 命中的热区
  - 不默认修改 `nanobot/`；除非明确是 upstream bugfix / upstream PR prep
- **Assumption**:
  - 当前 merge 基线固定为 `upstream/main@c092896`
  - 运行闭环已通过：split fresh-process 330 项定向 pytest + `python -m ava --help` / `status` smoke 已验证
  - 本轮 follow-up 的一等验收仍是 runtime continuity，治理优化必须排在其后

## 1.1 Context Sources

- Requirement Source:
  - 用户请求：`Dream 真源统一、shadow skills 收窄/删除、Batch C 增益区增量复核 生成对应的task spec`
  - Codex code review（v3 输入）：P1 person attribution contract 缺失、P2 去重边界遗漏 USER.md、P2 验证矩阵不足
- Design Refs:
  - `.specanchor/tasks/_cross-module/2026-04-08_upstream-main-merge-implementation.spec.md`
  - `.specanchor/tasks/_cross-module/2026-04-08_upstream-v0.1.5-merge-analysis.spec.md`
  - `.specanchor/patch_map.md`
  - `.specanchor/TODO.md`
- Extra Context:
  - `.specanchor/global/architecture.md`
  - `.specanchor/global-patch-spec.md`

## 1.5 Codemap Used (Feature/Project Index)

- Codemap Mode: `targeted-research`
- Key Index:
  - Entry Points / Architecture Layers:
    - `ava/__main__.py`
    - `ava/launcher.py`
    - `ava/patches/context_patch.py`
    - `ava/patches/loop_patch.py`
    - `ava/patches/skills_patch.py`
  - Core Logic / Cross-Module Flows:
    - `nanobot/agent/memory.py` — MemoryStore / Consolidator / Dream
    - `nanobot/agent/context.py` — ContextBuilder.build_system_prompt()（L20: BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md"]）
    - `nanobot/agent/loop.py` — AgentLoop._process_message()（L527/561: consolidator 调用点）
    - `nanobot/cli/commands.py` — L698-703: Dream cron 入口（无会话上下文）
    - `ava/agent/categorized_memory.py` — CategorizedMemoryStore / IdentityResolver
    - `ava/tools/memory_tool.py` — MemoryTool (recall/remember/map_identity/search_history)
    - `ava/skills/*`
    - `nanobot/skills/*`
    - `ava/patches/channel_patch.py`
    - `ava/patches/transcription_patch.py`
    - `ava/patches/provider_prefix_patch.py`
  - Dependencies / External Systems:
    - workspace `memory/` 目录与 `history.jsonl`（格式：`{cursor, timestamp, content}` — **不含 channel/chat_id**）
    - `memory/persons/` 目录（identity_map.yaml + per-person MEMORY.md / HISTORY.md / sources/）
    - workspace `sessions/` 目录（.jsonl 文件，metadata 行含 session.key = "channel:chat_id"）
    - SQLite `skill_config` disabled filter
    - provider / channel runtime

## 1.6 Context Bundle Snapshot (Lite)

- Bundle Level: `Lite`
- Key Facts:
  - merge 提交已完成：`42ea7cf`
  - `ava/UPSTREAM_VERSION` 已更新到 `c092896922373ac56602081d7350c5f3b3941aae`
  - `CategorizedMemoryStore.on_consolidate()` 已定义（L230-247），但从未被调用——Consolidator 和 Dream 都不知道它的存在
  - `skills_patch` 当前优先级：workspace/skills → ava/skills → .agents/*/skills → nanobot/skills
  - shadow skills 代码对比已完成：github/summarize/weather 与 upstream 完全相同；skill-creator 存在轻微文案漂移但无行为差异
  - cron 增量 +49 行（check_status/mark_done/timezone），tmux 增量 +108 行（BackgroundTaskStore 指导）
  - memory skill 是完全不同的架构（多用户/身份解析 vs upstream 的 Dream 两层模型）
- Key Architecture Facts（代码审计结论）:
  - **系统提示词加载顺序**（`context.py:build_system_prompt`）：identity → bootstrap files (`AGENTS.md`, `SOUL.md`, **`USER.md`**, `TOOLS.md`) → `# Memory\n\n{get_memory_context()}` (= `memory/MEMORY.md`) → active skills → recent history
  - **个人记忆注入点**（`context_patch.py:patched_build_messages`）：在 system prompt 末尾追加 `# Personal Memory\n\n{cat_mem.get_combined_context()}`
  - **去重必须覆盖三层**：`USER.md`（Dream 也会编辑它）+ `memory/MEMORY.md`（全局长期记忆）+ Personal Memory（个人记忆）。仅对后两者去重不够——用户偏好可能同时出现在 `USER.md` 和个人记忆里
  - **Person attribution 断点**（v3 核心发现）：
    - `history.jsonl` 格式：`{cursor, timestamp, content}` — **不含 channel/chat_id**
    - `Consolidator.archive(messages)` — 只接收消息列表，**不接收 session/channel/chat_id**
    - `maybe_consolidate_by_tokens(session)` — 有 session 但调用 `archive(chunk)` 时**丢掉了会话信息**
    - `Dream.run()` — 读取 history.jsonl，条目中**无身份信息**；cron 触发时**完全无会话上下文**
    - **可用的身份信息源**：实时消息处理时 `msg.channel`/`msg.chat_id` 可用；`session.key` = `"channel:chat_id"` 可用；session 文件 metadata 含 key
  - **两者是正交维度**：Dream 管全局维度 (MEMORY.md / SOUL.md / USER.md)，categorized_memory 管个人维度 (persons/\*/MEMORY.md)，不是主从关系

## 2. Research Findings

- 事实与约束:
  - 当前运行是双记忆面，但**不是双真源竞争**，而是两个正交粒度的视图缺少同步：
    - upstream `MemoryStore` / `Dream` / `Consolidator` → 全局 `memory/*` 与 `history.jsonl`
    - sidecar `categorized_memory` → 个人 `memory/persons/*/MEMORY.md` 与 per-person `HISTORY.md`
  - `on_consolidate()` 方法已完整实现（接受 channel/chat_id/history_entry/person_memory_facts，写入 person history 和 person memory），但从未被任何代码调用
  - prompt 注入目前是**无条件叠加**：`USER.md`（bootstrap）+ Global Memory（`memory/MEMORY.md`）+ Personal Memory（`persons/*/MEMORY.md`），三层之间没有去重或冲突检测。Dream 会编辑 `USER.md` 和 `MEMORY.md`，因此用户偏好可能同时出现在 `USER.md` 和 Personal Memory 中
  - **Person attribution 困境**：
    - Consolidator 路径：`maybe_consolidate_by_tokens(session)` 有 session（含 `channel:chat_id`），但调用 `archive(chunk)` 时丢掉了——**信息在调用链中可用但未传递**
    - Dream 路径：完全没有会话上下文——history.jsonl 不含身份、cron 入口不传 session——**信息在数据中不存在**
    - 两条路径需要不同的解决策略
  - shadow skills 代码对比结论：
    - `github`/`summarize`/`weather`：与上游完全相同，零增量
    - `skill-creator`：存在轻微文案漂移，但无行为差异，可安全回落 upstream
    - `cron`：+49 行实质增量（check_status/mark_done action + timezone 最佳实践）
    - `tmux`：+108 行实质增量（BackgroundTaskStore 优先建议 + coding agent 编排防错）
    - `memory`：完全不同架构（upstream 两层 Dream 模型 vs sidecar 三维度多用户身份解析）
  - Batch C patch 状态：
    - `channel_patch`：stream_id 部分已由上游 `33abe915` 接管并注释确认；MessageBatcher / typing 修复 / message_id fallback 是纯 sidecar 功能，无法收窄
    - `transcription_patch`：纯 SOCKS5 代理注入（GFW 绕过），上游永远不会接受地域特定功能
    - `provider_prefix_patch`：yunwu/zenmux 前缀剥离，向后兼容旧配置的垫片；只在 `_spec is None` 时触发

- 风险与不确定项:
  - **R1**（高→已升级）：Person attribution 在 Consolidator/Dream 路径中不可用。Consolidator 路径可通过 sidecar monkey-patch `maybe_consolidate_by_tokens` 在调用 `archive()` 前/后捕获 session.key 来解决。Dream 路径则需要更深入的方案（扩展 history.jsonl 格式、或接受 Dream 阶段不做 person 同步）
  - **R2**（低）：prompt 去重逻辑如果过于激进，可能误删有效的个人记忆片段
  - **R3**（低）：直接删 4 个 shadow skills 后，如果 workspace/skills/ 中有用户自定义的同名 skill，行为会变成 workspace → nanobot（跳过了 ava 层），但这是正确的优先级行为
  - **R4**（低）：provider_prefix_patch 如果定义弃用时间线，需要提前准备配置迁移文档

## 3. Innovate (Decision)

### 核心架构决策：Dream 同步方案

#### 已否决：Option A-old（三层存储重定义）

原 spec v1 方案：将 Dream 定义为 authoritative store，categorized_memory 降为 projection store / tool-facing store。

**否决理由**：过度设计。Dream 和 categorized_memory 是正交维度，不需要主从关系。

#### 已否决：Option A-v2（直接补 hook 调用）

v2 方案：在 Consolidator.archive() 和 Dream Phase 2 完成后各加 1-2 行 hook 调用 on_consolidate()。

**否决理由**（Codex review）：当前 history.jsonl 不携带 channel/chat_id，archive() 签名不接收会话参数，Dream cron 无会话上下文。直接加 hook 调用时参数从哪来没有定义。

#### 选定：Option A-v3（前置 gate + 分路径策略）

**方案**：先通过 A0 前置 gate 定义 person attribution contract，再分路径实施桥接。

**A0 前置 gate 需要回答的问题**：

1. **Consolidator 路径**：`maybe_consolidate_by_tokens(session)` 中 session.key 可用，但 `archive(chunk)` 时丢失。可选方案：
   - **(a) sidecar wrap `maybe_consolidate_by_tokens`**：在 `loop_patch` 中 monkey-patch 该方法，在调用原始方法前后捕获 `session.key`，解析出 `channel:chat_id`，archive 完成后调用 `on_consolidate()`。**不需要改 nanobot/**
   - **(b) 扩展 `archive()` 签名**：在 nanobot/ 中给 archive 加 `session_key` 参数。属于 upstream PR prep 例外。**需要改 nanobot/**
   - **(c) 在 history.jsonl 中持久化身份**：扩展 `append_history()` 记录格式。最彻底但改动面最大。**需要改 nanobot/**

2. **Dream 路径**：history.jsonl 不含身份信息，Dream cron 无会话上下文。可选方案：
   - **(d) 接受 Dream 阶段不做 person 同步**：Dream 编辑的是全局文件（MEMORY.md / SOUL.md / USER.md），本身不区分 person。person 同步只在 Consolidator 路径做。**零改动**
   - **(e) Dream 后处理时扫描 session 文件反查身份**：从 workspace/sessions/ 的 metadata 中提取 channel:chat_id，与 history 条目做时间窗口匹配。**可行但脆弱**
   - **(f) 在 history.jsonl 中持久化身份**：同 (c)，一次性解决两条路径。**需要改 nanobot/**

3. **A0 gate 的输出**：一份明确的技术决策文档，选定上述方案组合，并更新 A1/A2 的具体实施步骤。**A0 不通过则 A1/A2 不开始**。

**推荐组合**：**(a) + (d)**——Consolidator 路径用 sidecar wrap（不改 nanobot/），Dream 路径接受不做 person 同步（Dream 编辑的本身就是全局文件）。这是改动最小、风险最低的组合。

**优势**：
- 不改变 nanobot/ 中的任何代码
- 不改变任何现有数据结构和工具语义
- Consolidator 路径能获得完整的 person 归属（因为 session 在内存中）
- Dream 路径的"不做 person 同步"是语义正确的（Dream 管全局，不管个人）
- 两个维度保持独立演进能力

### 去重边界决策（v3 新增）

去重目标从 v2 的"Global Memory vs Personal Memory"扩展为**三层去重**：

| 层 | 来源 | 注入位置 | 编辑者 |
|----|------|----------|--------|
| `USER.md` | bootstrap file | `context.py:build_system_prompt` L38 | Dream Phase 2、用户手动 |
| `memory/MEMORY.md` | get_memory_context() | `context.py:build_system_prompt` L42-44 | Dream Phase 2 |
| Personal Memory | cat_mem.get_combined_context() | `context_patch.py:patched_build_messages` | MemoryTool、on_consolidate |

**去重策略**：在 `context_patch` 注入 Personal Memory 前，读取当前 system prompt 中已包含的 `USER.md` 和 `MEMORY.md` 内容，对 Personal Memory 做归一化后的段落级去重。保守原则：只去重高置信度的重复段落，宁可多注入也不要误删。

### Shadow Skills 决策

| Skill | 决策 | 依据 |
|-------|------|------|
| `github` | **删除** | 与 upstream 完全相同，零增量 |
| `summarize` | **删除** | 与 upstream 完全相同，零增量 |
| `weather` | **删除** | 与 upstream 完全相同，零增量 |
| `skill-creator` | **删除** | 无行为差异，可安全回落 upstream（存在轻微文案漂移但无功能差别） |
| `cron` | **收窄** | 保留 check_status/mark_done/timezone 增量，其余回退 upstream |
| `tmux` | **收窄** | 保留 BackgroundTaskStore 指导和 coding agent 防错建议 |
| `memory` | **保留+重写边界** | 完全不同架构，需明确"Dream 管全局，memory tool 管个人" |

### Batch C 决策

| Patch | 决策 | 具体判断标准 |
|-------|------|------------|
| `channel_patch` | **保留，清理注释** | 删除已过时的 stream_id 相关注释；MessageBatcher / typing / fallback 无法收窄 |
| `transcription_patch` | **保留，不动** | 纯地域特定需求，上游永远不会接受 |
| `provider_prefix_patch` | **保留，加弃用标记** | 在代码中加 `# DEPRECATION: 待所有配置迁移到 ProviderSpec 后删除` + 在 TODO.md 登记 |

## 4. Plan (Contract)

### 4.0 并行依赖图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        三条工作线的依赖关系 (v3)                      │
└─────────────────────────────────────────────────────────────────────┘

   Workstream A: Dream 同步通道
   ┌──────────────────────────┐
   │ A0. Person Attribution   │ ← GATE：必须先完成并输出技术决策
   │     Contract (research)  │   推荐结论：(a)+(d) sidecar wrap + Dream 不做 person 同步
   └──────────┬───────────────┘
              │ gate 通过后
   ┌──────────▼───────────────┐
   │ A1. Consolidator 桥接    │ ← 方案取决于 A0 结论
   │ A2. Dream 桥接或 skip    │ ← 若选 (d) 则此步为"记录决策 + skip"
   │ A3. 三层 prompt 去重     │ ← USER.md + MEMORY.md + Personal Memory
   └──────────┬───────────────┘
              │
              │                          Workstream B: Shadow Skills
              │                          ┌────────────────────────┐
              │                          │ B1. 删除 4 个 skills   │ ← 可立即并行
              │                          │ B2. 收窄 cron/tmux     │ ← 可立即并行
              │                          ├────────────────────────┤
              │ 必须等 A 完成            │ B3. memory skill       │
              └──────────┬───────────────┤     边界重写           │
                         │               └────────────────────────┘
              ┌──────────▼───────────────┐
              │ 回归验证 + 治理工件更新   │
              └──────────────────────────┘

   Workstream C: Batch C 复核              ← 完全独立，可与 A/B 全程并行
   ┌──────────────────────┐
   │ C1. channel_patch    │
   │     注释清理         │
   │ C2. transcription    │
   │     确认不动         │
   │ C3. provider_prefix  │
   │     加弃用标记       │
   └──────────────────────┘
```

**可并行的组合**：
- B1/B2 与 C 全部 → 可立即并行启动
- A0（research/gate）可与 B1/B2/C 并行
- A1/A2/A3 必须等 A0 gate 通过
- B3（memory skill 重写）必须等 A1-A3 完成

### 4.1 File Changes

#### Workstream A: Dream 同步通道

**A0 前置 gate（research only，无代码变更）：**
- 输出：在本 spec 的 Execute Log 中记录 person attribution 技术决策
- 验证 Consolidator 路径中 session.key 的可用性（读 `loop.py` 调用点确认）
- 验证 Dream 路径中身份信息的不可用性（读 `memory.py:Dream.run()` + `commands.py:on_cron_job` 确认）
- 选定方案组合并更新 A1/A2 具体步骤
- **Gate 判据**：选定的方案必须回答"on_consolidate(channel, chat_id, ...) 的 channel 和 chat_id 从哪里来"

**A1：Consolidator 桥接（假设选定方案 (a)：sidecar wrap）：**
- `ava/patches/loop_patch.py`
  - Monkey-patch `Consolidator.maybe_consolidate_by_tokens`（或在已有的 `patched_process_message` / `patched_save_turn` 中拦截）
  - 在调用原始方法前捕获 `session.key`，解析为 `channel, chat_id = session.key.split(":", 1)`
  - 在原始方法返回后（归档成功时），调用 `categorized_memory.on_consolidate(channel, chat_id, history_entry, "")`
  - `history_entry` 来源：Consolidator.archive() 的 LLM 摘要结果。由于 archive() 返回 `bool` 不返回摘要内容，需额外捕获（可 wrap archive() 或读取 history.jsonl 末条记录）

**A2：Dream 桥接（假设选定方案 (d)：skip）：**
- 无代码变更
- 在 Execute Log 中记录决策：Dream 编辑全局文件（MEMORY.md/SOUL.md/USER.md），不区分 person，因此 Dream 路径不做 person 同步是语义正确的

**A3：三层 prompt 去重：**
- `ava/patches/context_patch.py`
  - 实现 `_deduplicate_memory(system_prompt_so_far: str, personal_memory: str) -> str`
  - 输入：当前 system prompt（已包含 USER.md 和 MEMORY.md 内容）+ 待注入的 Personal Memory
  - 去重逻辑：对 Personal Memory 按段落（`\n\n` 分割）逐段检查，若段落内容（归一化：去空白、小写化）在 system_prompt_so_far 中出现为子串，则移除该段落
  - **保守原则**：只去重整段完全匹配，不做模糊匹配，宁可多注入

#### Workstream B: Shadow Skills 治理

- **删除**（B1，可立即执行）：
  - `ava/skills/github/` — 整个目录删除
  - `ava/skills/summarize/` — 整个目录删除
  - `ava/skills/weather/` — 整个目录删除
  - `ava/skills/skill-creator/` — 整个目录删除
- **收窄**（B2，可立即执行）：
  - `ava/skills/cron/SKILL.md` — 只保留 sidecar 增量部分（check_status/mark_done/timezone），其余描述回退到 upstream 版本
  - `ava/skills/tmux/SKILL.md` — 只保留 sidecar 增量部分（BackgroundTaskStore 优先建议 + coding agent 编排防错），其余描述回退到 upstream 版本
- **重写边界说明**（B3，依赖 A 完成）：
  - `ava/skills/memory/SKILL.md` — 重写为：明确 Dream 管全局记忆（MEMORY.md/SOUL.md/USER.md），memory tool 管个人记忆（persons/\*/MEMORY.md）；Consolidator 归档时通过 on_consolidate 同步 person history；Dream 阶段不做 person 同步（语义正确：Dream 管全局）；memory tool 的 recall/remember/map_identity/search_history 语义不变
- `ava/patches/skills_patch.py`
  - 无需修改；删除 ava/skills 中的 shadow skills 后，上游版本自动成为唯一来源

#### Workstream C: Batch C 复核

- `ava/patches/channel_patch.py`
  - 删除或更新 stream_id 相关的过时注释（L12-13 及其他引用处）
  - 确认 MessageBatcher / typing 修复 / message_id fallback 仍为 sidecar 独有功能
  - 无逻辑变更
- `ava/patches/transcription_patch.py`
  - 无变更。确认仍为纯 SOCKS5 代理注入，上游无替代方案
- `ava/patches/provider_prefix_patch.py`
  - 在文件头部 docstring 或关键代码段加弃用标记：`# DEPRECATION: 待所有 sidecar 网关配置迁移到 ProviderSpec 后，此 patch 可删除`
  - 无逻辑变更

#### 治理工件更新

- `.specanchor/patch_map.md`
  - 更新 `channel_patch` 行：注明 stream_id 已完全由上游接管
  - 更新 `provider_prefix_patch` 行：加弃用方向标记
- `.specanchor/TODO.md`
  - 更新 P1 "Dream 与 categorized_memory 仍是双真源" 条目：标注为"已定义同步方案（Consolidator 路径桥接 + Dream 路径语义正确不做 person 同步 + 三层去重）"
  - 新增条目：provider_prefix_patch 弃用时间线（P2）
- 相关 module spec
  - 按需更新 categorized_memory_spec / context_patch_spec / loop_patch_spec / skills_patch_spec

### 4.2 Signatures

- `ava.agent.categorized_memory.CategorizedMemoryStore.on_consolidate(channel: str, chat_id: str, history_entry: str, person_memory_facts: str) -> None` — 已有，无变更
- `ava.agent.categorized_memory.CategorizedMemoryStore.get_combined_context(channel: str | None, chat_id: str | None) -> str` — 已有，无变更
- `ava.tools.memory_tool.MemoryTool.execute(action: str, **kwargs: Any) -> str` — 已有，无变更
- `ava.patches.context_patch._deduplicate_memory(system_prompt_so_far: str, personal_memory: str) -> str` — **新增**，返回去重后的 personal_memory（v3：输入改为完整 system prompt 而非仅 global memory，覆盖 USER.md）
- `ava.patches.loop_patch._bridge_consolidation(original_method, self, session) -> None` — **新增**（v3 重新定义），wrap `maybe_consolidate_by_tokens`，在归档完成后调用 `on_consolidate()`

### 4.3 Implementation Checklist

#### Phase 0: A0 前置 Gate（research，可与 B1/B2/C 并行）

- [x] **A0**. Person Attribution Contract
  - 确认 Consolidator 路径中 `session.key` 在 `maybe_consolidate_by_tokens` 执行期间可用
  - 确认 `archive()` 返回 `bool`，不返回摘要内容——需要额外机制获取 `history_entry`（方案：wrap 后读 `history.jsonl` 末条，或 wrap `archive()` 本身捕获 LLM 输出）
  - 确认 Dream 路径中 history.jsonl 无身份信息 + cron 入口无会话上下文
  - 选定方案组合，推荐 (a)+(d)
  - 在 Execute Log Step 0 中记录决策结论
  - **Gate 通过条件**：决策记录中明确回答了"on_consolidate 的四个参数分别从哪里来"

#### Phase 1: 可并行的独立工作（B1/B2 + C 立即启动；A1-A3 在 A0 通过后启动）

- [x] **A1**. 在 `loop_patch` 中补 Consolidator → on_consolidate 桥接
  - Monkey-patch `Consolidator.maybe_consolidate_by_tokens`（在 `apply_loop_patch` 中）
  - 在调用前捕获 `session.key` → `channel, chat_id`
  - 在调用后（归档成功时）获取 history_entry（读 history.jsonl 末条 or wrap archive）
  - 调用 `categorized_memory.on_consolidate(channel, chat_id, history_entry, "")`
  - person_memory_facts 传空串（Consolidator 只做摘要归档，不提取个人记忆事实）
- [x] **A2**. Dream 路径决策落地
  - 若选定 (d)：在 Execute Log 中记录"Dream 管全局，不做 person 同步"
  - 若选定 (e) 或 (f)：按 A0 结论实施（但不推荐）
- [x] **A3**. 在 `context_patch` 中添加三层 prompt 去重逻辑
  - 实现 `_deduplicate_memory(system_prompt_so_far, personal_memory)` 函数
  - 在 Personal Memory 注入前调用去重
  - 去重范围覆盖 system_prompt_so_far 中的 USER.md + MEMORY.md 内容
  - 策略：段落级归一化后完全匹配，保守去重
- [x] **B1**. 删除 4 个无行为差异的 shadow skills
  - `rm -rf ava/skills/github ava/skills/summarize ava/skills/weather ava/skills/skill-creator`
  - 验证 `skills_patch` 的 `patched_list_skills()` 正确回退到 nanobot/skills 版本
- [x] **B2**. 收窄 cron/tmux skills
  - `cron`：提取 check_status/mark_done/timezone 增量为 sidecar-only section
  - `tmux`：提取 BackgroundTaskStore 指导和 coding agent 防错为 sidecar-only section
- [x] **C1**. 清理 `channel_patch` 过时注释
  - 更新或删除 L12-13 stream_id 相关注释
  - 验证 MessageBatcher / typing / fallback 代码不变
- [x] **C2**. 确认 `transcription_patch` 不动
  - 快速审计确认仍为纯 SOCKS5 代理注入
- [x] **C3**. 给 `provider_prefix_patch` 加弃用标记
  - docstring 加 DEPRECATION 注释
  - TODO.md 登记弃用时间线

#### Phase 2: 依赖 Phase 1 中 A 完成的工作

- [x] **B3**. 重写 memory skill 边界说明
  - 更新 `ava/skills/memory/SKILL.md`
  - 明确：Dream 管全局记忆，memory tool 管个人记忆
  - 说明 Consolidator 桥接的 on_consolidate 同步机制
  - 说明 Dream 路径不做 person 同步的设计决策及理由
  - 保持 recall/remember/map_identity/search_history 语义不变

#### Phase 3: 回归验证

- [x] **V1**. Dream 同步通道——桥接专用测试（v3 新增）
  - 新增 `tests/patches/test_consolidation_bridge.py`：
    - 构造 mock session（key="telegram:12345"）和 mock categorized_memory
    - 调用 wrapped `maybe_consolidate_by_tokens`
    - 断言 `on_consolidate` 被调用且 channel="telegram", chat_id="12345"
    - 断言 history_entry 非空
  - 此测试是 A1 的验收条件，不可省略
- [x] **V2**. Dream 同步通道——已有测试回归
  - `uv run pytest tests/patches/test_loop_patch.py tests/patches/test_context_patch.py -q`
  - `uv run pytest tests/agent/test_consolidator.py tests/agent/test_dream.py -q`（v3 新增：确保桥接没有破坏上游 Consolidator/Dream 行为）
- [x] **V3**. Prompt 去重验证
  - 手动构造场景：USER.md 和 Personal Memory 中有重复段落
  - 验证去重后 Personal Memory 中该段落被移除
  - 验证不重复的段落保留完整
- [x] **V4**. Skills 回归
  - `uv run pytest tests/patches/test_skills_patch.py -q`
  - 验证删除后 `patched_list_skills()` 返回的 4 个 skill 来自 nanobot/skills/
  - 验证 cron/tmux 的 sidecar 增量仍可被加载
- [x] **V5**. Batch C 回归
  - `uv run pytest tests/patches/test_channel_patch.py tests/patches/test_transcription_patch.py -q`
  - 验证 channel_patch 注释变更不影响运行时行为
- [x] **V6**. 全局 smoke
  - `python -m ava --help`
  - `python -m ava status`（如果可用）
- [x] **V7**. `git diff --check`

#### Phase 4: 治理工件更新

- [x] **G1**. 更新 `.specanchor/patch_map.md`
- [x] **G2**. 更新 `.specanchor/TODO.md`
- [x] **G3**. 更新相关 module spec（按需）

### 4.4 回滚策略

| 工作线 | 回滚方式 | 影响范围 |
|--------|----------|----------|
| A1 (Consolidator 桥接) | `git revert` 对应 commit；on_consolidate 从未被调用 → 回到现状 | 仅 loop_patch |
| A3 (prompt 去重) | `git revert` 对应 commit；prompt 回到无条件叠加 → 回到现状 | 仅 context_patch |
| B1 (删除 skills) | `git checkout -- ava/skills/{github,summarize,weather,skill-creator}/` | 仅 skills 目录 |
| B2 (收窄 skills) | `git checkout -- ava/skills/{cron,tmux}/SKILL.md` | 仅两个 SKILL.md |
| B3 (memory 边界) | `git checkout -- ava/skills/memory/SKILL.md` | 仅一个 SKILL.md |
| C (Batch C) | `git checkout -- ava/patches/{channel,transcription,provider_prefix}_patch.py` | 仅注释变更，无逻辑回滚需求 |

**原则**：每个工作线完成后独立验证，验证失败可独立回滚，不影响其他工作线。

## 5. Execute Log

- [x] Step 0: A0 前置 Gate——Person Attribution Contract 决策（记录于此）
  - 决策结论：选定 **(a) + (d)**。Consolidator 路径在 `loop_patch` 中 wrap `maybe_consolidate_by_tokens()` 与 `archive()`，用 `session.key` 保留 person attribution；Dream 路径保持“只管理全局文件，不做 person sync”
  - on_consolidate 四个参数来源：
    - `channel`：来自 `session.key.split(":", 1)[0]`
    - `chat_id`：来自 `session.key.split(":", 1)[1]`
    - `history_entry`：wrap `archive()` 后读取 `history.jsonl` 新写入的末条记录内容
    - `person_memory_facts`：本轮继续传空串；Consolidator 只做归档摘要，不单独提取 person facts
  - 选定方案组合：`(a) sidecar wrap maybe_consolidate_by_tokens/archive + (d) Dream 不做 person 同步`
- [x] Step 1: Phase 1 并行执行（A1/A2/A3 + B1/B2 + C1/C2/C3）
- [x] Step 2: Phase 2 串行执行（B3，依赖 A 完成）
- [x] Step 3: Phase 3 回归验证（V1-V7）
- [x] Step 4: Phase 4 治理工件更新（G1-G3）

## 6. Review Verdict

- Spec coverage: `pass`
- Behavior check: `pass`
- Regression risk: `medium-low`
- Module Spec 需更新: `ava-agent-categorized_memory` / `ava-patches-context_patch` / `ava-patches-loop_patch` / `ava-patches-skills_patch`
- Follow-ups: `保留 provider_prefix_patch 弃用观察项；其余本 task 已收口`

## 7. Plan-Execution Diff

- Any deviation from plan: `C1 最终无需代码 diff；当前 channel_patch 注释已与“stream_id 由上游接管、sidecar 仅保留 batcher/typing/fallback”口径一致，因此仅做审计并在 Execute Log 中收口`

## Appendix: Spec 版本记录

| 版本 | 日期 | 核心变更 |
|------|------|----------|
| v1 | 2026-04-08 | 初版：Dream 三层存储重定义 + shadow skills + Batch C |
| v2 | 2026-04-09 | Dream 方案改为"补同步通道"；明确并行依赖图；Batch C 逐 patch 判断标准；补回滚策略 |
| v3 | 2026-04-09 | 吸收 Codex review：A 线拆成 A0 gate + A1-A3；去重覆盖 USER.md；验证面补 test_consolidator/test_dream + 桥接专用测试；skill-creator 措辞修正为"无行为差异" |
| v4 | 2026-04-09 | A0 选 `(a)+(d)`；实现 Consolidator 桥接与 prompt 去重；完成 shadow skills 收口、provider_prefix 弃用标记、定向测试与治理工件回填 |
