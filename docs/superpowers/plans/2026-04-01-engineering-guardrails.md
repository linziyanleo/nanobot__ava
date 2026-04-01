# Engineering Guardrails Implementation Plan

> 面向本次演讲的开发补完计划。目标不是再堆概念，而是把“Sidecar + Monkey Patch 有工程化护栏”这件事补成可演示、可验证、可复盘的事实。

## 目标

为 `nanobot__ava` 增加 4 类硬约束，并先修复当前已暴露的基线漂移问题：

1. 阻止误改 `nanobot/`，但保留“上游 bugfix / upstream PR prep”例外通道。
2. 防止 `ava/forks/config/schema.py` 与上游 schema 静默漂移。
3. 防止 patch 规范只停留在文档里，缺少自动校验。
4. 防止 Spec / 文档 / 测试 / 实现再次失同步。

## 当前缺口

在开始新增 guardrails 之前，仓库当前存在几类会直接削弱演讲可信度的问题：

- `tests/patches/test_bus_patch.py` 仍按 callback API 断言，而 `ava/patches/bus_patch.py` 已切到 queue API。
- `tests/patches/test_schema_patch.py` 和 `ava/patches/a_schema_patch.py` 仍提及 `voice_model`，但 fork schema 已移除该字段。
- `.specanchor/modules/module-index.md` 尚未覆盖 `skills_patch.py` 和 `transcription_patch.py`。
- 规范要求存在 `ava/UPSTREAM_VERSION`，但仓库中尚未落地。
- 当前 patch 规范有文档、有测试要求，但缺少结构校验、运行时契约校验、Spec 同步校验。

结论：必须先把基线修绿，再谈新增 guardrails。否则只是把护栏搭在红灯状态上。

## 设计原则

- 先修基线，再加护栏。
- 护栏以仓库内可执行文件为准，不依赖口头流程。
- 本地拦截、CI 拦截、测试拦截三层分工明确，避免重复但保留冗余。
- 允许上游例外场景，但例外必须留下机器可读痕迹。
- 演讲用表述只引用已落地能力，不引用“计划中能力”。

## 分层架构

- 第 0 层：Baseline Stabilization
  先把现有红灯测试、过期文档、错误注释修正到一致状态。
- 第 1 层：Repo-tracked Hook
  用版本化的 `.githooks/` 阻止误改 `nanobot/`。
- 第 2 层：CI Diff Guardrail
  在 GitHub Actions 中按 base/head diff 检测 `nanobot/` 改动，并要求例外标记。
- 第 3 层：Contract Tests
  检查 schema drift、patch 结构、patch 运行时契约、Spec 同步。
- 第 4 层：Evidence
  产出一份可直接用于演讲的“红转绿”证据文档。

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `tests/patches/test_bus_patch.py` | 修改 | 对齐 queue API 的现状 |
| `tests/patches/test_schema_patch.py` | 修改 | 移除对 `voice_model` 的过期断言 |
| `ava/patches/a_schema_patch.py` | 修改 | 修正文档字符串中的过期字段说明 |
| `.specanchor/modules/bus_console_listener_spec.md` | 修改 | 对齐 queue API 的 bus module spec |
| `.specanchor/modules/module-index.md` | 修改 | 补齐新增 patch 的索引 |
| `.specanchor/modules/schema_patch_spec.md` | 修改 | 修正 fork schema 的字段描述 |
| `.githooks/pre-commit` | 创建 | 版本化 pre-commit hook |
| `scripts/install-hooks.sh` | 创建 | 安装 `.githooks` 为仓库 hooksPath |
| `tests/guardrails/test_nanobot_guardrail.py` | 创建 | 校验 hook 脚本和 guardrail 辅助函数 |
| `tests/guardrails/test_schema_drift.py` | 创建 | schema 漂移、重复类定义、关键字段签名一致性 |
| `tests/guardrails/test_patch_structure.py` | 创建 | patch AST 结构合规性检查 |
| `tests/guardrails/test_patch_runtime_contracts.py` | 创建 | patch 幂等、降级、重复应用契约检查 |
| `tests/guardrails/test_spec_sync.py` | 创建 | patch / tests / Spec / module-index 一致性检查 |
| `ava/UPSTREAM_VERSION` | 创建 | 记录最后验证通过的上游 commit hash |
| `.github/workflows/ci.yml` | 修改 | 增加 guardrails job，并在上游目录变更时检查例外条件 |
| `README.md` 或 `CONTRIBUTING.md` | 修改 | 补充 hook 安装说明 |
| `docs/superpowers/evidence/engineering-guardrails-demo.md` | 创建 | 演讲证据文档 |

## Task 0: Baseline Stabilization

**目标：** 在新增 guardrails 前先把仓库从“已知不一致”修回到可验证基线。

### 范围

- 修复 `bus_patch` 测试与实现不一致。
- 修复 `bus_console_listener_spec.md` 与 queue API 不一致。
- 修复 `voice_model` 相关的过期测试和注释。
- 补齐 `.specanchor/modules/module-index.md` 中缺失的 patch 条目。
- 修正 schema 相关 Spec 中与当前实现不一致的字段描述。

### 具体任务

- [x] 将 `tests/patches/test_bus_patch.py` 改为断言 queue API：
  - `register_console_listener(session_key)` 返回 `asyncio.Queue`
  - `dispatch_to_console_listener()` 将消息写入队列
  - 移除对 callback 签名的旧断言
- [x] 更新 `.specanchor/modules/bus_console_listener_spec.md`，将 callback 语义改为 queue 语义
- [x] 将 `tests/patches/test_schema_patch.py` 中 `voice_model` 从扩展字段断言里移除
- [x] 修正 `ava/patches/a_schema_patch.py` 头部注释，不再宣称 fork 提供 `voice_model`
- [x] 更新 `.specanchor/modules/module-index.md`：
  - 补充 `ava/patches/skills_patch.py`
  - 补充 `ava/patches/transcription_patch.py`
- [x] 更新 `.specanchor/modules/schema_patch_spec.md`，移除过期字段说明
- [x] 运行基线验证：

```bash
uv run pytest tests/patches -q
```

### 完成标准

- `tests/patches/` 全绿。
- patch 头注释、模块 Spec、测试断言与当前实现一致。

## Task 1: Repo-tracked Hook

**目标：** 不再直接生成 Git 默认 hooks 目录中的 `pre-commit` 作为“黑盒产物”，而是把 hook 脚本纳入仓库版本控制。

### 方案

- 在仓库中新增 `.githooks/pre-commit`
- 通过 `scripts/install-hooks.sh` 执行：

```bash
git config core.hooksPath .githooks
```

- hook 默认阻止任何 staged 的 `nanobot/` 改动
- 仅当显式设置 `ALLOW_NANOBOT_PATCH=1` 时允许放行

### 具体任务

- [x] 创建 `.githooks/pre-commit`
- [x] 创建 `scripts/install-hooks.sh`
- [x] hook 必须支持如下逻辑：
  - 若 `ALLOW_NANOBOT_PATCH=1`，打印 bypass 提示并放行
  - 否则检查 `git diff --cached --name-only -- nanobot/`
  - 若命中，阻止 commit 并输出受影响文件列表
- [x] 在 `tests/guardrails/test_nanobot_guardrail.py` 中校验：
  - `.githooks/pre-commit` 存在
  - `scripts/install-hooks.sh` 存在
  - hook 内容包含 `ALLOW_NANOBOT_PATCH`
  - hook 内容明确检查 `nanobot/`

### 不做的事

- 不尝试在 pytest 中验证真实 pre-commit 行为。
  原因：这属于 Git 进程行为，测试“脚本内容 + CI 备用层”即可。

## Task 2: CI Diff Guardrail + Exception Path

**目标：** 在 GitHub Actions 中检查本次变更范围是否触碰 `nanobot/`，并要求机器可读例外痕迹。

### 当前计划需要修正的点

- 不能用 `git diff HEAD~1 HEAD`，这只覆盖单 commit push。
- 不能复用“staged files”语义，CI 里没有这个概念。

### 新方案

- 在 `.github/workflows/ci.yml` 新增 `guardrails` job
- 使用 GitHub event 提供的 base/head SHA 计算 diff
- 若 diff 包含 `nanobot/` 改动，则必须同时满足：
  - `ava/UPSTREAM_VERSION` 被修改
  - commit message 或 PR 描述包含 `[allow-nanobot-patch]`

### 具体任务

- [x] 新增 `guardrails` job
- [x] checkout 使用 `fetch-depth: 0`
- [x] 区分事件类型：
  - `pull_request`：使用 `github.event.pull_request.base.sha` 和 `github.event.pull_request.head.sha`
  - `push`：使用 `github.event.before` 和 `github.sha`
- [x] 编写 shell 校验逻辑：
  - 计算变更文件列表
  - 若无 `nanobot/` 改动，直接通过
  - 若有 `nanobot/` 改动，则校验：
    - `ava/UPSTREAM_VERSION` 也在变更列表中
    - PR body、PR title 或最近 commit message 含 `[allow-nanobot-patch]`
- [x] 在失败输出里明确提示允许的例外场景：
  - upstream bugfix
  - upstream feature
  - PR prep for upstream

### 备注

- 本地 hook 用环境变量 bypass。
- CI 用 message / PR metadata bypass。
- 两者故意分离，避免开发者误以为本地绕过等于 CI 也会放行。

## Task 3: Fork Schema Drift Detection

**目标：** 防止 fork schema 与上游 schema 静默漂移，不只检查“字段在不在”，还要检查“结构有没有明显坏掉”。

### 当前计划需要增强的点

- 仅比较字段集合不够。
- 抓不到重复类定义。
- 抓不到关键共享字段的 annotation/default 漂移。

### 测试拆分

创建 `tests/guardrails/test_schema_drift.py`，至少包含以下检查：

- [ ] `test_schema_files_exist`
- [x] `test_schema_files_exist`
  - 上游 schema 和 fork schema 文件可读
- [x] `test_no_duplicate_class_defs`
  - 同一文件内不允许出现重复 `ClassDef`
  - 当前 `ava/forks/config/schema.py` 中的重复 `MatrixConfig` 应先修复或显式处理
- [x] `test_no_unacknowledged_upstream_removals`
  - fork 删除上游字段时，必须写入 `INTENTIONAL_REMOVALS`
- [x] `test_no_unacknowledged_upstream_additions`
  - 上游新增字段时，fork 必须同步或在例外清单里解释
- [x] `test_shared_field_annotations_match_for_critical_classes`
  - 对关键类做 annotation 一致性检查：
    - `AgentDefaults`
    - `GatewayConfig`
    - `ToolsConfig`
    - `ProvidersConfig`
    - `MCPServerConfig`
- [x] `test_shared_field_defaults_match_for_critical_classes`
  - 对关键共享字段的默认值做 AST 层面的保守比较

### 例外机制

- 允许存在 `INTENTIONAL_REMOVALS`
- 每个例外必须写明原因
- 不允许无理由删除

## Task 4: Patch Structure AST Validator

**目标：** 把 patch 规范里最容易静态检查的部分落成 AST 校验。

### 要检查的内容

- [x] 模块级 docstring 存在
- [x] 至少有一个 `apply_*_patch() -> str`
- [x] 存在 `register_patch(...)`
- [x] 存在拦截点检查
  - `hasattr(...)`
  - 或等价的存在性检查，如 `Path.exists()`、`getattr(..., default)` 加明确 skip 分支
- [x] 每个 patch 都有对应 `tests/patches/test_*.py`

### 需要修正原计划的点

- 不能把“必须出现 `hasattr()`”写死。
  当前 [a_schema_patch](/Users/fanghu/Documents/Test/nanobot__ava/ava/patches/a_schema_patch.py) 用的是 fork 文件存在性检查，不是 `hasattr()`。
- AST 测试只负责“结构合规”，不宣称能证明幂等和降级行为。

## Task 5: Patch Runtime Contract Tests

**目标：** 把文档里的幂等、降级、重复应用等约束补成运行时测试。

创建 `tests/guardrails/test_patch_runtime_contracts.py`，重点覆盖：

- [x] `test_apply_all_patches_twice_does_not_crash`
  - 连续调用 `apply_all_patches()` 两次不应抛异常
- [x] `test_patch_registry_has_expected_patch_names`
  - patch 注册名与实际文件集合一致
- [x] `test_context_patch_is_idempotent`
  - 二次 apply 返回 skipped 或等价结果
- [x] `test_schema_patch_is_idempotent`
  - 二次 apply 返回 skipped
- [x] `test_missing_intercept_points_degrade_gracefully_for_selected_patches`
  - 至少挑 2 到 3 个 patch 做 monkeypatch 验证：
    - `console_patch`
    - `context_patch`
    - `transcription_patch`
- [x] `test_apply_all_patches_matches_documented_count`
  - 实际发现的 patch 数量与 Spec 索引一致

### 说明

- 这一层不是替代 `tests/patches/`
- 这一层用于补“全局契约”，抓 patch 系统级退化

## Task 6: Spec / Doc Sync + UPSTREAM_VERSION

**目标：** 防止“实现已变，Spec 和说明文档还停在旧时代”。

### 6.1 UPSTREAM_VERSION

- [x] 创建 `ava/UPSTREAM_VERSION`
- [x] 文件格式建议：

```text
<upstream_commit_sha>
# verified_at: 2026-04-01
# note: last full patch test baseline
```

- [x] 在 `README.md` 或 `CONTRIBUTING.md` 说明其用途
- [x] 在 CI guardrails 中加入规则：
  - 若 `nanobot/` 有变更，则 `ava/UPSTREAM_VERSION` 必须同步修改

### 6.2 Spec / Doc Sync Test

创建 `tests/guardrails/test_spec_sync.py`，至少包含：

- [x] `test_module_index_covers_all_patch_files`
  - `ava/patches/*_patch.py` 必须全部出现在 `.specanchor/modules/module-index.md`
- [x] `test_patch_specs_reference_existing_files`
  - module index 中列出的 patch 文件必须真实存在
- [x] `test_schema_patch_spec_matches_current_field_set`
  - schema Spec 中提到的扩展字段要与 fork 当前实现一致
- [x] `test_plan_and_repo_hook_paths_match`
  - 计划文档里写的是 `.githooks/pre-commit`，不能再退回到 Git 默认 hooks 目录里的旧路径写法

### 备注

- 这是演讲最关键的补完之一。
- 观众最容易抓到的就是“你说有约束，但文档已经过期”。

## Task 7: README / CONTRIBUTING / Evidence

**目标：** 不只让仓库能跑，还要让演讲可以拿出证据。

### README / CONTRIBUTING

- [x] 在 `README.md` 或 `CONTRIBUTING.md` 增加开发环境约束说明
- [x] 至少包含：
  - 安装 hooks：`bash scripts/install-hooks.sh`
  - 例外场景说明
  - `ava/UPSTREAM_VERSION` 的更新要求

### 演讲证据文档

创建 `docs/superpowers/evidence/engineering-guardrails-demo.md`，记录 3 个可复现演示：

- [x] Demo 1：尝试提交 `nanobot/` 修改，被 hook 拦截
- [x] Demo 2：上游 schema 新增字段时，`test_schema_drift.py` 报警
- [x] Demo 3：patch 缺少结构要件或 Spec 未同步时，guardrail 测试报错

每个 demo 都记录：

- 触发条件
- 执行命令
- 预期失败输出
- 修复后转绿截图或文本

## 推荐执行顺序

1. Task 0: Baseline Stabilization
2. Task 1: Repo-tracked Hook
3. Task 2: CI Diff Guardrail + Exception Path
4. Task 3: Fork Schema Drift Detection
5. Task 4: Patch Structure AST Validator
6. Task 5: Patch Runtime Contract Tests
7. Task 6: Spec / Doc Sync + UPSTREAM_VERSION
8. Task 7: README / CONTRIBUTING / Evidence

## 验收标准

完成后，以下约束应全部生效：

| 约束 | 验证方式 | 状态 |
|------|----------|------|
| `tests/patches/` 基线全绿 | `uv run pytest tests/patches -q` | ✅ 已完成 |
| 本地提交 `nanobot/` 改动时默认被拦截 | `.githooks/pre-commit` | ✅ 已完成 |
| 本地存在明确绕过机制 | `ALLOW_NANOBOT_PATCH=1 git commit ...` | ✅ 已完成 |
| CI 检测到 `nanobot/` 改动时要求例外痕迹 | `.github/workflows/ci.yml` guardrails job | ✅ 已完成 |
| schema 上游新增 / 删除 / 重复定义可被发现 | `tests/guardrails/test_schema_drift.py` | ✅ 已完成 |
| patch 缺 docstring / apply / register / test coverage 时 CI 失败 | `tests/guardrails/test_patch_structure.py` | ✅ 已完成 |
| patch 系统级幂等 / 降级契约可被发现 | `tests/guardrails/test_patch_runtime_contracts.py` | ✅ 已完成 |
| patch / Spec / module-index / 计划文档不一致时 CI 失败 | `tests/guardrails/test_spec_sync.py` | ✅ 已完成 |
| `nanobot/` 有改动时必须同步更新 `ava/UPSTREAM_VERSION` | guardrails job + repo file | ✅ 已完成 |
| 演讲可以展示“护栏触发 -> 修复 -> 转绿”证据 | `docs/superpowers/evidence/engineering-guardrails-demo.md` | ✅ 已完成 |

## 非目标

本计划明确不包含以下高成本事项：

- 不将 `ava/forks/config/schema.py` 立即重构为继承式实现
- 不在本计划内重做整个 patch 架构
- 不尝试用 AST 静态分析替代所有运行时测试
- 不把演讲文案直接写死成“无限进化”叙事

## 演讲表述约束

在这些 guardrails 落地并转绿之前，演讲中可以使用的表述上限是：

- “我们为 Sidecar + Monkey Patch 加了工程化护栏”
- “这些护栏覆盖了误改上游、fork 漂移、patch 结构和文档同步”

不应提前使用的表述：

- “已经完全稳住底盘”
- “自我进化闭环已经成熟”
- “可以无痛追上游且零维护成本”

## 备注

这份计划故意把“新增 guardrails”和“修复当前基线漂移”绑在一起。

原因很简单：

- 如果不先修基线，guardrails 上线后第一件事就是把现有仓库打红。
- 如果不把 Spec / 测试 / 注释一起纳入约束，演讲时最容易被挑出来的不是架构，而是细节自相矛盾。

先把仓库变成一份能自证的样品，再谈方法论，才站得住。
