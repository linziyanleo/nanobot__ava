---
specanchor:
  level: task
  task_name: "schema 继承重构与 onboard 配置结构同步"
  author: "@Ziyan Lin"
  assignee: "@Ziyan Lin"
  reviewer: "@Ziyan Lin"
  created: "2026-04-01"
  status: "in_progress"
  last_change: "完成真实 ~/.nanobot refresh + wizard no-change 实机回归：兼容字段保留、新结构补齐，随后已恢复原 config.json/extra_config.json"
  related_modules:
    - ".specanchor/modules/ava-patches-a_schema_patch.spec.md"
    - ".specanchor/modules/ava-patches-b_config_patch.spec.md"
    - ".specanchor/modules/ava-patches-c_onboard_patch.spec.md"
  related_global:
    - ".specanchor/global/architecture.md"
    - ".specanchor/global-patch-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "REVIEW"
  branch: "refactor/sidecar"
---

# SDD Spec: schema 继承重构与 onboard 配置结构同步

## 0. Open Questions

- [x] 可以在 `ava/` 内完成 schema 继承重构并保持 `nanobot/` 零修改；当前无需 `nanobot/` 例外改动。
- [x] 本轮不额外收敛 `memoryWindow` 等历史字段口径，只保证继承重构后的结构正确落盘，并保持既有 sidecar 扩展字段兼容。

## 1. Requirements (Context)

- **Goal**: 梳理并落地 config schema 的继承式重构，同时确保 `onboard` 初始化/刷新时写出的 config 结构与新 schema 一致。
- **In-Scope**:
  - 分析 `a_schema_patch` / `b_config_patch` / `ava/forks/config/schema.py` 的现状与耦合点
  - 分析 `onboard` 初始化与 config load/save/migration 路径
  - 实现 schema 结构调整与初始化配置同步
  - 补齐/更新受影响测试与 Spec
- **Out-of-Scope**:
  - 与本次 schema/config 结构无关的 patch 整理
  - 无明确例外理由前直接修改 `nanobot/`
  - 大范围重写 channel / tool / console 配置系统
- **Schema**: `sdd-riper-one`（虽然包含“继承重构”，但同时涉及 `onboard` 生成配置结构的外部行为变化，需要标准 Research → Plan → Execute 流程而非“行为必须不变”的纯 refactor 流程）

## 1.1 Context Sources

- Requirement Source:
  - 用户请求：查看 `docs/superpowers/plans/2026-04-01-engineering-guardrails.md` 中的 schema 继承重构，并同步 `onboard` 初始化 config 结构
- Design Refs:
  - `.specanchor/global/architecture.md`
  - `.specanchor/global-patch-spec.md`
  - `.specanchor/modules/ava-patches-a_schema_patch.spec.md`
  - `.specanchor/modules/ava-patches-b_config_patch.spec.md`
- Chat/Business Refs:
  - `docs/superpowers/plans/2026-04-01-engineering-guardrails.md`
- Extra Context:
  - 项目级约束：优先在 `ava/` 内完成，非例外场景不改 `nanobot/`

## 1.5 Codemap Used (Feature/Project Index)

- Codemap Mode: `targeted-research`
- Codemap File: `N/A（先基于 Spec 与定向文件检索）`
- Key Index:
  - Entry Points / Architecture Layers:
    - `ava/patches/a_schema_patch.py`
    - `ava/patches/b_config_patch.py`
    - `ava/forks/config/schema.py`
    - `nanobot.config.loader` / `onboard` 命令链路
  - Core Logic / Cross-Module Flows:
    - fork schema 注入 → config load/save → onboard 初始化/刷新
  - Dependencies / External Systems:
    - Pydantic schema 定义
    - 本地 `config.json` 生成/迁移路径

## 1.6 Context Bundle Snapshot (Lite)

- Bundle Level: `Lite`
- Bundle File: `N/A`
- Key Facts:
  - `a_schema_patch` 当前通过 fork 完整替换 `nanobot.config.schema`
  - `b_config_patch` 是 fork 不可用时的降级字段注入方案
  - 用户明确要求 `onboard` 初始化时同步更新 config 结构，不能只改 schema 定义
- Open Questions:
  - 继承重构是否仅发生在 fork schema 内，还是会影响 patch 边界与 loader 行为

## 2. Research Findings

### 2.1 代码事实

- `ava/patches/a_schema_patch.py` 当前通过 `sys.modules["nanobot.config.schema"]` 完整替换 schema 模块，并同步覆盖 `nanobot.config.loader.Config` 引用；`python -m ava` 启动时会先执行该 patch，再进入 `nanobot.cli.commands.app`。
- `ava/forks/config/schema.py` 目前本质上是“手拷上游 schema + Sidecar 扩展”，不是继承式实现，因此上游一旦新增字段，fork 需要手工跟进，漂移面很大。
- 当前 fork 已确认存在多处结构漂移：
  - `ProvidersConfig` 缺少 `mistral`、`ollama`、`ovms`、`stepfun`、`byteplus`、`byteplus_coding_plan`、`volcengine_coding_plan`
  - `MCPServerConfig` 缺少 `type`、`enabled_tools`
  - `WebSearchConfig` 缺少 `provider`、`base_url`
  - `ChannelsConfig` 未继承上游 `extra="allow"` 语义
- 在 patched runtime 下，`Config.model_validate({"channels": {"myplugin": {"enabled": true}}})` 会静默丢弃 `myplugin`；`tools.web.search.provider/baseUrl` 也会在 round-trip 后被丢弃。这说明当前 fork 不只是“文档漂移”，而是已经影响配置兼容性。
- `nanobot onboard` 的非 wizard 路径是：
  - 现有配置：`load_config()` -> `save_config()` -> `_onboard_plugins()`
  - 新配置：`Config()` -> `save_config()` -> `_onboard_plugins()`
- `nanobot.cli.onboard.run_onboard()` 的 wizard 路径依赖 `type(model).model_fields` 递归展示字段，并最终通过 `model_dump(by_alias=True)` 落盘。因此 schema 结构会直接决定 wizard 中可见字段和最终写出的 JSON 结构。

### 2.2 约束与结论

- 本任务可以在 `ava/` 内完成，不需要修改 `nanobot/`：
  - `a_schema_patch` 已经是稳定入口
  - `load_config/save_config/onboard` 在 `python -m ava` 下会天然消费被替换后的 `Config`
- 因为 `onboard refresh` 和 `wizard save` 都依赖当前 `Config` 的 `model_validate/model_dump`，所以“schema 继承重构”和“onboard 配置结构同步”本质上是同一条链路，优先级不能拆开。
- 最简有效方案不是另写一个复杂的 `onboard` 交互 patch，而是把 fork schema 改成“继承上游 + 最少 override”。这样：
  - 上游新增字段默认继承进来
  - `save_config()` 自动写出新的结构
  - `onboard refresh` 自动补齐可序列化字段
  - wizard 自动展示新的字段树
- 需要单独保留的 Sidecar 本地能力主要是：
  - `ConsoleConfig`
  - `ClaudeCodeConfig`
  - `TokenStatsConfig`
  - Sidecar 扩展字段（如 `vision_model`、`image_gen_model` 等）
  - Sidecar 额外 provider（如 `zenmux`、`yunwu`）

### 2.3 Next Actions

- 将 `ava/forks/config/schema.py` 按“上游类继承 / 复用 + Sidecar 类补充 / override”拆解
- 为 patched runtime 增加“config 序列化 / onboard refresh”验证，确保新结构真实写入 JSON
- 更新 drift / patch / Spec 测试与文档，收敛新的单一事实源

## 3. Innovate (Optional: Options & Decision)

### Option A

- Pros: 仅重构 `ava/forks/config/schema.py` 为继承式实现，让 `load_config/save_config/onboard` 天然复用新结构；不需要侵入 `nanobot/`
- Cons: 需要仔细处理上游类的导入方式，以及少数需要 override 的默认值 / exclude 行为

### Option B

- Pros: 通过新增 `onboard/config` patch 显式改写 CLI 与 loader 行为，定制空间更大
- Cons: 链路更长、维护面更大，而且会把“结构问题”误做成“流程 patch 问题”

### Decision

- Selected: `Option A`
- Why:
  - 当前已经确认 `onboard` 只是 `Config` 的消费者，不是结构定义源
  - 使用继承式 fork 能一次性解决上游字段漂移、plugin channel 丢失、web search 字段 round-trip 丢失等问题
  - 该方案符合项目约束：通过 Sidecar patch 生效，不触碰 `nanobot/`

### Skip (for small/simple tasks)

- Skipped: false
- Reason: 该任务涉及结构设计与数据流边界，先保留方案比较位

## 4. Plan (Contract)

### 4.1 File Changes

- `ava/forks/config/schema.py`
  - 改为基于上游 schema 的继承式实现
  - 保留 Sidecar 本地类与字段
  - 恢复当前 fork 缺失的上游字段与配置结构
- `ava/patches/a_schema_patch.py`
  - 仅在必要时补充文档字符串 / 返回描述，说明 fork 已从“整份复制”切到“继承式 fork”
- `tests/patches/test_schema_patch.py`
  - 增加对继承后共享字段仍存在、Sidecar 扩展字段仍存在的断言
- `tests/config/test_config_migration.py`
  - 增加 patched runtime 下的 `save_config()` / `onboard refresh` 结构断言
- `tests/guardrails/test_schema_drift.py`
  - 更新 drift 基线，使其反映新的继承式事实，移除已不再需要的“缺失字段例外”
- `.specanchor/modules/ava-patches-a_schema_patch.spec.md`
  - 将模块职责从“完整替换手拷 fork”更新为“继承上游 schema 的 fork 注入”

### 4.2 Signatures

- `class AgentDefaults(UpstreamAgentDefaults): ...`
- `class ProvidersConfig(UpstreamProvidersConfig): ...`
- `class ChannelsConfig(UpstreamChannelsConfig): ...`
- `class GatewayConfig(UpstreamGatewayConfig): ...`
- `class ToolsConfig(UpstreamToolsConfig): ...`
- `class Config(UpstreamConfig): ...`
- `def apply_schema_patch() -> str`

### 4.3 Implementation Checklist

- [x] 1. 将 `ava/forks/config/schema.py` 重构为继承式 schema，并保留 Sidecar 扩展字段 / 默认值 / provider 扩展
- [x] 2. 验证 patched runtime 下 `save_config()` 默认输出和 `onboard refresh` 输出都包含新的 config 结构
- [x] 3. 更新 patch / config / drift 相关测试，覆盖 plugin channel 保留、web search round-trip、上游 provider 字段恢复
- [x] 4. 同步更新 `schema_patch` 的 Module Spec
- [x] 5. 按用户“请开发”请求直接进入 Execute；未再等待单独的 `Plan Approved` 字样

## 5. Execute Log

- [x] Step 1: 将 `ava/forks/config/schema.py` 从“手拷上游”改为“继承上游 + 最小 sidecar override”，恢复 `ProvidersConfig` / `MCPServerConfig` / `WebSearchConfig` / `ChannelsConfig` 的共享结构。
- [x] Step 2: 在 `ava/patches/a_schema_patch.py` 注入 `_ava_upstream_schema`，确保 fork 执行期可直接继承已加载的上游 schema，而不是反向导入自己。
- [x] Step 3: 更新 `tests/patches/test_schema_patch.py`、`tests/config/test_config_migration.py`、`tests/guardrails/test_schema_drift.py`，补上 patched runtime 的序列化与 onboard refresh 断言。
- [x] Step 4: 更新 `.specanchor/modules/ava-patches-a_schema_patch.spec.md`，将模块职责同步为“继承式 fork 注入”。
- [x] Step 5: 运行定向验证：
  - `uv run pytest tests/patches/test_schema_patch.py tests/config/test_config_migration.py tests/guardrails/test_schema_drift.py -q`
  - `uv run pytest tests/patches/test_config_patch.py tests/guardrails/test_spec_sync.py -q`
- [x] Step 6: 备份真实家目录 `~/.nanobot` 到 `~/.nanobot.backup.20260402100045` 后运行实机回归：
  - `printf 'n\n' | python -m ava onboard`
  - 结果：命中真实兼容性问题，`config.json` 被 refresh 成更接近上游的新结构，导致旧 sidecar 配置字段被收缩或重写；已用备份恢复原始 `config.json`
  - 证据：`providers.zenmux/yunwu` 丢失，`tools.claudeCode`、`agents.defaults.contextCompression/historySummarizer/heartbeat` 等旧字段未被保留，新增了大量上游默认 provider / channel 字段
- [x] Step 7: 运行 `python -m ava onboard --wizard`
  - 结果：未进入真实交互回归，当前机器缺少可选依赖 `questionary`
  - 恢复确认：`~/.nanobot/config.json` 当前 SHA256 与备份一致
- [x] Step 8: 新增 `ava/patches/c_onboard_patch.py`，只拦截 `onboard` 的 refresh 分支，改为“保留旧字段 + 仅补当前 schema 缺失默认值 + 不固化 extra_config overlay”的兼容写回。
- [x] Step 9: 强化 `a_schema_patch` / fork schema：
  - 在执行 fork 前先把 fork 模块临时注册到 `sys.modules["nanobot.config.schema"]`，修复 Pydantic 前向引用错误绑到上游类的问题
  - 若当前 runtime 已经持有 fork 模块，仅重新绑定 `_ava_fork` 标记与 loader `Config`，不再重复重建类图
  - 为 `Config.model_dump(...)` 增加显式递归 dump，保证 sidecar 扩展字段导出稳定
- [x] Step 10: 新增 `tests/patches/test_onboard_patch.py` 与 import-order 回归断言，并通过：
  - `uv run pytest tests/patches/test_onboard_patch.py tests/patches/test_schema_patch.py tests/config/test_config_migration.py tests/guardrails/test_schema_drift.py -q`
- [x] Step 11: 再次对真实 `~/.nanobot` 做 refresh 回归（2026-04-02）：
  - 新备份：`~/.nanobot.backup.20260402112204`
  - 执行：`printf 'n\n' | python -m ava onboard`
  - 结果：关键旧字段全部保留，`gateway.console` / `api` / `mistral` 等新结构成功补齐，`extra_config.json` 未被固化回 `config.json`
  - 收尾：已将 `~/.nanobot/config.json` 与 `extra_config.json` 恢复到回归前内容，SHA256 与备份一致
- [x] Step 12: 使用虚拟环境依赖补齐后的真实 `wizard` 路径完成 no-change 实机回归（2026-04-02）：
  - 新备份：`~/.nanobot.backup.20260402115244`
  - 执行：`uv run python -m ava onboard --wizard`
  - 操作：在主菜单直接选择 `[S] Save and Exit`，不进入任何子菜单修改字段
  - 结果：`voiceModel`、`agents.defaults.historySummarizer`、`agents.defaults.heartbeat.interval_s`、`tools.claudeCode.enabled`、`channels.telegram.transcriptionApiKey`、`providers.zenmux/yunwu`、`providers.gemini.apiBase` 全部保留；`gateway.console` / `api` / `mistral` 等新结构正常补齐；`extra_config.json` 未被固化回 `config.json`
  - 收尾：已将 `~/.nanobot/config.json` 与 `extra_config.json` 恢复到回归前内容；两者 SHA256 均与备份一致
- [x] Step 13: 补跑整组验证：
  - `uv run pytest tests/patches -q`
  - `uv run pytest tests/config/test_config_migration.py -q`
  - `uv run pytest tests/guardrails -q`
  - `git diff --check`

## 6. Review Verdict

- Spec coverage: 已覆盖 Plan 4.3 的 1-5 项，并补齐了真实 `~/.nanobot` 的 refresh + wizard no-change 回归。
- Behavior check: 旧 sidecar 配置样本回归、真实 `~/.nanobot` refresh 回归、真实 `~/.nanobot` wizard no-change 回归均已通过；`Config.model_validate(...)` / `model_dump(...)` 不再吞掉 `gateway.console` / `heartbeat.phrase1/phrase2` / plugin channel / web search provider/baseUrl 等 fork 字段。
- Regression risk: 低。refresh 与 wizard 保存路径都已有兼容写回层、schema 前向引用修复、定向测试和真实家目录回归保护；当前未再观察到 overlay 固化或旧 sidecar 字段收缩。
- Module Spec 需更新: 已完成，见 `.specanchor/modules/ava-patches-a_schema_patch.spec.md`、`.specanchor/modules/ava-patches-c_onboard_patch.spec.md`
- Follow-ups: 如需继续扩大覆盖，下一步可以补“进入 wizard 子菜单后修改单个字段再保存”的真实交互回归；当前 no-change/save-exit 链路已经闭环。

## 7. Plan-Execution Diff

- Any deviation from plan: 相对原计划新增了 `c_onboard_patch`。原因是“仅靠 schema 继承修正即可让 refresh/save 正常输出”的假设被真实旧配置证伪；因此补了一层极窄的 onboard 兼容写回 patch，先覆盖 refresh，再扩到 wizard save，并同时修复 schema fork 的前向引用绑定问题。
