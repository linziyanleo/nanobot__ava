---
specanchor:
  level: task
  task_name: "post-merge follow-up：Dream 真源统一、shadow skills 治理与 Batch C 复核"
  author: "@Codex"
  assignee: "@Codex"
  reviewer: "@Ziyan Lin"
  created: "2026-04-08"
  status: "in_progress"
  last_change: "基线刷新为 merge commit 42ea7cf / upstream c092896；运行闭环刷新为 split fresh-process 330 项 pytest + ava help/status smoke 已通过"
  related_modules:
    - ".specanchor/modules/categorized_memory_spec.md"
    - ".specanchor/modules/context_patch_spec.md"
    - ".specanchor/modules/loop_patch_spec.md"
    - ".specanchor/modules/skills_patch_spec.md"
    - ".specanchor/modules/tools_patch_spec.md"
    - ".specanchor/modules/channel_patch_spec.md"
    - ".specanchor/modules/transcription_patch_spec.md"
  related_global:
    - ".specanchor/global/architecture.md"
    - ".specanchor/global-patch-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "EXECUTE"
  branch: "codex/upstream-v0.1.5-merge-analysis"
---

# SDD Spec: post-merge follow-up：Dream 真源统一、shadow skills 治理与 Batch C 复核

## 0. Open Questions

- [x] 这三项 follow-up 是拆成 3 份 spec，还是先收在一份 cross-module spec
  - 结论：先收在一份 cross-module spec。三者共享同一批热区文件、同一条运行闭环和同一套上游基准，先分成三份会重复 research 与门禁；若执行中明显分叉，再拆子 spec
- [x] Dream 真源统一默认以哪一侧为基准
  - 结论：默认以上游 `Dream / Consolidator / history.jsonl / memory/*` 为全局记忆真源；`categorized_memory` 降为派生视图与 tool-facing/person-facing 投影层。这与当前“以上游为基准”的 merge 后治理方向一致
- [x] shadow skills 的默认处理规则是什么
  - 结论：同内容直接删除；仅保留 sidecar 增量的做收窄；语义已实质分叉的继续保留，但必须重新写清与 upstream 的边界
- [ ] `memory` skill / `memory` tool 在 Dream 真源统一后是否继续保留现有 person/source 双作用面，还是改成 upstream Dream 第一语义 + sidecar 补充动作

## 1. Requirements (Context)

- **Goal**: 在已完成 `upstream/main` merge 且运行闭环已验证通过的基础上，继续以 upstream 为基准推进三项 post-merge 收口工作：1）统一 Dream 记忆真源；2）治理 shadow skills；3）增量复核 Batch C（provider / transcription / channels）上游增益区，并确保 sidecar patch / tools / skills 仍能正常运行。
- **In-Scope**:
  - 定义并落地 Dream 真源统一方案：
    - upstream `Dream / Consolidator / history.jsonl / memory/*` 作为全局记忆真源
    - `categorized_memory` 保留为 person/source 视图、tool-facing 操作面或派生缓存
    - 收敛 prompt 注入边界，避免 global memory 与 personal memory 双重注入产生语义冲突
  - 审计并治理当前 shadow skills：
    - 删除：`github`、`summarize`、`weather`、`skill-creator`（若确认与 upstream 无行为差异）
    - 收窄：`cron`、`tmux`
    - 保留并重写边界：`memory`
  - 复核 Batch C 上游增益区与 sidecar patch 的重叠面：
    - `providers/*`
    - `providers/transcription.py`
    - `channels/*`
    - `ava/patches/channel_patch.py`
    - `ava/patches/transcription_patch.py`
    - `ava/patches/provider_prefix_patch.py`
  - 跑与上述三条工作线直接相关的最小必要回归
  - 更新必要治理工件与相关 module spec
- **Out-of-Scope**:
  - 不重新做一次 `upstream/main` merge
  - 不顺手重构 page-agent / console-ui / claude_code / codex / gateway lifecycle
  - 不把所有 sidecar 定制一次性改写成纯上游接口；仅处理本 spec 命中的热区
  - 不默认修改 `nanobot/`；除非明确是 upstream bugfix / upstream PR prep
- **Assumption**:
  - 当前 merge 基线固定为 `upstream/main@c092896`
  - 运行闭环已通过：split fresh-process 330 项定向 pytest + `python -m ava --help` / `status` smoke 已验证
  - 本轮 follow-up 的一等验收仍是 runtime continuity，治理优化必须排在其后

## 1.1 Context Sources

- Requirement Source:
  - 用户请求：`Dream 真源统一、shadow skills 收窄/删除、Batch C 增益区增量复核 生成对应的task spec`
- Design Refs:
  - `.specanchor/tasks/_cross-module/2026-04-08_upstream-main-merge-implementation.spec.md`
  - `.specanchor/tasks/_cross-module/2026-04-08_upstream-v0.1.5-merge-analysis.spec.md`
  - `.specanchor/patch_map.md`
  - `.specanchor/TODO.md`
- Extra Context:
  - `.specanchor/global/architecture.md`
  - `.specanchor/global-patch-spec.md`
  - 当前仓库仍缺 `scripts/specanchor-check.sh`，本次只创建 Task Spec，不跑 freshness / coverage 脚本

## 1.5 Codemap Used (Feature/Project Index)

- Codemap Mode: `targeted-research`
- Codemap File: `N/A`
- Key Index:
  - Entry Points / Architecture Layers:
    - `ava/__main__.py`
    - `ava/launcher.py`
    - `ava/patches/context_patch.py`
    - `ava/patches/loop_patch.py`
    - `ava/patches/skills_patch.py`
  - Core Logic / Cross-Module Flows:
    - `nanobot/agent/memory.py`
    - `nanobot/agent/context.py`
    - `nanobot/cli/commands.py`
    - `ava/agent/categorized_memory.py`
    - `ava/tools/memory_tool.py`
    - `ava/skills/*`
    - `nanobot/skills/*`
    - `ava/patches/channel_patch.py`
    - `ava/patches/transcription_patch.py`
  - Dependencies / External Systems:
    - workspace `memory/` 目录与 `history.jsonl`
    - SQLite `skill_config` disabled filter
    - provider / channel runtime

## 1.6 Context Bundle Snapshot (Lite)

- Bundle Level: `Lite`
- Bundle File: `N/A`
- Key Facts:
  - merge 提交已完成：`42ea7cf`
  - `ava/UPSTREAM_VERSION` 已更新到 `c092896922373ac56602081d7350c5f3b3941aae`
  - 当前最大未收口问题不是 merge 冲突，而是 merge 后治理：Dream 双真源、shadow skills 覆盖、Batch C patch overlap
  - `CategorizedMemoryStore.on_consolidate()` 已定义，但当前没有接到 upstream `Dream / Consolidator` 输出上
  - `skills_patch` 当前优先级会让 `ava/skills/*` 覆盖同名 upstream skills
- Open Questions:
  - person/source 记忆语义要保留到什么程度
  - `memory` skill / tool 是否需要改成“Dream 第一语义 + sidecar 增量动作”

## 2. Research Findings

- 事实与约束:
  - 当前运行是双记忆面：
    - upstream `MemoryStore` / `Dream` / `Consolidator` 提供全局 `memory/*` 与 `history.jsonl`
    - sidecar `categorized_memory` 仍提供 person/source 记忆与 `memory` tool 当前语义
  - 当前双记忆面不会立刻打崩启动，但会形成双重 prompt 注入和双写/双读语义风险
  - shadow skills 目前至少包括：
    - 直接同名且建议删除：`github`、`summarize`、`weather`、`skill-creator`
    - 同名但仅保留 sidecar 增量更合理：`cron`、`tmux`
    - 同名且实质分叉：`memory`
  - Batch C 增益区的主要目标不是“全量重做 provider/channel”，而是确认 merge 后 sidecar patch 没有压住上游新能力或继续重复旧修复
- 风险与不确定项:
  - 直接把 `categorized_memory` 废掉，可能破坏当前 `memory` tool 和 person/source 记忆体验
  - 直接删 shadow skills，可能改变 prompt 暗示与 operator 习惯
  - Batch C 触点分散在 providers / transcription / channels，多数不是共享文件冲突，而是行为重叠，容易“能跑但边界已漂”

## 2.1 Next Actions

- 下一步动作 1：先把 Dream 真源统一的目标结构写死，明确什么是 authoritative store，什么只是 projection / tool-facing view
- 下一步动作 2：按 `delete / narrow / keep` 三分类清空 shadow skills 清单，避免继续以 `ava/skills` 阴影覆盖 upstream
- 下一步动作 3：以 Batch C audit matrix 的方式检查 provider / transcription / channels，不做泛化 sweep

## 3. Innovate (Optional: Options & Decision)

### Option A

- 方案：以上游 Dream 为全局真源，`categorized_memory` 变成派生视图 / tool-facing cache
- Pros:
  - 与 upstream 基线一致，后续 merge 成本最低
  - 可以保留 sidecar person/source 操作面，而不用继续维护两套真正的持久化真源
  - `memory` tool / skill 可以逐步收敛到“读取派生视图 + 写入统一真源”
- Cons:
  - 需要补桥接点
  - 需要重新定义 prompt 注入边界和 memory tool 语义

### Option B

- 方案：继续以 `categorized_memory` 为真源，把 Dream 当全局归档或旁路能力
- Pros:
  - 对现有 tool / skill 语义改动最小
  - person/source 体验风险较低
- Cons:
  - 违背“以上游为基准”的治理方向
  - 每次 upstream memory 演进都会继续形成 merge debt

### Option C

- 方案：长期双写，Dream 与 categorized_memory 都保留真源地位
- Pros:
  - 过渡期体验平滑
- Cons:
  - 状态最复杂，测试面最大
  - 只是把当前双真源风险制度化，不是真正收口

### Decision

- Selected: `Option A`
- Why:
  - 这轮 follow-up 的核心目标不是“保留所有旧语义不动”，而是 merge 后以上游为基准收口技术债
  - 只要派生视图与 tool-facing 语义设计得当，就能兼顾 upstream 对齐和 sidecar 体验

### Skip (for small/simple tasks)

- Skipped: false
- Reason: 此任务跨 memory / tools / skills / provider / channels 多个热区，必须先写清契约再进入实现

## 4. Plan (Contract)

### 4.1 File Changes

- `ava/agent/categorized_memory.py`
  - 重新定义为统一真源之上的派生 person/source 视图，并接上 consolidate / dream 输出桥
- `ava/tools/memory_tool.py`
  - 对齐统一后的记忆语义，明确 recall / remember / search_history 各自读写哪一层
- `ava/patches/context_patch.py`
  - 收窄 prompt memory 注入边界，避免 upstream global memory 与 sidecar personal memory 无限制叠加
- `ava/patches/loop_patch.py`
  - 补 Dream / Consolidator / categorized_memory 之间的桥接点或 hook
- `ava/skills/memory/SKILL.md`
  - 更新 memory skill 说明，明确 Dream 真源与 person/source 视图的边界
- `ava/patches/skills_patch.py`
  - 若需要，补更明确的 shadow skill allowlist / override 策略
- `ava/skills/github/SKILL.md`
  - 若确认无 sidecar 增量则删除
- `ava/skills/summarize/SKILL.md`
  - 若确认无 sidecar 增量则删除
- `ava/skills/weather/SKILL.md`
  - 若确认无 sidecar 增量则删除
- `ava/skills/skill-creator/SKILL.md`
  - 若确认无 sidecar 增量则删除
- `ava/skills/cron/SKILL.md`
  - 收窄为仅保留 sidecar 额外约束
- `ava/skills/tmux/SKILL.md`
  - 收窄为仅保留 sidecar guardrail
- `ava/templates/TOOLS.md`
  - 若 `memory` tool 语义或调用建议变化，同步运行时提示
- `ava/patches/channel_patch.py`
  - 复核 Telegram patch 是否还能继续收窄到仅保留 upstream 未覆盖边界
- `ava/patches/transcription_patch.py`
  - 复核是否仍只需要 proxy 增量，或是否还能继续收窄
- `ava/patches/provider_prefix_patch.py`
  - 复核 Batch C provider 增益后是否仍保持最小兼容职责
- `.specanchor/patch_map.md`
  - 更新 post-merge 后的 keep / narrow / delete 判断
- `.specanchor/TODO.md`
  - 回填剩余 follow-up 与未收口风险
- 相关测试文件
  - 仅补 memory / skills / transcription / channel / provider 相关回归

### 4.2 Signatures

- `ava.agent.categorized_memory.CategorizedMemoryStore.on_consolidate(channel: str, chat_id: str, history_entry: str, person_memory_facts: str) -> None`
- `ava.agent.categorized_memory.CategorizedMemoryStore.get_combined_context(channel: str | None, chat_id: str | None) -> str`
- `ava.tools.memory_tool.MemoryTool.execute(action: str, **kwargs: Any) -> str`
- `ava.patches.context_patch.apply_context_patch() -> str`
- `ava.patches.loop_patch.apply_loop_patch() -> str`
- `ava.patches.skills_patch.apply_skills_patch() -> str`
- `ava.patches.channel_patch.apply_channel_patch() -> str`
- `ava.patches.transcription_patch.apply_transcription_patch() -> str`

### 4.3 Implementation Checklist

- [ ] 1. 建立 follow-up audit matrix：Dream 真源、shadow skills、Batch C 三条工作线各自的目标文件、当前行为和最低验证
- [ ] 2. 明确 Dream 真源统一契约：定义 authoritative store、projection store、tool-facing store 三层边界
- [ ] 3. 落地 memory bridge：让 `categorized_memory` / `memory_tool` 与 upstream `Dream / Consolidator` 对齐，而不是继续各自为政
- [ ] 4. 调整 `context_patch` / `loop_patch` 的记忆注入与桥接逻辑，避免双重 prompt 注入或语义漂移
- [ ] 5. 审计并治理 shadow skills：
  - delete: `github` / `summarize` / `weather` / `skill-creator`
  - narrow: `cron` / `tmux`
  - keep-but-rewrite-boundary: `memory`
- [ ] 6. 复核 Batch C：
  - provider 增益
  - transcription 增益
  - channels 增益
  - sidecar 对应 patch 是否还能继续收窄
- [ ] 7. 跑最小必要回归：
  - memory / context / dream / commands
  - skills loader / skill discovery / skill load
  - provider / transcription / channels
  - `python -m ava --help` / `status`
- [ ] 8. 更新 `.specanchor/patch_map.md`、`.specanchor/TODO.md` 与必要 module spec
- [ ] 9. 执行 `git diff --check`

## 5. Execute Log

- [ ] Step 1: 建立 Dream / skills / Batch C audit matrix
- [ ] Step 2: 明确 Dream 真源统一契约
- [ ] Step 3: 落地 memory bridge 与 tool/context 语义调整
- [ ] Step 4: 收窄 / 删除 shadow skills
- [ ] Step 5: 复核并修补 Batch C 热区
- [ ] Step 6: 跑 focused pytest / ava smoke / diff-check
- [ ] Step 7: 更新治理工件与 follow-up 结论

## 6. Review Verdict

- Spec coverage: `TBD`
- Behavior check: `TBD`
- Regression risk: `TBD`
- Module Spec 需更新: `TBD`
- Follow-ups: `TBD`

## 7. Plan-Execution Diff

- Any deviation from plan: `TBD`
