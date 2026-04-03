---
specanchor:
  level: task
  task_name: "合并 upstream main 并复核 sidecar patch 更新项"
  author: "@Codex"
  assignee: "@Codex"
  reviewer: "@Ziyan Lin"
  created: "2026-04-03"
  status: "in_progress"
  last_change: "补充 global spec：明确 upstream 集成例外可更新 nanobot/，并记录 ALLOW_NANOBOT_PATCH=1 作为 commit guard 放行参数"
  related_modules:
    - ".specanchor/modules/schema_patch_spec.md"
    - ".specanchor/modules/onboard_patch_spec.md"
    - ".specanchor/modules/channel_patch_spec.md"
    - ".specanchor/modules/console_patch_spec.md"
    - ".specanchor/modules/context_patch_spec.md"
    - ".specanchor/modules/loop_patch_spec.md"
  related_global:
    - ".specanchor/global/architecture.md"
    - ".specanchor/global-patch-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "REVIEW"
  branch: "refactor/sidecar"
---

# SDD Spec: 合并 upstream main 并复核 sidecar patch 更新项

## 0. Open Questions

- [x] 当前 worktree 上已有未提交改动，是否会与 upstream merge 命中同一路径导致 merge 前必须额外处理
- [x] 最新 `upstream/main` 相比当前 `HEAD` 是否真的需要 merge，还是仅需更新追踪信息
- [x] 本轮 upstream 变更命中了哪些 patch 热区，哪些 patch / spec / 测试需要同步

## 1. Requirements (Context)

- **Goal**: 拉取最新 `upstream/main` 并合并到 `refactor/sidecar`，随后依据 `.specanchor/patch_map.md` 和 `.specanchor/global-patch-spec.md` 判断需要更新的 patch、spec、测试与 TODO。
- **In-Scope**:
  - fetch 最新 `upstream/main` 并重算 merge-base / 左右分叉
  - 执行 merge（若确有必要且 worktree 允许）
  - 基于 upstream 改动的 `nanobot/` 触点，对照 patch_map 识别需要更新的 patch 热区
  - 修复本轮 merge 直接带来的 sidecar 漂移，并同步最小必要的 spec / 测试
- **Out-of-Scope**:
  - 与本轮 upstream 触点无关的 sidecar 重构
  - 无明确例外理由前直接修改 `nanobot/`
  - 把历史 TODO 全量清空
- **Schema**: `sdd-riper-one`（涉及 git 合并、跨 patch 热区判断与可能的运行时/测试回归，不适合走轻量流程）

## 1.1 Context Sources

- Requirement Source:
  - 用户请求：`合并上游main分支，参考patch_map.md和 .specanchor/global-patch-spec.md ，看看有哪些需要更新的`
- Design Refs:
  - `.specanchor/global/architecture.md`
  - `.specanchor/global-patch-spec.md`
  - `.specanchor/patch_map.md`
- Extra Context:
  - 项目级约束：默认禁止修改 `nanobot/`，sidecar 入口为 `python -m ava`
  - merge 治理经验：fetch 后必须重算 merge-base 和左右分叉，不能沿用旧结论

## 1.5 Codemap Used (Feature/Project Index)

- Codemap Mode: `targeted-research`
- Bundle File: `N/A`
- Key Index:
  - git / upstream 集成：`git fetch upstream main`、`git merge-base`、`git log --left-right`
  - patch 治理工件：`.specanchor/patch_map.md`、`.specanchor/TODO.md`
  - 高热区模块：
    - `ava/forks/config/schema.py`
    - `ava/patches/c_onboard_patch.py`
    - `ava/patches/channel_patch.py`
    - `ava/patches/console_patch.py`
    - `ava/patches/context_patch.py`
    - `ava/patches/loop_patch.py`

## 1.6 Context Bundle Snapshot (Lite)

- Bundle Level: `Lite`
- Key Facts:
  - 当前分支为 `refactor/sidecar`
  - worktree 已有非本任务文件改动：`ava/templates/TOOLS.md` 与一个未跟踪 task spec
  - `.specanchor/patch_map.md` 已把 `schema` / `onboard` / `channel` / `console` / `context` / `loop` 标为本轮最可能命中的热区
- Open Questions:
  - 最新 upstream 这次是否又命中新的触点，超出当前 patch_map 的判断

## 2. Research Findings

### 2.1 分叉关系与 merge 必要性

- `git fetch upstream main` 后，`upstream/main` 从 `63d646f7` 前进到 `7113ad34`。
- 当前 `HEAD` 为 `bd1ff36d`，新的 `merge-base` 仍是 `63d646f7`，说明 sidecar 分支和 upstream 都各自前进了，必须做真实 merge，不能判定为“无需 merge”。
- 现有 worktree 脏文件只有 `ava/templates/TOOLS.md` 和未跟踪的 task spec；它们不在本轮 upstream 命中的路径中，因此不构成 merge 前阻塞。

### 2.2 本轮 upstream 命中的 patch 热区

- `git diff --name-only $(git merge-base HEAD upstream/main)..upstream/main -- nanobot/` 命中了：
  - `nanobot/agent/context.py`
  - `nanobot/agent/loop.py`
  - `nanobot/cli/commands.py`
  - `nanobot/config/schema.py`
  - `nanobot/session/manager.py`
  - `nanobot/providers/base.py`
  - 以及一组 tool / provider / api 相关文件
- 对照 `.specanchor/patch_map.md` 后，本轮需要优先复核的是：
  - `context_patch`
  - `loop_patch`
  - `console_patch`
  - `a_schema_patch`
  - `storage_patch`

### 2.3 唯一 merge 冲突与结论

- 唯一文本冲突出现在 `nanobot/agent/context.py`。
- 冲突两侧语义：
  - 本地分支保留了 `_sanitize_history()`，用于清理 trailing incomplete assistant/tool-call history；
  - upstream 在 `build_messages()` 中新增了“连续同角色消息合并”逻辑。
- 最小正确解不是二选一，而是：
  - 保留 `_sanitize_history()`；
  - 采用 upstream 的 `messages[-1].role == current_role` 时合并 content 的返回路径。
- 该改动属于 upstream merge reconciliation，不是新增 sidecar 定制。

### 2.4 回归结果

- `uv run pytest tests/patches tests/guardrails -q`：`91 passed`
- `uv run pytest tests/agent/test_context_prompt_cache.py tests/agent/test_loop_save_turn.py tests/agent/test_runner.py tests/cli/test_commands.py tests/providers/test_cached_tokens.py tests/providers/test_openai_responses.py tests/test_openai_api.py -q`：`161 passed`
- 结论：本轮 merge 后不需要额外修改 sidecar patch 代码；需要更新的是 upstream 基线与 patch 治理文档。

## 3. Innovate (Optional: Options & Decision)

### Decision

- Selected: 保留现有 patch 代码，仅解决 `nanobot/agent/context.py` merge 冲突，并同步更新 `UPSTREAM_VERSION` 与 `.specanchor` 治理文档。
- Why:
  - patch / guardrail 基线和 targeted runtime/provider 回归均已通过；
  - upstream 对 `context_patch`、`loop_patch`、`console_patch` 的影响目前属于“overlap 增加但尚未打断契约”，更适合记录在 patch map / TODO，而不是为了“显得跟上游同步”去硬改 patch。

## 4. Plan (Contract)

### 4.1 File Changes

- `ava/UPSTREAM_VERSION`
  - 若本轮完成 merge 且验证通过，同步记录最新 upstream commit
- 受影响的 `ava/patches/*` / `ava/forks/*`
  - 仅更新被 upstream 变更真实命中的 patch 热区
- `tests/patches/*` / `tests/guardrails/*`
  - 补受影响 patch 的最小必要回归
- `.specanchor/patch_map.md` / `.specanchor/TODO.md` / 相关 module spec
  - 仅在本轮 merge 判断已发生变化时同步

### 4.2 Implementation Checklist

- [x] 1. fetch 最新 `upstream/main`，重算 `merge-base` 与左右分叉，判断是否需要真实 merge
- [x] 2. 在不破坏现有 worktree 改动的前提下完成 merge 或明确阻塞点
- [x] 3. 按 `patch_map.md` 对照 upstream 触及的 `nanobot/` 文件，列出需要复核的 patch 热区
- [x] 4. 修复 merge 直接带来的代码 / spec / 测试漂移
- [x] 5. 回归受影响测试，并更新 `UPSTREAM_VERSION` 与相关 `.specanchor` 工件

## 5. Execute Log

- [x] Step 0: 读取 `.specanchor/global-patch-spec.md`、`.specanchor/patch_map.md`、`.specanchor/TODO.md`、相关 module spec 与既有 merge 记忆，确认本轮必须先 fetch 再重算 merge-base。
- [x] Step 1: 执行 `git fetch upstream main`，确认 `upstream/main` 更新到 `7113ad34`，新的 merge-base 仍为 `63d646f7`，因此必须真实 merge。
- [x] Step 2: 在不动现有 `ava/templates/TOOLS.md` 与未跟踪 task 文件的前提下执行 `git merge --no-ff upstream/main`；merge 过程中仅 `nanobot/agent/context.py` 发生文本冲突。
- [x] Step 3: 解决 `nanobot/agent/context.py` 冲突：保留本地 `_sanitize_history()`，同时采用 upstream 的同角色消息 content merge 逻辑。
- [x] Step 4: 按 patch map 复核热区，确认 `context_patch`、`loop_patch`、`console_patch`、`a_schema_patch`、`storage_patch` 需要更新治理判断，但当前无需改 patch 代码。
- [x] Step 5: 跑基线回归：
  - `uv run pytest tests/patches tests/guardrails -q`
  - `uv run pytest tests/agent/test_context_prompt_cache.py tests/agent/test_loop_save_turn.py tests/agent/test_runner.py tests/cli/test_commands.py tests/providers/test_cached_tokens.py tests/providers/test_openai_responses.py tests/test_openai_api.py -q`
- [x] Step 6: 更新 `ava/UPSTREAM_VERSION`、`.specanchor/patch_map.md`、`.specanchor/TODO.md`、`context_patch_spec.md`、`schema_patch_spec.md`、`loop_patch_spec.md`。
- [x] Step 7: 运行 `uv run pytest tests/guardrails/test_spec_sync.py -q` 与 `git diff --check`，均通过。
- [x] Step 8: 尝试运行 `bash scripts/specanchor-check.sh task ...`，发现当前仓库不存在该脚本，无法执行 task freshness 脚本检查。
- [x] Step 9: 更新 `.specanchor/global/architecture.md` 与 `.specanchor/global-patch-spec.md`，明确 upstream merge / upstream fix 场景可更新 `nanobot/`，并记录 `ALLOW_NANOBOT_PATCH=1 git commit ...` 为受限放行参数。

## 6. Review Verdict

- Merge status: `upstream/main` 已成功并入当前 index；唯一冲突已解决。
- Patch health: `tests/patches` 与 `tests/guardrails` 全通过，说明现有 sidecar 拦截点未被这次 upstream 变更打断。
- Targeted runtime health: `context` / `loop` / `cli` / `provider` / `api` 相关 targeted 测试通过，说明这次 conflict resolution 没引入回归。
- Spec sync: `UPSTREAM_VERSION` 与 patch 治理文档已同步到最新 upstream 基线。
- Global rule sync: global spec 已补充 upstream 集成例外，避免“文档写绝对禁止”与实际 merge guard 放行流程冲突。
- Residual risk:
  - `context_patch` 已进入“部分上游覆盖”状态，下一次 upstream 若继续把 sanitize 下沉到核心层，需要收窄 provider wrapper；
  - `loop_patch` 需继续盯住 runtime checkpoint 与新增 AgentDefaults 参数面；
  - 当前仓库缺少 `scripts/specanchor-check.sh`，所以 task freshness 只能靠 guardrail/spec sync，而不是脚本检查。

## 7. Plan-Execution Diff

- 原计划中的“修复 merge 直接带来的代码 / spec / 测试漂移”最终只需要一个上游文件冲突解法和一组治理文档更新，没有新增 patch 代码。
- 偏差原因不是计划错误，而是 patch / guardrail 回归比预期更健康：本轮真正变化的是 overlap 判断，而不是 sidecar 运行时契约。
