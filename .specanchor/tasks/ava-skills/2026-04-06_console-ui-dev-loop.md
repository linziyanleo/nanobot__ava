---
specanchor:
  level: task
  task_name: "console_ui_dev_loop 前端开发-回归闭环"
  author: "@codex"
  created: "2026-04-06"
  status: "review"
  last_change: "已实现 v1 最小闭环资产：新增 console_ui_dev_loop skill、page_agent JSON 输出、skill 收口与定向测试"
  related_modules:
    - ".specanchor/modules/ava-tools-claude_code.spec.md"
    - ".specanchor/modules/ava-tools-codex.spec.md"
    - ".specanchor/modules/ava-tools-page_agent.spec.md"
    - ".specanchor/modules/console-ui-src-pages-BrowserPage.spec.md"
    - ".specanchor/modules/ava-patches-loop_patch.spec.md"
    - ".specanchor/modules/ava-patches-tools_patch.spec.md"
  related_global:
    - ".specanchor/global/architecture.md"
    - ".specanchor/global-patch-spec.md"
  related_tasks:
    - ".specanchor/tasks/ava-skills/2026-04-06_page-agent-test-optimization.md"
    - ".specanchor/tasks/2026-04-04_coding-cli-and-self-improvement-loop.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "REVIEW"
  branch: "feat/0.1.1"
---

# SDD Spec: console_ui_dev_loop 前端开发-回归闭环

## 0. Open Questions

- [x] 这个闭环是否应由 `page_agent_test` 单独承担？
  - 结论：不应。`page_agent_test` 最多只能作为底层验证协议或内部参考，不适合作为用户面闭环入口。
- [x] `console_ui_regression` 是否仍需保留为独立 user-facing skill？
  - 结论：原则上不需要。它的有效部分应被 `console_ui_dev_loop` 吸收，只保留最小 console-ui 专属 verifier 资产。
- [x] 对当前仓库，最佳形态是“通用基础层 + repo wrapper”还是“单一 repo-specific orchestrator”？
  - 结论：当前以单一 repo-specific orchestrator 更合适，即 `console_ui_dev_loop`。
- [x] v1 的 coding 主路径是否要让 `claude_code` 与 `codex` 对等？
  - 结论：不对等。v1 默认 `claude_code mode="sync"`，`codex` 作为后续阶段能力规划。
- [x] 是否要在 v1 内补 `page_agent` 的结构化输出面？
  - 结论：要补。否则 verifier 只能靠文本解析，闭环会偏脆弱。
- [x] 是否要先基于需求意图生成一份跨轮持久化的测试任务 / 检查清单？
  - 结论：要。进入 coding 前先生成 `testing_task + master_checklist`，后续轮次只允许带理由地新增、废弃或保留 checkpoint。
- [x] 二次修复时是否每轮都要执行完整 checklist？
  - 结论：默认不需要。v1 默认 `rerun_policy=full_before_pass`：中间轮次执行受影响项 + 基础 smoke，只有准备宣告 `PASS` 前才跑完整 checklist；保留 `full_each_round` 作为显式严格模式。

## 1. Requirements (Context)

- **Goal**: 为当前 nanobot/console-ui 工作流定义一个单一用户面 skill 或等价 workflow 工件 `console_ui_dev_loop`，使 agent 能在一次任务中完成：编码实现、页面回归、结构化报告、失败反馈回灌、以及有限轮次重试。
- **In-Scope**:
  - 定义 `console_ui_dev_loop` 的输入契约、循环协议、停止条件、报告格式
  - 定义 Round 0 的需求意图理解与 `testing_task` 生成规则
  - 定义跨轮 `master_checklist` 生命周期：新增、废弃、重试、最终全量回归
  - 定义 v1 coding 主路径：`claude_code mode="sync"`
  - 统一 `page_agent` 驱动的回归验证策略，采用 deterministic-first
  - 为 `page_agent` 增加结构化输出面，供 verifier 稳定消费
  - 吸收 `console_ui_regression` 中真正有价值的 console-ui 页面映射、源码导出验证线索
  - 将 `page_agent_test` 降级为内部协议/参考或彻底退出 user-facing 触发面
  - 为 `codex` 补充后续开发 TODO，明确它何时再进入主路径
- **Out-of-Scope**:
  - 把该闭环扩展成通用任意前端项目的框架
  - 修改 `nanobot/`
  - 构建 CI 平台、并行浏览器矩阵、E2E 基础设施
  - 在本任务内直接实现 lifecycle/restart/control-plane 改造

## 1.1 Context Sources

- Requirement Source:
  - 用户确认方向：需要针对当前 nanobot 的前端任务，形成 `ClaudeCode/Codex -> 回归 -> 报告 -> 未通过则继续循环` 的闭环，并归档旧 spec
  - 用户进一步要求：参考 `sdd-riper-one` 流程，在 coding 前先理解需求意图并创建完整测试任务 / checklist，后续轮次允许动态更新，并在输出中同时返回已完成与未完成检查
- Design Refs:
  - `ava/skills/page_agent_test/SKILL.md`
  - `ava/skills/console_ui_regression/SKILL.md`
  - `ava/tools/page_agent.py`
  - `ava/tools/claude_code.py`
  - `ava/tools/codex.py`
  - `ava/templates/TOOLS.md`
- Extra Context:
  - `.specanchor/tasks/ava-skills/2026-04-06_page-agent-test-optimization.md`
  - `.specanchor/tasks/2026-04-04_coding-cli-and-self-improvement-loop.md`

## 2. Research Findings

### 2.1 当前闭环能力拆分

1. `claude_code` 与 `codex` 都已经提供真实 coding 能力；它们是“开发/修复任务”的执行器，而不是 skill 本身。
2. `page_agent` 已经提供页面导航、截图、URL/Title 查询和结构化 Page State 输出，足以承担多数 smoke 级验证的事实源。
3. `page_agent_test` 当前更像一个对这些工具的松散提示词包装，不具备稳定 gate 所需的 machine-friendly contract。
4. `console_ui_regression` 真正有价值的是 console-ui 专属页面注册、文件到页面映射、以及按源码推断页面期望；但它并不提供 coding loop orchestration。
5. 因此当前缺口不是“再多一个测试 skill”，而是“把 coding executor + verifier + retry policy 收口到一个统一闭环入口”。

### 2.2 针对当前仓库的工程判断

1. 当前仓库的用户目标是 `console-ui` 前端开发，不是任意网站自动化。
2. 若继续保留 `page_agent_test`、`console_ui_regression`、未来的 loop skill 三个并列 user-facing skill，调用层将持续混乱：谁负责开发，谁负责测试，谁负责重试，不清楚。
3. 更稳妥的方案是：仅保留一个对外入口 `console_ui_dev_loop`，其内部再组合 coding 工具和 verifier 资产。
4. `page_agent_test` 不再适合作为当前仓库里的强触发 skill；最多保留为内部参考协议，供 loop skill 复用断言梯度和报告模板。

### 2.3 当前 draft 在“测试任务化”上的缺口

1. 当前 draft 只有每轮 `regression_scope`，没有一份跨轮持久化的 `master_checklist`，因此无法清晰回答“哪些检查已经完成、哪些尚未完成、为什么新增或废弃了某个 checkpoint”。
2. 当前 repo 中最接近的既有流程 `console_ui_regression` 仍是线性的“导航 -> 路由检查 -> 截图 -> vision 判定 -> 汇总”，不是可长期维护的测试任务模型。
3. 若没有稳定 `check_id`，`same_failure_twice` 这类 stop condition 只能按自然语言近似比较，后续很难稳健判定“同一个检查连续失败两次”。
4. 参考 `sdd-riper-one` 的 `Research -> Plan -> Execute -> Review` 约束，更合适的做法是：
   - 在进入 coding 前先产出一个可执行的 `testing_task`
   - 将 `master_checklist` 视为该任务的执行清单
   - 在执行轮次中允许 Reverse Sync：新增 checkpoint、废弃 checkpoint、更新优先级与证据要求
5. 这也意味着 `vision` 不应被建模成一份独立 checklist，而应作为 checkpoint 的一种断言模式：`deterministic | visual | hybrid`。

### 2.4 工具就绪度评估

#### 已满足 v1 需求的能力

1. **Claude Code 执行器**
   - `claude_code` 已支持 `sync` 和 `async` 两条路径；其中 `sync` 足以承担 v1 阻塞式闭环主路径。
2. **Codex 执行器**
   - `codex` 已可注册，且当前机器上 CLI 可用；适合作为 Phase B 异步 coding 任务能力。
3. **页面验证执行器**
   - `page_agent` 已支持 `execute / screenshot / get_page_info / close_session / restart_runner`，且 `execute` 返回 `Page State`，足以支撑 deterministic-first smoke。
4. **视觉升级能力**
   - `vision` 已可用于视觉类补充判断，不需要为 v1 另补图片分析工具。
5. **前端构建后处理**
   - `BackgroundTaskStore` 已具备 coding 任务完成后的 `console-ui` 自动 rebuild hook，`gateway_control` 也可在需要时补充状态/重启控制。

#### 当前仍不满足或只部分满足的点

1. **闭环 skill 对 async task 的可控等待能力不足**
   - 当前 `claude_code` / `codex` 异步提交后，会通过 `BackgroundTaskStore` 自动 continuation，但 skill 本身没有可调用的 `wait/status` tool。
   - `/task` 是 slash command，不是 tool；不能把 skill 设计成依赖 `/task` 作为子步骤。
2. **async continuation 不能保证 skill 上下文自动续接**
   - 当前技能系统没有“上轮已加载 skill 持续生效”的机制；background continuation 是一条新的 agent loop，默认只带 skills summary，不保证再次加载 `console_ui_dev_loop` 全文。
3. **`page_agent` 返回仍是文本，不是 machine-friendly 结构**
   - 这是用户已明确要求补的 v1 配套增强；否则 `console_ui_dev_loop` 在失败分类、反馈压缩、重试判定上会过于依赖字符串解析。
4. **`codex` 没有 sync 模式**
   - 若我们选择“同一 turn 内阻塞跑完 coding→regression→retry”的保守方案，`codex` 无法完整参与，只能作为异步路径。
5. **自动 rebuild 目前偏向仓库内 `console-ui/dist`**
   - 对当前仓库内建 console-ui 路径足够；若未来 skill 要支持外部 `base_url` 或 dev server 模式，现有 post-task hook 不够泛化。

### 2.5 设计含义

1. v1 采用**方案 1**：默认 `claude_code mode="sync"`，先跑通阻塞式 coding→regression→retry 闭环。
2. `codex` 不进入 v1 主路径；只保留为后续阶段 TODO，待 async orchestration 能力补齐后再进入主路径。
3. `page_agent` 结构化输出面属于 v1 组成部分，而不是二期优化。
4. `console_ui_dev_loop` 在 Round 0 必须先完成需求意图压缩，并生成 `testing_task + master_checklist`，再进入 coding。
5. checklist 的基本单元是稳定 `check_id`，而不是“某一轮临时生成的一段 verify_prompt”。
6. 默认 `rerun_policy=full_before_pass`：
   - 中间 retry 轮次只跑受影响 checkpoint + 基础 smoke
   - 准备宣告 `PASS` 前必须执行完整 `master_checklist`
7. `page_agent` 和 `vision` 不再对应两份并列清单；每个 checkpoint 自带 `assertion_mode`，由 verifier 按需决定是否升级到视觉检查。

### 2.6 Next Actions

- 新建 `console_ui_dev_loop` task/skill 作为唯一用户面闭环入口
- 将 `page_agent_test` 优化 spec 归档
- 在实现阶段决定 `console_ui_regression` 是并入 `console_ui_dev_loop` 还是退化为 reference 资产
- 优先落地 `testing_task + master_checklist` 契约，再写具体 verifier prompt

## 3. Innovate

### Option A: 保留三个并列 user-facing skill

- Pros:
  - 表面上职责分层更细
  - 可分别迭代
- Cons:
  - 对当前仓库的真实工作流过度抽象
  - 调用层持续不清楚先用哪个、何时切换
  - prompt 开销和维护成本都更高

### Option B: 单一 user-facing `console_ui_dev_loop`，内部吸收 verifier 资产

- Pros:
  - 最贴近用户真实使用方式
  - 把开发、验证、重试收束到同一任务契约
  - 更容易形成稳定的 stop condition 和 round report
  - 避免 skill 之间来回切换造成上下文丢失
- Cons:
  - console-ui 场景特化更强
  - 后续若扩展到别的前端项目，需要再抽通用层

### Option C: 不做新 skill，只靠 task spec + 现有 skill 人工拼装

- Pros:
  - 实现成本最低
- Cons:
  - 无法形成稳定、可复用、低歧义的操作入口
  - 继续依赖操作者记忆多份 skill 的边界

### Decision

- Selected: `Option B`
- Why:
  - 当前仓库的真实目标不是“维护一套技能体系”，而是“让 nanobot 自己把前端任务做完并知道何时该停”。单一 orchestrator 最符合这个目标。
  - 在该 orchestrator 内，v1 进一步采用 `claude_code sync + page_agent structured output` 的最小闭环方案。

## 4. Plan (Contract)

### 4.1 File Changes

- `ava/skills/console_ui_dev_loop/SKILL.md`
  - 新建唯一用户面闭环 skill
- `ava/skills/console_ui_dev_loop/references/loop-contract.md`
  - 定义 round lifecycle、checklist lifecycle、stop policy、coder feedback contract
- `ava/skills/console_ui_dev_loop/references/testing-task.md`
  - 定义 Round 0 意图理解、`testing_task` 生成、checkpoint 更新与重测策略
- `ava/skills/console_ui_dev_loop/references/page-selection.md`
  - 定义“显式页面 > changed_files 映射 > baseline smoke / full checklist”的页面选择优先级
- `ava/skills/console_ui_dev_loop/references/verifier-policy.md`
  - 定义 deterministic-first 验证梯度与何时升级到 `vision`
- `ava/skills/console_ui_dev_loop/evals/evals.json`
  - 针对闭环能力设计 benchmark prompts
- `ava/tools/page_agent.py`
  - 增加可选结构化输出面，供 verifier 稳定消费
- `ava/templates/TOOLS.md`
  - 同步记录 `page_agent` 结构化输出参数与 `console_ui_dev_loop` 的 v1 约束
- `tests/tools/test_page_agent.py`
  - 补结构化输出 contract 测试
- `ava/skills/page_agent_test/SKILL.md`
  - 降级为内部参考协议，或改写为不再主动触发的 narrow skill
- `ava/skills/console_ui_regression/SKILL.md`
  - 合并/瘦身：仅保留 console-ui 页面注册和源码推断逻辑，供 `console_ui_dev_loop` 复用

### 4.2 Signatures

#### 顶层输入契约

```yaml
task:
  goal: "修复某个 console-ui 页面问题"
  project_path: "console-ui"
  coding_tool: "auto | claude_code"
  changed_files: []
  explicit_pages: []
  max_rounds: 3
  rerun_policy: "full_before_pass | full_each_round"
  stop_on:
    - "same_failure_twice"
    - "non_retryable_failure"
    - "manual_auth_required"
```

说明：
- v1 中 `auto` 实际解析为 `claude_code mode="sync"`
- `codex` 不进入 v1 主路径，见本 spec 的 Phase B TODO
- v1 默认 `rerun_policy=full_before_pass`

#### Round 0 / Testing Task 契约

```yaml
testing_task:
  summary: "本轮要验证的用户目标与风险边界"
  intent_understanding:
    target_outcomes: []
    primary_risks: []
    excluded_scope: []
  master_checklist:
    version: 1
    items:
      - check_id: "config.route.heading"
        title: "配置页路由与主标题可见"
        page: "/config"
        source: "explicit | file_map | inferred"
        assertion_mode: "deterministic | visual | hybrid"
        priority: "p0 | p1 | p2"
        status: "pending | passed | failed | skipped | deprecated"
        rationale: "为何需要这个检查"
        evidence_required:
          - "url"
          - "page_state.headings"
```

约束：
- `testing_task` 在 Round 0 生成，先于 coding 执行
- `check_id` 一旦生成，后续轮次不得重命名；只允许更新状态或标记 `deprecated`
- `vision` 不是单独 checklist，而是 `assertion_mode` 的一种执行方式
- `master_checklist` 必须覆盖：
  - 用户显式目标
  - 受 `changed_files` 影响的页面或关键交互
  - 最小基础 smoke（例如入口路由、主标题、关键按钮或错误提示）

#### 单轮输出契约

```yaml
round_output:
  round: 1
  phase: "round0_planning | coding | regression | final_verification"
  coding_summary: ""
  regression_scope:
    check_ids: []
    pages: []
    source: "impacted_subset | baseline_smoke | full_checklist"
  checklist_snapshot:
    version: 1
    completed_checks: []
    pending_checks: []
    failed_checks: []
    deprecated_checks: []
  checklist_delta:
    added: []
    deprecated: []
    unchanged: []
  regression_report: ""
  verdict: "pass | retry | escalate"
  feedback_for_coder:
    failed_pages: []
    failed_checks: []
    failure_taxonomy: []
    evidence_paths: []
    next_hint: ""
```

约束：
- 每轮必须返回 `completed_checks` 与 `pending_checks`
- 若本轮新增或废弃 checkpoint，必须写入 `checklist_delta`
- 只有执行过 `full_checklist` 的轮次，才允许输出最终 `verdict=pass`

#### Verifier 结果压缩契约

```yaml
verifier_result:
  check_id: "config.route.heading"
  page: "/config"
  status: "pass | fail"
  assertion_mode: "deterministic | visual | hybrid"
  failure_taxonomy:
    - "ROUTE_MISMATCH"
  evidence:
    session_id: "s_abc12345"
    screenshot: ""
    page_state: ""
  retryable: true
  coder_hint: "路由已进入 /config，但 heading 缺失，优先检查页面容器是否提前 return。"
  checklist_action:
    action: "keep | add_followup | deprecate"
    reason: ""
    new_checks: []
```

#### page_agent 结构化输出契约（v1 implemented）

```yaml
page_agent(
  action="execute|get_page_info|screenshot",
  ...,
  response_format="text|json"
) -> str
```

当 `response_format="json"` 时，返回 JSON 字符串：

```json
{
  "status": "SUCCESS",
  "session_id": "s_abc12345",
  "steps": 3,
  "duration_ms": 1200,
  "page": {
    "url": "http://127.0.0.1:6688/config",
    "title": "Config"
  },
  "result": {
    "success": true,
    "data": "..."
  },
  "page_state": {
    "headings": ["配置"],
    "alerts": [],
    "forms": [],
    "buttons": ["保存"]
  },
  "error": null
}
```

约束：
- 默认仍为 `text`，保持向后兼容
- `console_ui_dev_loop` 内部默认使用 `json`
- `screenshot` / `get_page_info` 同样提供 JSON 版本，字段只保留对应动作所需信息

#### 重测策略契约

- 默认：`rerun_policy=full_before_pass`
  - Round 0：生成完整 `master_checklist`
  - 中间 retry 轮次：执行 `impacted_subset + baseline_smoke`
  - 准备宣告 `PASS` 前：强制执行 `full_checklist`
- 显式严格模式：`rerun_policy=full_each_round`
  - 每轮修复后都执行完整 checklist
  - 仅在用户明确要求更高成本的严格模式时启用
- `same_failure_twice` 的判定以 `check_id + failure_taxonomy` 为主，而不是仅比较自然语言报告

### 4.3 Implementation Checklist

- [x] 1. 新建 `console_ui_dev_loop` spec/skill 入口，明确它是唯一用户面闭环入口
- [x] 2. 定义 Round 0 的 `testing_task` 生成协议
  - 先压缩需求意图
  - 生成 `master_checklist`
  - 为每个 checkpoint 分配稳定 `check_id`
- [x] 3. 定义 checklist 生命周期
  - 新增 checkpoint 的条件
  - `deprecated` 的条件
  - `completed/pending/failed/deprecated` 的返回格式
- [x] 4. 统一 coding executor 选择策略
  - v1 默认 `auto -> claude_code sync`
  - v1 仅允许显式强制 `claude_code`
- [x] 5. 定义页面选择优先级
  - `explicit_pages`
  - `changed_files` 映射
  - fallback 到 `baseline_smoke` 或 `full_checklist`
- [x] 6. 为 `page_agent` 增加结构化输出面
  - `response_format=json`
  - `execute/get_page_info/screenshot` 的 JSON contract
  - 保持 text 默认值不变
- [x] 7. 定义 deterministic-first verifier policy
  - 先 URL / Page State / DOM facts
  - 只有视觉问题才升级 `vision`
- [x] 8. 定义 round report、checklist delta、retry policy 与 stop condition
  - 最多轮次
  - `same_failure_twice` 基于 `check_id + failure_taxonomy`
  - 非 retryable failure 直接升级人工处理
  - 默认 `full_before_pass`
- [x] 9. 收缩现有 skill 体系
  - `page_agent_test` 退出 user-facing 主路径
  - `console_ui_regression` 只保留可复用 verifier 资产
- [x] 10. 补 Codex 后续开发 TODO
  - 定义进入主路径前需要的 async orchestration 缺口
  - 不在本阶段实现
- [x] 11. 设计 benchmark prompts
  - 单页面修复闭环
  - 多页面回归闭环
  - checklist 动态增删场景
  - 需要视觉升级但不可自动修复的场景
- [x] 12. 等待 `Plan Approved` 后进入实现

### 4.4 Codex Phase B TODO

- 为闭环补一个可调用的后台任务状态面（例如 `bg_task status|wait|cancel`），避免 skill 依赖 slash command
- 设计 Codex 在 `console_ui_dev_loop` 中的进入条件：
  - 显式选择 `coding_tool=codex`
  - 或 v2 的 `auto` 选择策略
- 明确 async continuation 与 skill 上下文续接方案：
  - 要么引入可等待 tool
  - 要么让 continuation 明确重载 `console_ui_dev_loop` 所需协议
- 补 Codex 主路径 benchmark：
  - 与 `claude_code sync` 的成功率/轮次/延迟对比

## 5. Execute Log

- [x] Step 1: 基于用户确认方向，决定不再围绕 `page_agent_test` 做独立 user-facing 能力扩展
- [x] Step 2: 新建以 `console_ui_dev_loop` 为中心的闭环 spec
- [x] Step 3: 根据用户选择，将 v1 收敛为 `claude_code sync + page_agent structured output`
- [x] Step 4: 为 `codex` 补 Phase B TODO，明确本阶段不进入主路径
- [x] Step 5: 同步 module spec TODO
  - `ava-tools-page_agent.spec.md` 已补 v1 结构化输出规划
  - `ava-tools-codex.spec.md` 已补 Phase B 进入主路径前置条件
- [x] Step 6: 按用户要求补入 `sdd-riper-one` 风格测试任务机制
  - Round 0 先生成 `testing_task + master_checklist`
  - 每轮返回 `completed/pending/deprecated` 视图
  - 默认 `rerun_policy=full_before_pass`
- [x] Step 7: 收到 `Plan Approved` 后进入 Execute
- [x] Step 8: 实现 `page_agent response_format=json`
  - 保持文本协议兼容
  - `execute / screenshot / get_page_info` 新增 JSON 字符串输出
- [x] Step 9: 新建 `console_ui_dev_loop` skill 与 references/evals
- [x] Step 10: 收缩 `page_agent_test` 与 `console_ui_regression` 的 user-facing 定位
- [x] Step 11: 同步 `ava/templates/TOOLS.md` 与 `ava-tools-page_agent.spec.md`
- [x] Step 12: 完成定向验证
  - `uv run pytest tests/tools/test_page_agent.py -q`
  - `git diff --check`
  - `specanchor-check.sh task .specanchor/tasks/ava-skills/2026-04-06_console-ui-dev-loop.md`

## 6. Review Verdict

- Spec coverage: PASS
- Behavior check: PASS（`page_agent` JSON contract 已落地，skill 资产已创建，定向测试通过）
- Regression risk: Low（文本协议保持兼容；新增 JSON 输出为可选参数）
- Module Spec 需更新: 已同步实现（`ava-tools-page_agent.spec.md` 已从 TODO 更新为已实现 contract；`ava-tools-codex.spec.md` 仍保留 Phase B TODO）
- Follow-ups:
  - 以本 spec 作为唯一执行入口
  - `console_ui_dev_loop` 实现时已先落地 `testing_task` 与 checklist 生命周期，再补 verifier prompt
  - Codex 仍不进入 v1 主路径
  - 若要做 skill packaging / validator 闭环，需另补 `skill-creator` 对 `evals/` 目录和下划线目录命名的兼容

## 7. Plan-Execution Diff

- 本轮按 spec 实现了 v1 最小闭环资产；与计划相比未扩展 Codex 主路径，符合原约束
