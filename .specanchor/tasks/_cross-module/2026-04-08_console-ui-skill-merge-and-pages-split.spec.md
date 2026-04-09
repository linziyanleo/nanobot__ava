---
specanchor:
  level: task
  task_name: "console-ui skill 合并与 Pages.md 按页拆分"
  author: "@Ziyan Lin"
  created: "2026-04-08"
  status: "review"
  last_change: "Execute 完成：合并两个 skill、拆分 Pages.md 为 per-page references、删除 console_ui_regression"
  related_modules:
    - ".specanchor/modules/ava-tools-page_agent.spec.md"
    - ".specanchor/modules/console-ui-src-pages-BrowserPage.spec.md"
  related_global:
    - ".specanchor/global/architecture.md"
  related_tasks:
    - ".specanchor/tasks/ava-skills/2026-04-06_console-ui-dev-loop.md"
    - ".specanchor/tasks/ava-skills/2026-04-06_page-agent-test-optimization.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "REVIEW"
  branch: "feat/0.1.1"
---

# SDD Spec: console-ui skill 合并与 Pages.md 按页拆分

## 0. Open Questions

- [x] 合并后的 skill 是否仍保留 `console_ui_dev_loop` 这个名字？还是改名为更通用的 `console_ui`？
  - 结论：保留 `console_ui_dev_loop` 名字不变。
- [x] `page_agent_test` skill 是否同步清理（降级为纯 reference）？还是保持现状？
  - 结论：保持现状。`page_agent_test` 是通用页面测试协议，职责不同，不动。
- [x] Pages.md 拆分后，Sidebar 共享元素是否需要独立为 `_sidebar.md`？还是在每个页面 md 中重复一小段引用提示即可？
  - 结论：独立为 `_sidebar.md`。Sidebar 有 25 行内容（导航项表 + Footer 元素），在 11 个页面中重复不合理；独立后 SKILL.md 引用指令统一写"先读 `_sidebar.md` + 目标页面 md"。
- [x] `console_ui_regression` 目录合并后是否直接删除？还是保留空壳 redirect？
  - 结论：直接删除整个目录。

## 1. Requirements (Context)

- **Goal**: 将 `console_ui_dev_loop` 和 `console_ui_regression` 两个 skill 合并为一个统一入口，同时将 `Pages.md`（317 行单文件）拆分为 per-page references，使模型在开发/测试不同页面时只加载对应页面的知识，降低 token 消耗。
- **In-Scope**:
  - 合并两个 skill 为一个，通过 mode 区分 `regression`（只测不修）和 `dev_loop`（coding → regression → retry 闭环）
  - 消除两个 skill 之间的重复内容（页面注册表、文件映射、verifier 策略）
  - 将 Pages.md 拆分为 `references/pages/{page_key}.md`，每个文件 ~20-40 行
  - 提取 Sidebar 共享元素为 `references/pages/_sidebar.md`
  - 提取认证流程为 `references/auth.md`
  - 将 `page-selection.md` 改名为 `page-registry.md`，作为页面注册表 + 文件映射的唯一维护点
  - 更新 SKILL.md 中的引用指令，明确"测某页面时先读哪些 references"
- **Out-of-Scope**:
  - 修改 `nanobot/` 目录
  - 修改 `page_agent_test` skill（保持现状）
  - 修改 `page_agent.py` 工具代码或 `page-agent-runner.mjs`
  - 修改 console-ui 前端源码
  - 修改 `console_ui_dev_loop/evals/`（内容保持不变，只是路径随合并调整）

## 1.1 Context Sources

- Requirement Source:
  - 用户在本次会话中提出：两个 skill 能否合并？Pages.md 拆成 per-page references 是否更好？
  - 用户确认了合并方案和拆分方案
- Design Refs:
  - `ava/skills/console_ui_dev_loop/SKILL.md` — 当前 dev_loop skill 主文件
  - `ava/skills/console_ui_dev_loop/references/` — loop-contract, testing-task, page-selection, verifier-policy
  - `ava/skills/console_ui_regression/SKILL.md` — 当前 regression skill 主文件
  - `ava/skills/console_ui_regression/Pages.md` — 页面知识库（317 行）
  - `ava/skills/page_agent_test/SKILL.md` — 通用 page-agent 测试协议
- Extra Context:
  - `.specanchor/tasks/ava-skills/2026-04-06_console-ui-dev-loop.md` — 前序 task spec，确立了"单一 orchestrator"方向

## 2. Research Findings

### 2.1 当前问题分析

1. **内容重复**：`regression/SKILL.md` 和 `dev_loop/references/page-selection.md` 各维护一份页面注册表和文件映射表。两份数据已经出现分歧（regression 新增了 media/persona 页面，page-selection 没有）。

2. **模型选择困惑**：三个 console-ui 相关 skill（`dev_loop`、`regression`、`page_agent_test`）的触发条件措辞差异微妙。"测一下 console-ui" 应该触发哪个？模型经常选错。

3. **Token 浪费**：Pages.md 有 317 行，包含 12 个页面的详细元素表。测试单个页面只需要 ~30 行，但当前必须全量加载。

4. **引用链断裂**：`dev_loop` SKILL.md 说"先读 references"，但 regression 的页面知识（Pages.md）在另一个 skill 目录里，模型需要跨 skill 引用。

### 2.2 前序决策回顾

`.specanchor/tasks/ava-skills/2026-04-06_console-ui-dev-loop.md` §3 Decision 已确认：

> Selected: Option B — 单一 user-facing `console_ui_dev_loop`，内部吸收 verifier 资产

当前任务是该决策的落地执行。前序 spec 中 `console_ui_regression` 被定位为"只保留可复用 verifier 资产"——本任务进一步将这些资产物理合并到 `console_ui_dev_loop` 目录。

### 2.3 Pages.md 拆分可行性

Pages.md 结构清晰，已按 `### N. 页面名（Page Key）` 分节：

| 章节 | 行数(约) | 内容 |
|------|---------|------|
| 全局 Sidebar | 25 | 导航项表 + Footer 元素 |
| Dashboard | 20 | 快捷卡片 + Gateway 状态 |
| Chat | 25 | 渠道标签 + 会话列表 + 消息操作 |
| Config | 25 | 折叠区 + 输入框 |
| Tasks | 20 | 任务列表 + CRUD 操作 |
| BgTasks | 18 | 空状态 + 任务卡片 |
| Memory | 18 | Tab 切换 + 编辑器 |
| Media | 22 | 搜索 + 分页 + 图片记录 |
| Persona | 15 | 文件 Tab + 编辑器 |
| Skills | 18 | 技能卡片 + 启用/禁用 |
| Tokens | 22 | 明细/聚合 Tab + 过滤器 + 汇总 |
| 测试环境 | 8 | 浏览器/账号/时间信息 |

每个页面章节独立性好，拆分无需额外重写，只需提取 + 补充 frontmatter。

### 2.4 合并后目录结构设计

```
ava/skills/console_ui_dev_loop/
├── SKILL.md                          # 合并后主 skill（mode=regression | dev_loop）
├── evals/
│   └── evals.json                    # 保持不变
└── references/
    ├── loop-contract.md              # 保留（dev_loop 模式专属）
    ├── testing-task.md               # 保留（dev_loop 模式专属）
    ├── verifier-policy.md            # 保留（两种模式共享）
    ├── page-registry.md              # 从 page-selection.md 重构：页面注册表 + 文件映射 + 权限矩阵
    ├── auth.md                       # 新建：认证流程（mock_tester 密码文件、登录操作、session 复用）
    └── pages/                        # 新建：按页拆分的页面知识
        ├── _sidebar.md               # Sidebar 共享元素
        ├── dashboard.md
        ├── config.md
        ├── tasks.md
        ├── bg-tasks.md
        ├── memory.md
        ├── media.md
        ├── persona.md
        ├── skills.md
        ├── chat.md
        └── tokens.md
```

### 2.5 SKILL.md 合并策略

合并后的 SKILL.md 需要处理两种模式：

- **regression 模式**：用户说"测一下 console-ui"、"对 console-ui 做 smoke 测试"
  - 只测不修，输出结构化报告
  - 引用：`page-registry.md` + `auth.md` + `pages/{page}.md` + `verifier-policy.md`
- **dev_loop 模式**：用户说"修这个 console-ui 页面并回归"、"做完后继续测直到通过"
  - coding → regression → retry 闭环
  - 额外引用：`loop-contract.md` + `testing-task.md`

SKILL.md 本身不重复 references 的内容，只描述流程骨架和引用指令。

## 2.1 Next Actions

- 确认 Open Questions
- 进入 Plan 阶段，定义具体文件变更清单

## 3. Innovate

### Option A: 纯合并，Pages.md 保持单文件

- Pros:
  - 实现最简单
  - 消除 skill 选择困惑
- Cons:
  - Token 浪费问题未解决
  - Pages.md 在 `console_ui_dev_loop/references/` 里仍是 317 行巨型文件

### Option B: 合并 + Pages.md 按页拆分

- Pros:
  - 消除 skill 选择困惑
  - 消除重复内容
  - 按需加载页面知识，token 节省 ~90%
  - 编辑隔离，git diff 更清晰
  - 与现有 `references/` 目录模式一致
- Cons:
  - 文件数量增加（11 个页面 md + 1 个 sidebar + 1 个 auth）
  - SKILL.md 需要写清楚"何时读哪个 reference"

### Option C: 不合并，只拆 Pages.md

- Pros:
  - 改动最小
  - 解决 token 问题
- Cons:
  - 两个 skill 的重复和选择困惑问题未解决
  - 拆出的页面 md 放在哪个 skill 目录下仍有歧义

### Decision

- Selected: `Option B`
- Why: 这是前序 spec 已确认方向的自然延伸。合并消除重复和选择困惑，拆分解决 token 效率。两者正交，同时做成本不比单独做高多少。

## 4. Plan (Contract)

### 4.1 File Changes

**删除**：
- `ava/skills/console_ui_regression/SKILL.md` — 合并到 dev_loop
- `ava/skills/console_ui_regression/Pages.md` — 拆分到 per-page references
- `ava/skills/console_ui_regression/` — 整个目录删除

**新建**：
- `ava/skills/console_ui_dev_loop/references/auth.md` — 认证流程
- `ava/skills/console_ui_dev_loop/references/pages/_sidebar.md` — Sidebar 共享元素
- `ava/skills/console_ui_dev_loop/references/pages/dashboard.md`
- `ava/skills/console_ui_dev_loop/references/pages/config.md`
- `ava/skills/console_ui_dev_loop/references/pages/tasks.md`
- `ava/skills/console_ui_dev_loop/references/pages/bg-tasks.md`
- `ava/skills/console_ui_dev_loop/references/pages/memory.md`
- `ava/skills/console_ui_dev_loop/references/pages/media.md`
- `ava/skills/console_ui_dev_loop/references/pages/persona.md`
- `ava/skills/console_ui_dev_loop/references/pages/skills.md`
- `ava/skills/console_ui_dev_loop/references/pages/chat.md`
- `ava/skills/console_ui_dev_loop/references/pages/tokens.md`

**重写**：
- `ava/skills/console_ui_dev_loop/SKILL.md` — 合并后的主 skill，增加 mode 区分
- `ava/skills/console_ui_dev_loop/references/page-selection.md` → 重命名为 `page-registry.md`，整合权限矩阵

**不变**：
- `ava/skills/console_ui_dev_loop/references/loop-contract.md`
- `ava/skills/console_ui_dev_loop/references/testing-task.md`
- `ava/skills/console_ui_dev_loop/references/verifier-policy.md`
- `ava/skills/console_ui_dev_loop/evals/evals.json`
- `ava/skills/page_agent_test/SKILL.md`

### 4.2 Signatures

#### SKILL.md 结构骨架

```markdown
---
name: console_ui_dev_loop
description: Console-UI 前端开发与回归测试。支持两种模式：
  regression（只测不修）和 dev_loop（coding→regression→retry 闭环）。
metadata: {"nanobot":{"emoji":"🔁"}}
---

# Console UI Dev Loop

## 模式选择
- mode=regression: "测一下 console-ui" / "做 smoke 测试"
- mode=dev_loop: "修这个页面并回归" / "做完继续测直到通过"

## 先读（两种模式共享）
- references/page-registry.md
- references/auth.md
- references/pages/{target_page}.md + references/pages/_sidebar.md

## dev_loop 模式额外读
- references/loop-contract.md
- references/testing-task.md

## 两种模式共享
- references/verifier-policy.md

## [regression 模式流程]
## [dev_loop 模式流程]
```

#### page-registry.md 结构

```markdown
# Page Registry

## 页面注册表（含权限矩阵）
| key | path | 权限要求 | 源文件 | 详细 reference |

## 文件 -> 页面映射
| 文件路径模式 | 受影响页面 |

## 页面选择优先级
1. explicit_pages
2. changed_files 映射
3. baseline_smoke
4. full_regression
```

#### auth.md 结构

```markdown
# 认证流程

## 测试账号
- mock_tester: <console_dir>/local-secrets/mock_tester_password
- nanobot (admin): <console_dir>/local-secrets/nanobot_password

## 登录操作
- page_agent(execute) 在 /login 页面填写并提交

## session 复用
- 登录后复用 session_id

## 权限说明
- users 页面仅 admin 可访问
- mock_tester 无权限的页面标记 skipped(AUTH_REQUIRED)
```

#### 单个页面 reference 结构（以 config.md 为例）

```markdown
# Config 页面

**路由**: /config
**页面标题**: 配置管理
**权限**: 任意已登录

## 可操作元素
| 元素 | 类型 | 作用 |

## 检查项
| check_id | 检查内容 | 断言方式 |

## instruction 示例
"检查页面是否显示重载和保存按钮，展开通用配置区域..."
```

### 4.3 Implementation Checklist

- [x] 1. 新建 `references/auth.md`，提取认证流程
- [x] 2. 新建 `references/pages/_sidebar.md`，提取 Sidebar 共享元素
- [x] 3. 将 Pages.md 拆分为 11 个 `references/pages/{page}.md` 文件
- [x] 4. 为每个页面 md 补充 check_id 模式和 instruction 示例
- [x] 5. 重命名 `page-selection.md` → `page-registry.md`，整合权限矩阵（从 regression SKILL.md 合入）
- [x] 6. 重写 `SKILL.md`：合并 regression 和 dev_loop 模式，引用新 references 结构
- [x] 7. 删除 `ava/skills/console_ui_regression/` 整个目录
- [x] 8. 验证：确认所有 references 文件路径正确、无悬挂引用
- [x] 9. 更新本 task spec 状态

## 5. Execute Log

- [x] Step 1: 新建 `references/auth.md`（认证流程、测试账号、session 复用、权限矩阵）
- [x] Step 2: 新建 `references/pages/_sidebar.md`（导航项表 + Footer + 通用检查项）
- [x] Step 3-4: 将 Pages.md 拆分为 11 个 per-page references，每个含检查项表和 instruction 示例
  - dashboard / config / chat / tasks / bg-tasks / memory / media / persona / skills / tokens
- [x] Step 5: `page-selection.md` → `page-registry.md`，整合权限矩阵（含 users / browser 的权限标注）
- [x] Step 6: 重写 SKILL.md，合并 regression + dev_loop 两种模式，所有 references 引用指向新路径
- [x] Step 7: 删除 `ava/skills/console_ui_regression/` 整个目录
- [x] Step 8: 验证无悬挂引用（grep `console_ui_regression`、`page-selection` 均为 none）

## 6. Review Verdict

- Spec coverage: PASS — 9/9 checklist 项全部完成
- Behavior check: PASS — SKILL.md 引用的 17 个 references 文件全部存在，无悬挂引用
- Regression risk: Low — 只影响 skill 静态文件，不涉及 Python/TS 代码变更
- Module Spec 需更新: No — 本任务只重组 skill 文件，未变更工具代码或 API
- Follow-ups:
  - `loop-contract.md` 和 `testing-task.md` 中仍引用 `page-selection.md` 的概念名"页面选择"，但实际路径引用已在 SKILL.md 层统一为 `page-registry.md`，无需额外改动
  - `evals/evals.json` 保持不变，内容仍适用于合并后的 skill
  - 历史 task spec 中对 `console_ui_regression` 的引用属于历史记录，不修改

## 7. Plan-Execution Diff

- 与计划完全一致，无偏离
