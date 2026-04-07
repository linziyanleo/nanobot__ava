---
specanchor:
  level: task
  task_name: "page_agent_test Skill 优化与分层收口"
  author: "@codex"
  created: "2026-04-06"
  status: "archived"
  last_change: "归档：当前 spec 被 console_ui_dev_loop 闭环 spec 替代，不再作为执行入口"
  related_modules:
    - ".specanchor/modules/page_agent_runtime_spec.md"
    - ".specanchor/modules/tools_patch_spec.md"
  related_global:
    - ".specanchor/global/architecture.md"
    - ".specanchor/global-patch-spec.md"
  related_tasks:
    - ".specanchor/tasks/2026-04-03_generic-page-agent-tool.md"
    - ".specanchor/tasks/2026-04-04_coding-cli-and-self-improvement-loop.md"
    - ".specanchor/tasks/ava-skills/2026-04-06_console-ui-dev-loop.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "feat/0.1.1"
---

# SDD Spec: page_agent_test Skill 优化与分层收口

> 归档说明：本 spec 已被 [`.specanchor/tasks/ava-skills/2026-04-06_console-ui-dev-loop.md`](/Users/fanghu/Documents/Test/nanobot__ava/.specanchor/tasks/ava-skills/2026-04-06_console-ui-dev-loop.md) 替代。保留此文件仅用于记录为何放弃“多个并列 user-facing skill”的分层方案。

## 0. Open Questions

- [x] `page_agent_test` 的目标是“通用前端自动化回归”还是“基于 page_agent 的 best-effort smoke / exploratory test”？
  - 结论：应明确为后者，不能冒充 CI 级回归框架。
- [x] 自动修复是否属于 base skill 的默认职责？
  - 结论：不应默认内置；应降为显式 opt-in 的二阶段能力，或由项目 wrapper 编排。
- [x] `vision` 是否应作为主判据？
  - 结论：不应。应采用 deterministic-first：先 URL / Page State / DOM 事实，再按需升级到视觉检查。
- [x] `page_agent_test` 是否应单独承担“开发完成后自动回归、输出报告、失败后继续循环修复”的闭环职责？
  - 结论：不应单独承担。它最多是底层验证协议；真正的闭环需要单独的 orchestrator。
- [x] `console_ui_regression` 是否是“修复和开发任务”的必要 skill？
  - 结论：不是。开发/修复能力来自 `claude_code` / `codex`；`console_ui_regression` 仅在需要 console-ui 特定页面映射与回归策略时才有价值。

## 1. Requirements (Context)

- **Goal**: 把 `ava/skills/page_agent_test` 从“看起来什么都能做”的草案，收口为一个 repo-grounded、可复用、可被 wrapper 继承的基础测试 skill，使其适合 Page Agent 驱动的通用前端 smoke / exploratory test，但不再误导为完整回归测试框架。
- **In-Scope**:
  - 重写 `page_agent_test` 的定位、触发描述、输入契约、执行协议、报告模板
  - 建立“URL / Page State / DOM / vision”四级断言梯度，默认 deterministic-first
  - 将“测试”与“自动修复”职责拆开，默认只做测试与诊断
  - 为 skill 补齐 references / evals，使其可被后续基准化优化
  - 同步调整 `console_ui_regression`，使其只承担 console-ui 特定编排，不重复定义底层协议
- **Out-of-Scope**:
  - 把 `page_agent_test` 做成 Playwright / Cypress 替代品
  - 修改 `nanobot/`
  - 为任意前端项目自动生成稳定登录策略、数据夹具或 CI 流程
  - 在本任务内直接实现完整修复闭环、自动 build / restart 编排

## 1.2 User Workflow Clarification

- 用户的真实目标链路是：
  1. 给当前 nanobot 一个前端开发任务
  2. 用 `claude_code` 或 `codex` 完成实现
  3. 调用某个 skill 执行回归测试并输出报告
  4. 若未达标，则把失败摘要继续回灌给 coding 工具，进入下一轮
- 这意味着评估标准不是“这个 skill 能不能做 smoke”，而是“它能不能作为 coding loop 里的稳定 verifier / gate”。
- 对这个目标，`page_agent_test` 和 `console_ui_regression` 都不应承担“开发工具”职责；它们最多承担“验证策略”职责。

## 1.1 Context Sources

- Requirement Source:
  - 用户问题：评估 `ava/skills/page_agent_test` 是否合格、指出问题，并按 `sdd-riper-one` 写优化方案
- Design Refs:
  - `ava/skills/page_agent_test/SKILL.md`
  - `ava/skills/console_ui_regression/SKILL.md`
  - `ava/tools/page_agent.py`
  - `ava/templates/TOOLS.md`
- Extra Context:
  - `.specanchor/tasks/2026-04-03_generic-page-agent-tool.md`
  - `.specanchor/tasks/2026-04-04_coding-cli-and-self-improvement-loop.md`

## 2. Research Findings

### 2.1 现状判断

1. 当前 `page_agent_test` 把自己描述为“通用前端页面回归测试协议”，但真实输入仍高度依赖项目方显式提供 `base_url + pages + verify_prompt (+ project_path/build_command)`。这更像“半手工 smoke protocol”，不是通用回归能力。
2. 当前协议把 `vision` 作为核心判定链路，但 `page_agent` 的真实 contract 已经提供 `URL / Title / Page State / Form / Alert / Buttons` 等结构化信息。对于登录成功、路由正确、错误提示、表单填充等常见前端健康检查，先用 `page_agent` 更稳。
3. 当前 skill 默认把“自动修复”并入测试流程，会把“测试协议”与“项目级修复编排”耦合在一起。对于只想验证页面、没有代码权限、没有 build 命令、或不希望 agent 改代码的场景，这是错误默认。
4. `console_ui_regression` 已明确把自己定位为 `page_agent_test` 的 wrapper，且已经引入“按页面源码动态生成 verify_prompt”的思路。这说明 repo 内已经出现分层意图，但 `page_agent_test` 本身还没有提供足够稳的基础协议。
5. 当前 `page_agent_test` 只有单个 `SKILL.md`，没有 `references/`、没有 `evals/`、没有 failure taxonomy，也没有“什么时候不该触发”的负向边界。它难以被持续 benchmark，也容易在触发层面漂移。
6. 若把它放进“ClaudeCode/Codex 完成后自动回归、失败则继续循环”的闭环里，当前 `page_agent_test` 还缺少 machine-friendly 的结果结构、retry policy、stop condition、失败分类和“把哪些结论反馈给 coder”的压缩协议，因此不足以充当稳定 gate。
7. `console_ui_regression` 的价值不是“让 agent 获得修复能力”，而是提供 console-ui 专属的页面选择、文件到页面映射和源码导出的验证线索；如果调用方已经能自己完成这些判断，它就不是必需层。

### 2.2 关键风险

- **风险 1：定位过宽**
  - 用户说“测一下页面”时，skill 可能误导 agent 走“截图 + vision + 自动修复”全套，而不是先做低成本 smoke。
- **风险 2：断言主次颠倒**
  - 把 `vision` 当默认判定器，会增加成本、波动和误判，尤其在 DOM 已足够表达问题时。
- **风险 3：把 wrapper 经验写成 base contract**
  - `console_ui_regression` 这种“项目专属页面注册表 + 动态验证”的做法，不等于 `page_agent_test` 已经具备对任意前端项目的自适应能力。
- **风险 4：测试与修复边界不清**
  - 当 skill 自动进入 `claude_code + exec` 修复回路时，调用者往往还没有明确授权“开始改代码”。
- **风险 5：闭环里没有真正的 orchestration**
  - 即使单次测试能跑，当前 skill 也没有定义“失败摘要如何喂给 coder、最多循环几轮、何时停止并升级人工介入”。

### 2.3 结论

- 当前版本 **不合格于“Page Agent 做通用前端测试”这个表述**。
- 更准确的评价是：它可以作为“通用前端 smoke / exploratory test 的初稿”，但还不能作为完整、稳健、可复用的通用测试 skill。

### 2.4 Next Actions

- 把 `page_agent_test` 重写为“基础 smoke 协议”，缩小承诺面
- 把自动修复降为显式 opt-in 能力
- 把 `console_ui_regression` 收口成真正的 wrapper
- 为 skill 增加 benchmark 所需的 evals 与参考文档

## 3. Innovate

### Option A: 小修文案，保留现有一体化协议

- Pros:
  - 改动最小
  - 短期能降低部分误导
- Cons:
  - 核心问题不变：定位仍虚胖、断言链仍偏视觉、测试和修复仍耦合
  - `console_ui_regression` 依旧会建立在不稳的 base contract 上

### Option B: 放弃 `page_agent_test`，转向纯 Playwright/选择器测试 skill

- Pros:
  - 更确定性
  - 更接近真正自动化测试框架
- Cons:
  - 偏离当前 repo 的 Page Agent 投资方向
  - 失去“自然语言探索页面”的价值
  - 不是用户当前想优化的对象

### Option C: 重构为“基础协议 + 项目 wrapper + 显式修复扩展”的三层模型

- Pros:
  - 与 `page_agent` 的真实 contract 一致
  - 与 `console_ui_regression` 的 wrapper 关系一致
  - 能把“通用 smoke”和“项目修复闭环”从一开始就分开
  - 后续容易做 skill benchmark 与迭代
- Cons:
  - 需要补文档结构、wrapper 对齐和评测资产

### Option D: 将 `page_agent_test` 降级为内部协议/参考，把闭环集中到单一 repo-specific orchestrator

- Pros:
  - 最贴近用户真实工作流
  - 避免“一个技能开发、另一个技能测试、第三个技能再调度”造成职责分散
  - 对只服务 `console-ui` 的场景更省 prompt 和维护成本
- Cons:
  - 若未来要复用到别的前端项目，缺少可独立迁移的基础协议层
  - 会让 console-ui 方案和通用协议耦合更紧

### Decision

- Selected: `Option C`
- Why:
  - 这是唯一能同时解决“定位不准、判据失衡、职责耦合、不可评测”四个问题的方案。
  - 同时保留向 `Option D` 收缩的余地：如果确认只服务 `console-ui`，可在实现阶段把 `page_agent_test` 降级为 reference，而不是继续保留强触发的 standalone skill。

## 4. Plan (Contract)

### 4.1 File Changes

- `ava/skills/page_agent_test/SKILL.md`
  - 重写 description、定位、触发边界、输入契约、执行流程、报告模板
- `ava/skills/page_agent_test/references/input-contract.md`
  - 定义标准输入模型：target/auth/safety/evidence/repair
- `ava/skills/page_agent_test/references/assertion-ladder.md`
  - 定义断言梯度：Route → Page State → DOM Facts → Vision
- `ava/skills/page_agent_test/references/report-template.md`
  - 定义统一报告与 failure taxonomy
- `ava/skills/page_agent_test/references/wrapper-guidelines.md`
  - 约束项目 wrapper 能做什么、不能做什么
- `ava/skills/page_agent_test/evals/evals.json`
  - 增加 3 组代表性评测 prompt，支撑 skill benchmark
- `ava/skills/console_ui_regression/SKILL.md`
  - 删除重复底层协议，只保留 console-ui 页面注册、源码推断与 wrapper 编排
- `ava/skills/console_ui_dev_loop/SKILL.md` 或等价 workflow 工件
  - 定义 coding → regression → report → retry 的顶层闭环；若决定不新增 skill，则把该职责写入现有 workflow / task protocol

### 4.2 Signatures

#### 闭环编排契约

```yaml
task:
  goal: "修复 console-ui 某页面问题"
  changed_files: []
  max_rounds: 3
  stop_on:
    - "same_failure_twice"
    - "non_retryable_failure"

round_output:
  coding_summary: ""
  regression_report: ""
  verdict: "pass | retry | escalate"
  feedback_for_coder:
    failed_pages: []
    failure_taxonomy: []
    evidence_paths: []
    next_hint: ""
```

#### 基础输入契约

```yaml
target:
  base_url: "http://127.0.0.1:6688"
  pages:
    - path: "/bg-tasks"
      label: "后台任务"
      nav_instruction: "点击左侧导航栏中的后台任务"
      expected:
        route: "/bg-tasks"
        headings: ["后台任务"]
        alerts_absent: ["Error", "Exception"]
        visuals: []   # 仅在确实需要视觉判定时填写

auth:
  mode: "none | form_login | reuse_session | manual"
  login_url: "/login"
  username: "admin"
  password: "admin"

safety:
  mode: "readonly | allow_mutation"

evidence:
  screenshot: "on_fail | always | never"
  include_page_state: true

repair:
  enabled: false
  project_path: ""
  build_command: ""
  max_fix_rounds: 0
```

#### 报告输出契约

```markdown
## Page Agent Smoke Report

**Target**: <base_url>
**Mode**: <readonly / allow_mutation>
**Result**: <PASS / FAIL / PARTIAL>

| # | 页面 | Route | Page State | Vision | 状态 |
|---|------|-------|------------|--------|------|

### Failure Taxonomy
- ROUTE_MISMATCH
- PAGE_AGENT_TIMEOUT
- PAGE_AGENT_ERROR
- DOM_EXPECTATION_MISSED
- VISUAL_EXPECTATION_MISSED
- AUTH_BLOCKED

### Evidence
- session_id: <...>
- screenshot: <path or none>
- page_state: <headings/forms/alerts/buttons 摘要>
- raw_result: <page_agent 关键输出摘要>
```

### 4.3 Implementation Checklist

- [ ] 1. 收紧 `page_agent_test` 的 description 与定位
  - 改为“Page Agent 驱动的通用前端 smoke / exploratory test”
  - 明确“不适用于 CI 级确定性回归，也不默认等价于 Playwright/Cypress”
- [ ] 2. 重写输入契约，区分 target / auth / safety / evidence / repair 五层
  - 默认 `repair.enabled=false`
  - 默认 `safety.mode=readonly`
- [ ] 3. 建立 deterministic-first 断言梯度
  - 先 `get_page_info`
  - 再读取 `execute` 的 Page State / DOM 文本
  - 仅在颜色、布局、图片、Canvas/SVG 场景时升级 `vision`
- [ ] 4. 把 failure taxonomy 和报告模板独立成 reference
  - 报告中必须保留 session_id、screenshot、page_state 摘要、失败分类
- [ ] 5. 把自动修复改为显式 opt-in
  - 未提供 `repair.enabled=true + project_path + build_command` 时，不进入修复回路
  - 修复建议默认只输出“下一步建议”，不直接改代码
- [ ] 6. 收口 `console_ui_regression`
  - 只保留 console-ui 的页面注册、文件到页面映射、源码推断与 wrapper 特化
  - 不再重复声明底层 page_agent/screenshot/report protocol
- [ ] 7. 明确闭环编排层归属
  - 若要跨项目复用：保留 `page_agent_test` 作为基础协议，并新增顶层 orchestrator
  - 若只服务 `console-ui`：将 `page_agent_test` 降级为 reference/内部协议，避免强触发 standalone skill
- [ ] 8. 增加 skill benchmark 资产
  - `readonly smoke`
  - `visual-only escalation`
  - `repair opt-in`
- [ ] 9. 等待 `Plan Approved` 后进入实现

## 5. Execute Log

- [x] Step 1: 完成 repo-grounded review，确认当前 skill 的主要问题不是“写得不够多”，而是定位、判据与职责边界不稳
- [x] Step 2: 将优化方向固化为 `基础协议 + wrapper + 显式修复扩展` 三层模型
- [x] Step 3: 补充用户真实闭环目标，确认验证 skill 不等于开发 skill，顶层需要单独 orchestration
- [ ] Step 4: 等待 `Plan Approved` 后开始修改 skill 文件与参考资产

## 6. Review Verdict

- Spec coverage: PASS
- Behavior check: N/A（本次只产出方案，未进入 Execute）
- Regression risk: Low（当前仅新增 task spec）
- Module Spec 需更新: No（当前问题主要在 skill 协议层；若后续修改 `page_agent` 返回 contract，再回看 `page_agent_runtime_spec.md`）
- Follow-ups:
  - 先实施 `page_agent_test` 收口，再同步 `console_ui_regression`
  - benchmark 结果应验证“减少不必要的 vision 调用”和“默认不越权修复”是否真的生效
  - 实现前先决定：是保留通用基础层，还是直接收缩为 `console-ui` 单一闭环 skill

## 7. Plan-Execution Diff

- 本轮仅完成研究与计划落盘，没有实现偏差
- 如后续实现中发现 `console_ui_regression` 已经承载额外 console 专属逻辑，再把其拆分范围收窄到最小必要集
