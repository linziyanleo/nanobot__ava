---
specanchor:
  level: task
  task_name: "合并 upstream/main 并收口 sidecar 热区冲突"
  author: "@Codex"
  assignee: "@Codex"
  reviewer: "@Ziyan Lin"
  created: "2026-04-08"
  status: "in_progress"
  last_change: "执行 upstream/main merge 冲突收口，完成 206 项定向回归与 ava startup/status smoke，并同步治理工件"
  related_modules:
    - ".specanchor/modules/schema_patch_spec.md"
    - ".specanchor/modules/onboard_patch_spec.md"
    - ".specanchor/modules/console_patch_spec.md"
    - ".specanchor/modules/context_patch_spec.md"
    - ".specanchor/modules/loop_patch_spec.md"
    - ".specanchor/modules/skills_patch_spec.md"
    - ".specanchor/modules/storage_patch_spec.md"
    - ".specanchor/modules/tools_patch_spec.md"
    - ".specanchor/modules/page_agent_runtime_spec.md"
  related_global:
    - ".specanchor/global/architecture.md"
    - ".specanchor/global-patch-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "EXECUTE"
  branch: "codex/upstream-v0.1.5-merge-analysis"
---

# SDD Spec: 合并 upstream/main 并收口 sidecar 热区冲突

## 0. Open Questions

- [x] 本轮实施目标是否继续停在 `v0.1.5`
  - 结论：默认不再停在 `v0.1.5`，按上一份 research spec 的结论直接以 `upstream/main` 为目标；`v0.1.5` 仅作为热区地图和风险分层依据
- [x] Dream 本轮是否要直接接管现有记忆真源
  - 结论：不直接接管。策略改为“先合并兼容”，即保留 upstream Dream / Consolidator / config / cron 路径可运行，但本轮不把它升级为 sidecar 记忆真源，也不要求立即打通到 `categorized_memory`
- [x] 当前分支已有未提交改动是否命中本轮 merge 路径并阻塞真正执行
  - 结论：存在本地 spec 改动与一个未跟踪 task spec，但未命中 merge 阻塞路径；实际 merge 已执行并完成冲突收口
- [x] merge 后 `patch / tools / skills` 的最小运行闭环是否完整
  - 结论：完整。两轮定向 pytest 共 206 项通过，`uv run python -m ava --help` 与 `uv run python -m ava status` 均通过；patch、custom tools、skills loader、Dream compat 主路径均成功注册
- [ ] 在运行闭环确认后，哪些 patch / skills 可以立即收窄或删除，哪些只应先保留并补回归

## 1. Requirements (Context)

- **Goal**: 将当前 sidecar 分支与最新 `upstream/main` 对齐，并优先确认 `patch / custom tools / skills` 在 merge 后仍能继续正常运行；其中 Dream 相关能力按“先合并兼容、不切换真源”处理；在此基础上再收口 shared file 与长期 patch 热区冲突。
- **In-Scope**:
  - fetch 最新 `upstream/main` 并重算 merge-base / 左右分叉
  - 执行 merge 或明确不能 merge 的真实阻塞点
  - 按研究结论处理 3 个共享文件：`nanobot/agent/context.py`、`nanobot/config/loader.py`、`nanobot/templates/TOOLS.md`
  - 先验证 merge 后 `schema/onboard`、`context/loop`、`tools/templates`、`console/restart`、`skills` 这些 patch 热区还能继续工作
  - Dream 相关能力先按兼容目标处理：
    - upstream `Consolidator` / `Dream` / `DreamConfig` / cron 注册路径可以正常启动
    - 不要求本轮把 Dream 接成 sidecar 记忆真源
    - 不要求本轮把 Dream 输出同步进 `categorized_memory`
  - 仅在运行闭环确认后，再评估这些热区的收窄 / 删除 / 上推空间
  - 更新 `ava/UPSTREAM_VERSION` 与 `.specanchor` 治理工件
  - 跑最小必要的 patch/guardrail/config/runtime 回归
- **Out-of-Scope**:
  - 不把所有 sidecar 直接落在 `nanobot/` 的历史定制一次性彻底迁回 `ava/`
  - 不在本轮顺手做与 merge 无关的 console/page-agent/skill 重构
  - 不处理与本轮上游变更无关的 repo 杂项脏文件
- **Assumption**:
  - 默认按 `upstream/main` 执行，而不是只并 `v0.1.5`
  - 若用户后续明确要求 release-aligned checkpoint，可将执行目标收窄回 `v0.1.5`
  - Dream 本轮先并兼容，不把 `memory/MEMORY.md` / `categorized_memory` / `history_summarizer` / `history_compressor` 重构成单一真源

## 1.1 Context Sources

- Requirement Source:
  - 用户请求：`先继续之前的合并任务，开一个实施型 Task Spec`
- Design Refs:
  - `.specanchor/tasks/_cross-module/2026-04-08_upstream-v0.1.5-merge-analysis.spec.md`
  - `.specanchor/tasks/_cross-module/2026-04-03_upstream-main-merge-followup.spec.md`
  - `.specanchor/patch_map.md`
  - `.specanchor/TODO.md`
- Extra Context:
  - `.specanchor/global/architecture.md`
  - `.specanchor/global-patch-spec.md`
  - 当前仓库缺少 `scripts/specanchor-check.sh`，无法按标准脚本做 coverage / freshness 检查
  - 项目约束：默认禁止直接改 `nanobot/`，但 upstream 集成 / conflict reconciliation 属于例外

## 1.5 Codemap Used (Feature/Project Index)

- Codemap Mode: `targeted-research`
- Codemap File: `N/A`
- Key Index:
  - Entry Points / Architecture Layers:
    - `ava/__main__.py`
    - `ava/launcher.py`
    - `ava/patches/*`
    - `nanobot/agent/loop.py`
  - Core Logic / Cross-Module Flows:
    - `nanobot/agent/context.py` + `ava/patches/context_patch.py`
    - `nanobot/config/loader.py` + `ava/forks/config/schema.py` + `ava/patches/c_onboard_patch.py`
    - `nanobot/templates/TOOLS.md` + `ava/templates/TOOLS.md` + `ava/patches/templates_patch.py`
    - `ava/patches/loop_patch.py` + `ava/patches/tools_patch.py` + `ava/patches/skills_patch.py`
    - `ava/runtime/lifecycle.py` + `ava/patches/console_patch.py` + `ava/tools/gateway_control.py`
  - Dependencies / External Systems:
    - SQLite storage (`ava/storage/*`)
    - console observe/token stats/media surfaces
    - upstream `providers/`、`channels/`、`utils/restart.py`

## 1.6 Context Bundle Snapshot (Lite)

- Bundle Level: `Lite`
- Bundle File: `N/A`
- Key Facts:
  - 当前分支为 `codex/upstream-v0.1.5-merge-analysis`
  - 已完成一份 research spec，核心结论是直接对齐 `upstream/main` 比停在 `v0.1.5` 更省总成本
  - 当前最可能形成真实 merge 冲突的 shared files 只有 `context.py`、`loader.py`、`TOOLS.md`
  - 行为级热区仍集中在 `schema/onboard`、`context/loop`、`tools/templates`、`console/restart`、`skills`
  - Dream 在 upstream `v0.1.5` 中是默认注册的 system job，因此本轮需要明确“先兼容，不切真源”
- Open Questions:
  - 当前 worktree 里的非本任务脏文件是否与本轮 merge 命中同一路径
  - `skills_patch` 与 upstream `SkillsLoader` 重构是否需要即刻收窄

## 2. Research Findings

- 事实与约束:
  - 当前 sidecar upstream 基线是 `7113ad34`，`v0.1.5` 是 `79234d23`，最新 `upstream/main` 已前进到 `e21ba5f6`
  - `v0.1.5` 相对当前基线暴露出的核心问题，不是 tag 独有功能，而是 shared file 与长期 patch 热区边界
  - 真正的 shared file 冲突候选只有 3 个：
    - `nanobot/agent/context.py`
    - `nanobot/config/loader.py`
    - `nanobot/templates/TOOLS.md`
  - 行为热区分层：
    - Batch A：`context` / `loader` / `TOOLS.md` + `schema/onboard` + Dream config / startup 兼容
    - Batch B：`loop/context/tools/templates/console/skills`
    - Batch C：`provider/transcription/channels/*` 上游增益区
- 风险与不确定项:
  - 直接追到 `upstream/main` 会把 `v0.1.5` 后的 48 个提交一起带进来，扩大验证面
  - `restart` 当前有 upstream notice 与 sidecar lifecycle 两套状态语义，若 merge 时不先定真源，容易形成表面能跑但语义分裂
  - `nanobot/templates/TOOLS.md` 与 `ava/templates/TOOLS.md` 是双事实源；只解决前者会导致 runtime 仍旧陈旧
  - Dream 默认会注册 cron job，而 sidecar 现有记忆体系仍以 `categorized_memory + summarize/compress` 为主；若不显式限定“先兼容”，容易在 merge 当回合误切成双真源

## 2.1 Next Actions

- 下一步动作 1：先 fetch 最新 `upstream/main`，重新确认 merge-base 与 worktree 阻塞点
- 下一步动作 2：先处理 3 个 shared files 的 reconcile 策略，并以“merge 后 patch / tools / skills 还能否继续运行”为第一验收门槛
- 下一步动作 3：对 Dream 采用“兼容优先”策略，先确认 upstream memory / dream / cron 路径不打断 sidecar 现有记忆链，再决定后续是否统一真源

## 3. Innovate (Optional: Options & Decision)

### Decision

- Selected: 直接以 `upstream/main` 为实施目标，按 research spec 已经形成的 Batch A/B/C 热区顺序执行
- Why:
  - 如果当前就是要投入 merge 成本，停在 `v0.1.5` 只会把 shared file reconcile 和 patch 热区判断做两轮
  - 但执行顺序必须先改成“运行连续性优先，治理优化其次”，否则容易在 merge 当回合过早做收窄判断

### Skip (for small/simple tasks)

- Skipped: false
- Reason: 此任务跨多个 patch / fork / shared file，且需要先定 shared file 真源，再进入 Execute

## 4. Plan (Contract)

### 4.1 File Changes

- `nanobot/agent/context.py`
  - 解决 upstream prompt/template 变化与本地 `_sanitize_history()` 的 reconcile
- `nanobot/config/loader.py`
  - 融合 upstream `${VAR}` env interpolation 与本地 `extra_config.json` overlay 逻辑
- `nanobot/templates/TOOLS.md`
  - 解决 upstream 原生工具说明变化与本地重写之间的 shared file 冲突
- `nanobot/cli/commands.py`
  - 若 merge 命中 Dream cron 注册 / gateway 启动路径，做最小兼容 reconcile，但不在本轮扩展 Dream 的 sidecar 接管面
- `ava/templates/TOOLS.md`
  - 同步运行时有效模板中的 `glob/grep` 等上游新增工具说明
- `ava/forks/config/schema.py`
  - 若 merge 后 upstream schema 形状再变化，补齐 sidecar fork 继承兼容
- `ava/patches/c_onboard_patch.py`
  - 确认 refresh / wizard 路径与新 loader/schema 行为兼容
- `ava/patches/context_patch.py`
  - 确认 build_messages 与 provider sanitize 的边界没有被 upstream 吃掉或重复，并验证与 upstream Dream 全局 memory 注入不形成明显冲突
- `ava/patches/loop_patch.py`
  - 复核 upstream `AgentLoop` 的 `Consolidator` / `Dream` / tool context 变化是否打断现有 wrapper 契约
- `ava/patches/tools_patch.py`
  - 复核与 upstream default tools / new tool docs 的兼容性
- `ava/patches/skills_patch.py`
  - 复核 SkillsLoader 重构后的 wrapper 契约
- `ava/patches/console_patch.py`
  - 复核 gateway / restart 相关变动与 sidecar lifecycle 的兼容性
- `ava/UPSTREAM_VERSION`
  - 成功 merge 并验证后同步到最新 upstream commit
- `.specanchor/patch_map.md`
  - 更新热区判断和 patch 取舍
- `.specanchor/TODO.md`
  - 补 merge 后剩余技术债与 follow-up
- 相关测试文件
  - 仅补与本轮 hit zone 直接相关的 patch / config / provider / command 回归

### 4.2 Signatures

- `ava.patches.a_schema_patch.apply_schema_patch() -> str`
- `ava.patches.c_onboard_patch.apply_onboard_patch() -> str`
- `ava.patches.context_patch.apply_context_patch() -> str`
- `ava.patches.loop_patch.apply_loop_patch() -> str`
- `ava.patches.tools_patch.apply_tools_patch() -> str`
- `ava.patches.skills_patch.apply_skills_patch() -> str`
- `ava.patches.console_patch.apply_console_patch() -> str`
- `ava.patches.storage_patch.apply_storage_patch() -> str`

### 4.3 Implementation Checklist

- [x] 1. fetch 最新 `upstream/main`，重算 merge-base / 左右分叉，并确认当前 worktree 是否有真实阻塞
- [x] 2. 执行 merge，并优先处理 3 个 shared files：`context.py`、`loader.py`、`TOOLS.md`
- [x] 3. 先做运行闭环验证：确认 merge 后 `patch / custom tools / skills` 仍能注册、加载、执行基础路径
- [x] 4. 完成 Batch A：`schema/onboard`、Dream config/startup compat 与 `ava/templates/TOOLS.md` 的真实运行时对齐
- [x] 5. 完成 Batch B：`loop/context/tools/templates/console/skills` 热区复核与最小必要修补
- [ ] 6. 复核 Batch C：provider/transcription/channel 增益区，只修被 merge 打断的契约，不做额外扩改
- [x] 7. 在运行闭环稳定后，再更新 `ava/UPSTREAM_VERSION`、`.specanchor/patch_map.md`、`.specanchor/TODO.md` 与必要 module spec
- [x] 8. 跑最小必要回归：
  - patches: schema/onboard/context/loop/tools/console/skills/storage/transcription
  - guardrails: schema_drift / patch_runtime_contracts / spec_sync
  - focused runtime/config/provider: config_migration / context_prompt_cache / loop_save_turn / commands / gateway_control / provider_retry / openai_responses / Dream cron startup
- [ ] 9. 基于回归结果，再决定本轮只保留运行修复，还是顺手做低风险的收窄 / 删除
- [ ] 10. 执行 `git diff --check`，确认无格式性破坏

## 5. Execute Log

- [x] Step 1: fetch 最新 `upstream/main` 并确认 merge-base / worktree 状态
- [x] Step 2: merge upstream 并记录命中的 shared files / patch 热区
- [x] Step 3: reconcile `context.py` / `loader.py` / `TOOLS.md`
- [x] Step 4: 验证 `patch / custom tools / skills` 的基础运行闭环，并确认 Dream compat 不打断现有记忆主链
- [x] Step 5: 复核并修补 Batch A / B 热区
- [ ] Step 6: 跑 focused pytest / guardrails / diff-check
- [x] Step 7: 更新 `UPSTREAM_VERSION` 与 `.specanchor` 治理工件

## 6. Upstream 基准 Overlap 清单（供 Execute 后开发使用）

> 基准：`upstream/main@e21ba5f6`
> 用途：merge / reconcile 完成后，后续开发默认以上游为真源，对 sidecar 现有 patch / tools / skills 做 keep / narrow / delete / upstream 判断。
> 第一判定原则：先看 merge 后是否还能继续正常运行。
> 第二判定原则：只有在运行闭环稳定后，才讨论该项是否应收窄 / 删除 / 上推。
> Dream 特别规则：本轮只要求 upstream Dream / Consolidator / cron 路径与 sidecar 共存，不要求本轮把它升级为 sidecar 记忆真源。
> 约束：本节不是要求在本轮立即做全量重构；若某项未被本轮 merge 命中，可记录为 follow-up，不顺手扩改。

### 6.1 Patch 清单

| Patch | 与 upstream/main 的关系 | sidecar 独有职责 | 当前建议 | 说明 |
|-------|--------------------------|------------------|----------|------|
| `a_schema_patch` | 上游 `schema.py` 持续演进，且本仓库仍以 fork 完整替换 | sidecar config 字段承载、继承式兼容 | `保留` | 这是当前最高热区；每次上游 schema 增量都必须先同步这里，再谈其他 patch 收窄 |
| `b_config_patch` | 上游 `AgentDefaults` 已吸收大部分基础形状 | 降级字段注入 | `删除` | 目标是把残余兼容压回 schema / migration；若 merge 后验证无依赖，应优先删掉它 |
| `bus_patch` | 上游没有 sidecar console queue listener | console 事件桥接 | `保留` | 与上游职责边界清晰，低冲突低收益，不建议为 merge 顺手改写 |
| `c_onboard_patch` | 上游已有 onboard / refresh 主流程 | 保形 refresh、sidecar config 兼容 | `收窄` | 只保留 sidecar 结构兼容层，不重复上游 wizard / prompt / baseline 初始化 |
| `channel_patch` | 上游 Telegram 能力持续增强 | batch 发送与 `send_delta` 修补 | `收窄` | 保留确属 sidecar 修复的最小差异；若修复已被证实通用，应转成独立 upstream bugfix PR |
| `console_patch` | 上游 gateway / restart 有变化，但无 sidecar console 启动面 | console 注入、同 loop 事件循环协作 | `保留` | console 仍是 sidecar 独有面；只需持续防止遮蔽上游 gateway / restart 新逻辑 |
| `context_patch` | 上游已吸收部分 message merge / prompt template 演进，并引入 Dream 全局 memory 视图 | summarize / compress / personal memory / digest / provider-side sanitize | `收窄` | 以上游 `build_messages` 为主；本轮先确认 Dream 全局 memory 与 sidecar personal memory 能共存，再决定后续是否统一 |
| `loop_patch` | 上游 `AgentLoop` 仍是持续热区，且新增 `Consolidator` / `Dream` | db / token / bg_tasks / lifecycle 注入 | `保留` | 这是 sidecar 主承重点；本轮要求它与 upstream Dream/Consolidator 共存，不要求立刻把两套记忆链统一 |
| `provider_prefix_patch` | 上游不关心 `yunwu/zenmux` 这类 sidecar 私有前缀 | 旧配置兼容 | `保留` | 与 upstream 基线几乎无重叠；等历史 `.nanobot` 配置迁移完再评估删除 |
| `skills_patch` | 上游 `SkillsLoader` 持续在演进 | 三源发现、优先级覆盖、disabled filter | `收窄` | 保留 source policy，尽量少改 loader 内部流程；尤其避免继续复制上游 skill 元数据处理 |
| `storage_patch` | 上游无 sidecar SQLite 共享持久化替代 | session/db 持久化、shared DB | `保留` | 低冲突且 sidecar 独有，当前不建议上推或拆散 |
| `templates_patch` | 上游模板持续变，但 runtime overlay 仍由 sidecar 托管 | `ava/templates/*` → workspace overlay | `保留` | 关键不是删 patch，而是把上游新增工具 / 提示同步进 overlay 真源 |
| `tools_patch` | 上游 default tools 在扩张，但不会注册 sidecar 自定义工具 | 8 个 sidecar tool 注入 | `保留` | 真风险在注册入口和文档漂移，不在于功能已被上游替代 |
| `transcription_patch` | 上游统一转写链路继续增强 | Groq proxy / compat | `收窄` | 只保留代理兼容这类 sidecar 增补，不再重复上游通用 transcription 行为 |

### 6.2 Custom Tools 清单

> 截至当前 `upstream/main`，sidecar 自定义工具与上游默认工具**没有直接同名冲突**；重叠主要发生在能力域和控制面，而不是 tool name。

| Tool | 与 upstream/main 的关系 | 当前建议 | 说明 |
|------|--------------------------|----------|------|
| `claude_code` | 上游没有同类 coding-agent tool | `保留` | sidecar 独有工作流面 |
| `codex` | 上游没有同类 coding-agent tool；只有 provider / model 支持增强 | `保留` | 与 upstream provider 能力不是一个层次 |
| `gateway_control` | 与 upstream `restart_notice` / gateway status 同域 | `保留` | 仍以 sidecar lifecycle 为真源；不要把 upstream notice 当替代控制面 |
| `image_gen` | 上游无同类 tool | `保留` | sidecar 独有多媒体面 |
| `memory` | 与 upstream memory / Dream 同域，但上游还没有同名 tool | `保留` | 本轮维持 sidecar `memory` tool 不变；Dream 先兼容，不替代当前按 person/source 操作的工具面 |
| `page_agent` | 上游无浏览器 page-agent tool | `保留` | sidecar 独有能力 |
| `send_sticker` | 上游无同类 tool | `保留` | sidecar 独有能力 |
| `vision` | 与上游多模态能力同域，但无独立 tool 对应 | `保留` | 当前仍是 sidecar 独有调用面 |

### 6.3 Skills 清单

> `skills_patch` 当前优先级是：`workspace/skills > ava/skills > .agents/skills > nanobot/skills`。
> 因此同名 `ava/skills/*` 会覆盖 `upstream/main` 的 builtin skill；这类项目要优先分辨是真分叉，还是已经可以删回 upstream。

| Skill | 与 upstream/main 的关系 | 当前建议 | 说明 |
|-------|--------------------------|----------|------|
| `console_ui_dev_loop` | 上游无同名 skill | `保留` | sidecar console 专用开发流程 |
| `diary` | 上游无同名 skill | `保留` | sidecar 独有能力 |
| `page_agent_test` | 上游无同名 skill | `保留` | sidecar page-agent 回归专用 |
| `cron` | 与 upstream 同名，但 `ava` 版增加本地时区、`check_status` / `mark_done` 指导 | `收窄` | 只保留 sidecar 额外动作和时区约束；能回落到 upstream 的说明尽量回落 |
| `github` | 与 upstream 同名，当前内容一致 | `删除` | 没有 sidecar 增量，不应继续 shadow upstream |
| `memory` | 与 upstream 同名，但能力模型已完全分叉：upstream 是 Dream 文件体系，sidecar 是 categorized memory tool | `保留` | 本轮继续保留 sidecar 版；Dream 先兼容接入，不切换到 upstream 记忆语义 |
| `skill-creator` | 与 upstream 同名，当前差异只有轻微文案漂移 | `删除` | 无明确 sidecar 行为差异，保留只会制造影子副本 |
| `summarize` | 与 upstream 同名，当前内容一致 | `删除` | 直接回落到 upstream builtin |
| `tmux` | 与 upstream 同名，但 `ava` 版增加“不要用 tmux 编排 coding agent”的 sidecar 约束 | `收窄` | 只保留这类 sidecar 特有 guardrail；其余说明尽量回落到 upstream |
| `weather` | 与 upstream 同名，当前内容一致 | `删除` | 直接回落到 upstream builtin |

### 6.4 Post-Merge 开发顺序

1. 先按本轮 merge 实际命中的文件 / patch 热区处理，不做泛化清理。
2. 第一优先级永远是运行闭环：`patch` 能注册、`tools` 能注入、`skills` 能发现与加载、核心调用链不报错。
3. Dream 按“先兼容、不切真源”执行：先让 upstream Dream / Consolidator / cron 路径可运行，但不在本轮要求接管 `categorized_memory` 或替代 sidecar 现有记忆链。
4. 只有在运行闭环稳定后，才处理 `github` / `summarize` / `weather` / `skill-creator` 这类 shadow skill 的删除，或 `context/channel/transcription/onboard` 的收窄。
5. `loop_patch`、`console_patch`、`tools_patch`、`storage_patch`、`page_agent` 相关能力默认视为 sidecar 主体，不以“和 upstream 同域”为由误删。
6. 真正适合独立 upstream PR 的，不是整块 sidecar patch，而是其中被证明通用且不影响 sidecar 当前运行闭环的窄切片，例如通用 bugfix、hook seam、或文档/模板同步点。

## 7. Review Verdict

- Spec coverage: `merge shared files / runtime continuity / Dream compat / overlay drift 已覆盖`
- Behavior check: `206 项定向 pytest 通过；ava startup/status smoke 通过`
- Regression risk: `中；Matrix / 全量外部集成未跑，Batch C 仍保留增量复核空间`
- Module Spec 需更新: `可选：context_patch_spec / tools_patch_spec / skills_patch_spec`
- Follow-ups: `Dream 真源统一、shadow skills 收窄/删除、Batch C 增益区增量复核`

## 8. Plan-Execution Diff

- Any deviation from plan: `nanobot/templates/TOOLS.md 未产生文本冲突，真正需要额外对齐的是 ava/templates/TOOLS.md；运行闭环验证优先级高于 patch 收窄治理`
