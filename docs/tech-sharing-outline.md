# 技术分享大纲：怎么让 AI 帮你改代码，但不把项目改坏

> 从 OpenClaw 的困境到 Nanobot/Ava 的 Harness 实践
> 主讲人：方壶 | 预计时长：60 分钟

---

## 核心信息（全场只让听众记住一句话）

> **我不是只会用 AI 写代码，我会给 AI 设计边界——把一个个人 AI 助手做成了一个有边界、有状态、有验证、有生命周期的 agent harness 系统。**

---

## 一、开场：OpenClaw 的爆火与龙虾悖论（5 分钟）

### 从现象出发

- OpenClaw（龙虾）现象：GitHub 三十多万星的现象级项目，全球出圈
- 它能做什么：接管键盘鼠标、自动整理文件、起草邮件、填写表格
- 听起来很酷，但——

### 龙虾悖论
>
> 想让它做的事情越多，给它的权限必须越大；权限越大，安全风险就越高。

- 第三方安全报告称，3000+ 插件中约 10.8% 包含恶意代码
- 用户账户被盗刷、文件被一键清空
- AI "自作主张"改了不该改的东西

### 转折

- 这不只是 OpenClaw 的问题——Cursor、Claude Code、Codex 在工程项目中也面临类似困境
- AI 足够聪明，但"聪明"恰恰是问题——它会自己决定改哪里、怎么改、什么时候"完成"
- **OpenClaw 证明了 Agent 产品能爆发，也暴露了自治系统的权限、插件、维护、攻击面问题**
- Nanobot 的价值不在于"比 OpenClaw 大"，而在于"更轻、更可读、更适合做受控实验"（Nanobot README 自述："Inspired by OpenClaw, 99% fewer lines"）
- 引出问题：怎么让 AI 改代码但不把项目改坏？

### ⚠️ 需要准备

- [ ] OpenClaw 新闻截图作为视觉元素
- [ ] 龙虾悖论的一句话定义放在 slide 上

---

## 二、Harness Engineering：Agent 时代的工程范式（8 分钟）

> 🎯 不是"介绍一个概念"，而是"介绍一个正在形成的工程学科，并展示我真的在项目里做了一个 harness"

### 2.1 三个来源，一个共识

**OpenAI 的启发**：

- Codex 团队的内部实验：用 Agent 构建了超过百万行代码的应用
- 核心观点：**Humans steer. Agents execute.** 工程师的工作从"亲手写代码"转向"设计环境、表达意图、搭反馈回路"
- 把规则编码成仓库内版本化文件，且需要周期性清理避免腐化

**Anthropic 的启发**：

- 长时程 Agent 靠 initializer、feature list、progress file、init.sh、E2E 验证才能跨 context 持续推进
- 没有 harness 的 Agent 和有 harness 的 Agent，差距不是边际改进，是"能不能用"的质变

**Learn Harness Engineering 的抽象**：

- 把上述做法收束成五子系统：Instructions / State / Verification / Scope / Lifecycle
- Harness 不让模型更聪明，它让模型的输出更可靠

```
┌─────────────────────────────────────────────────┐
│                  THE HARNESS                     │
│                                                  │
│  Instructions    State         Verification      │
│  (做什么)        (做到哪了)     (做对了吗)         │
│                                                  │
│  Scope           Session Lifecycle               │
│  (一次只做一件事)  (开始初始化、结束清理)            │
└─────────────────────────────────────────────────┘

模型决定写什么代码。Harness 治理何时、何地、怎么写。
```

### 2.2 Ava 的 Harness 设计——五子系统在我项目里的真实落地

| Harness 子系统 | Ava 当前实现 |
|---|---|
| **Instructions** | AGENTS.md / CLAUDE.md / ava/templates/TOOLS.md（工具使用指引 + 委托策略）/ .specanchor/global/（Global Spec） |
| **State** | .specanchor/ 三级 Spec 体系（上下文记忆）/ ava/agent/bg_tasks.py（后台任务状态机）/ session 持久化 |
| **Verification** | .githooks/pre-commit / tests/guardrails/（nanobot 禁改检测、patch 结构检测、Spec 同步检测）/ ava/console/ui_build.py（前端产物新鲜度检测） |
| **Scope** | nanobot/ 禁改规则 + ALLOW_NANOBOT_PATCH 例外机制 / strict schema gate（如 sdd-riper-one）+ Task Spec 作为载体 / patch_map 热区管理 |
| **Lifecycle** | python -m ava 启动 → patch apply → gateway_control / auto_continue 续跑 / auto rebuild / supervisor-first restart |

<!-- speaker note: 这页是全场最重要的一页——从"我知道一个概念"变成"我真的做了一个 harness"。 -->

### 2.3 SpecAnchor 在 Harness 中的角色

> **SpecAnchor = 面向 Agent 开发的 spec governance layer。**
> 它不替代 OpenSpec、Spec Kit 或 SDD-RIPER-ONE；它负责的是：spec 放哪、该加载哪份 spec、spec 是否过期、task 结论如何回流到模块知识。

在 Ava 的 harness 里，SpecAnchor 负责 **State（共享记忆）和 Scope（治理边界）**：Global / Module / Task 分层、上下文按需加载、Task 结果回流、Spec 新鲜度检查。至于 Plan Approved 这类门禁，来自它集成的 strict schema（如 sdd-riper-one），不是 SpecAnchor 自身提供的。

如果说 OpenSpec / Spec Kit 更像是在回答"这次需求怎么写成 spec"，那 SpecAnchor 回答的是"项目里的 spec 变多以后，怎么组织、加载、同步和治理"。

### ⚠️ 需要准备

- [ ] Ava Harness 五子系统映射表（做成 slide）
- [ ] 三个来源的核心观点做成一页三栏对比

---

## 三、Nanobot/Ava：我做了一个怎样的系统（10 分钟）

> 🎯 先让听众看到系统的全貌和已有能力，再讲约束

### 3.1 为什么是 Nanobot

- **不是因为 Nanobot 更酷，而是因为它更轻、更可读、更适合做 harness 实验**
- Nanobot 自述："Inspired by OpenClaw, 99% fewer lines"——核心能力完整，但规模让个人开发者能真正理解和掌控
- 支持 Telegram/飞书/Discord 等多通道，核心能力：工具调用、记忆、多轮对话、后台任务

### 3.2 Ava 是我基于 Nanobot 做的个人 AI 助手

- **不是 fork，是 Sidecar**——近万行扩展代码，把日常 upstream 同步的冲突从结构上压到最小
- Ava 在 Nanobot 上加了一层 sidecar harness，从"能跑的 agent"变成"可治理的 agent 系统"
- 已有能力一览：
  - Sidecar 配置兼容 + Gateway + Web Console
  - 自定义工具：Claude Code CLI、Codex CLI、图片生成、视觉识别、贴纸生成、记忆系统
  - 13 个 patch 模块，涵盖 schema / config / loop / context / tools / skills / storage / 等
  - Supervisor 生命周期管理（Docker/systemd 自动拉起）
  - 后台异步任务：编码任务自动通知 + 自动续跑 + 前端自动重建
  - SpecAnchor 三级规范体系

### 3.3 带人工监督的研发半闭环

> 我用 AI（Cursor + Claude Code）来给 Ava 写功能。Ava 自己也是一个 AI Agent。

**已经打通的部分**：

- Development loop：任务委托 → 后台执行 → 自动续跑 → 前端自动重建
- Runtime loop：supervisor-first lifecycle、gateway_control

**尚未闭合的部分**：

- Release loop：自动 commit / 自动 PR / 自动部署仍需人工参与
- 所以叫"半闭环"——人类仍然是最终决策者

### ⚠️ 需要准备

- [ ] Ava 架构全景图（Nanobot 核心 + Ava Sidecar + Console + Tools）
- [ ] 代码行数统计：nanobot/ 多少行 vs ava/ 多少行
- [ ] 1-2 分钟 demo 录屏：完整展示一次"带人工监督的 AI 改 AI"流程
- [ ] "半闭环"示意图：哪些环已通，哪些还需人工

---

## 四、三个真实问题：改错地方、改完不收尾、改完看不到（15 分钟）

> 🎯 全场高潮。先讲症状（人话），再讲机制（术语）。每个故事映射回 Harness 子系统。

### 故事 1：改错地方——AI 越过边界改了上游代码

**症状**：让 AI 修一个 bug，AI 分析后认为"改上游更简单"，直接改了 nanobot/ 的代码

**为什么会这样**：

- CLAUDE.md 写了"禁止改 nanobot/"，但 AI 会在"效率"和"规则"之间权衡
- 规则在提示词里，不在架构里——AI 有能力违反

**怎么修（三层防御）**：

- Layer 1（Instructions）：加强 CLAUDE.md 和 tool description 的措辞
- Layer 2（Verification）：guardrail 测试自动检测是否误改 nanobot/
- Layer 3（Scope）：Sidecar 把默认扩展路径收束到 ava/，误改 nanobot/ 会被 hook 和 guardrail 测试及时拦截

**Harness 映射**：Instructions + Verification + Scope

---

### 故事 2：改完不收尾——后台任务完成但 agent 不继续

**症状**：Claude Code 后台跑完了代码修改，Telegram 通知了我，但 agent 不会自动处理后续步骤

**为什么会这样**：

- 完成回调只做了"通知用户"，没有触发 agent loop 继续
- 相当于员工完成了任务汇报了领导，但领导没有安排下一步

**怎么修**：

- `auto_continue` 机制：任务完成后自动在原会话中注入结果，触发 agent 继续
- 每个会话最多自动续跑 5 次（continuation budget），防止无限循环
- 用户发新消息时 budget 重置

**Harness 映射**：Lifecycle + State

---

### 故事 3：改完看不到——前端改了但没有效果

**症状**：AI 修改了前端 TypeScript 代码，截图显示"已完成"，但实际页面没变

**为什么会这样**：

- AI 不知道改完前端代码还需要 `npm run build`
- AI 看了截图认为"完成了"——这正是 Harness Engineering 说的 "confidence ≠ correctness"

**怎么修**：

- Post-task hook：任务完成后自动检测 console-ui 产物是否过期（源码 mtime > dist mtime）
- 过期则自动 rebuild，不依赖 AI 记住构建步骤

**Harness 映射**：Verification（产物新鲜度检测）

---

### 约束的分层设计（总结图）

```
┌──────────────────────────────────────────┐
│ Layer 4: CI / Guardrail Tests            │ ← 最终兜底（Verification）
├──────────────────────────────────────────┤
│ Layer 3: Post-task Hooks                 │ ← 自动补救（Lifecycle）
│   (auto rebuild / continuation)          │
├──────────────────────────────────────────┤
│ Layer 2: Tool Description + Spec         │ ← 影响 AI 决策（Instructions + State）
│   (委托优先 / 模块契约 / SpecAnchor)      │
├──────────────────────────────────────────┤
│ Layer 1: CLAUDE.md / AGENTS.md           │ ← 文档规范（Instructions）
└──────────────────────────────────────────┘

每一层不需要 100% 可靠。四层组合 + Sidecar 架构约束（Scope），覆盖面足够。
```

### ⚠️ 需要准备

- [ ] 每个故事准备一个 Before/After 的截图（git diff 或代码对比）
- [ ] 找到 git log 中 AI 误改 nanobot/ 的真实 commit
- [ ] Continuation budget 工作流程图
- [ ] 前端 rebuild 检测逻辑的简化示意图

---

## 五、个人优势显性化——不只是踩坑，是体系化能力（5 分钟）

> 🎯 直接讲"我厉害在哪"，不要让听众自己悟

### 三层能力

**1. 架构判断力**

- 选择了 Sidecar 而不是 fork——这个决定让日常 upstream 同步的冲突从结构上降到最小
- Monkey Patch 模式：13 个 patch 模块，按字母序加载，每个都有 guard 检查
- 判断什么放 patch、什么放 fork、什么该提 PR 给上游

**2. 治理意识**

- 不满足于"写个提示词 AI 就会听话"
- 把 prompt 失效的地方变成了：测试 + hook + 运行时控制面
- 用 SpecAnchor 把经验沉淀成团队和 AI 都能遵守的工程契约

**3. 闭环落地能力**

- 不是只看到问题，而是把问题变成了代码：
  - "AI 改完了但没闭环" → continuation + auto rebuild + console control
  - "AI 不听话改了上游" → guardrail tests + CI + Sidecar 架构
  - "经验会丢失" → SpecAnchor 三级 Spec + Task Spec 知识回流

### 一句话总结
>
> 我不是单纯会用 AI 写代码。我会给 AI 设计边界。我不是只会写 prompt，我会把 prompt 失效的地方变成测试、hook、运行时控制面。

### ⚠️ 需要准备

- [ ] 一张"三层能力"的总结 slide
- [ ] Monkey Patch 的真实例子（loop_patch.py 的 diff）

---

## 六、可复用的模式（3 分钟）

### 你今天就能带走的三个模式

**模式 1：Sidecar 扩展**

- 依赖开源项目但需要深度定制？不要 fork，在旁边扩展
- 前提：上游代码有足够的可 patch 点
- 成本：patch 维护 + 上游变更追踪

**模式 2：软硬护栏组合**

- 软护栏（提示词 / Spec）决定 AI"想做什么"
- 硬护栏（测试 / CI / Hook）决定 AI"能做什么"
- 两者缺一不可

**模式 3：Post-task 自动化**

- AI 改完代码后有固定后续步骤（build、lint、deploy）？
- 不依赖 AI 记住，用 hook 系统级兜底

---

## 七、Q&A + 讨论（5-10 分钟）

### 预设 Q&A

1. **Q: Monkey Patch 会不会很脆弱，上游改了就挂？**
   A: 会。所以每个 patch 里有 guard 检查，上游改了就跳过并告警。这是维护成本的一部分，但比 fork 的合并成本低得多。

2. **Q: 这套约束体系对小项目值得吗？**
   A: 如果项目持续迭代 3 个月以上且频繁用 AI Coding，那值得。否则 AGENTS.md 加几条规则就够了——这本身就是 Harness 的最小形态。

3. **Q: 能不能直接让 AI 自己设计约束？**
   A: 可以，本次分享的很多约束就是 AI 参与设计的。但 AI 设计的约束在边界情况容易遗漏，必须人 review。这也是为什么叫"半闭环"。

4. **Q: Token 消耗和成本怎么样？**
   A: Harness 文件会增加 context 消耗，但减少了返工。真实项目里，harness 增加上下文成本，但通常减少返工，净效果是省钱的。

5. **Q: Nanobot 和 OpenClaw 的区别？**
   A: Nanobot 自述"Inspired by OpenClaw, 99% fewer lines"。OpenClaw 是一个成熟的 Agent 产品，Nanobot 更轻、更可读，适合个人开发者理解和掌控。我选它不是因为它"更好"，而是因为它的规模让 harness 实验可行。

6. **Q: SpecAnchor 和 Spec Kit / OpenSpec / Kiro 的区别？**
   A: Spec Kit / OpenSpec / Kiro 更偏 spec authoring 和 workflow；SpecAnchor 更偏 spec governance。它不替代你怎么写 spec，而是负责 spec 放哪、怎么加载、怎么保持新鲜。

---

## 附录 A：可直接引用的 .specanchor/ 文件

以下文件可以直接截图或节选放入演讲 slide 中：

### 作为 "Harness 真实落地" 证据

| 文件 | 用途 | 在哪一章引用 |
|------|------|------------|
| `.specanchor/global/architecture.md` | Global Spec 实物：Sidecar 架构规范（零侵入上游、Monkey Patch 优先、Fork 作为最后手段） | 第二章 Instructions 映射 / 第五章 架构判断力 |
| `.specanchor/modules/module-index.md` | Module Spec 索引实物：13 个 patch 模块 + 6 个功能模块，全部有 Spec 覆盖状态 | 第二章 State 映射 / 第三章 系统全貌 |
| `.specanchor/patch_map.md` | Patch 热区图：标注哪些 patch 是高频修改区、哪些是稳定区 | 第二章 Scope 映射 / 第五章 治理意识 |

### 作为 "SpecAnchor 实战" 演示素材

| 文件 | 用途 | 在哪一章引用 |
|------|------|------------|
| `.specanchor/tasks/2026-04-05_self-improvement-loop-e2e-closure.md` | Task Spec 实物：Research → Plan → Execute 的实际流程记录（⚠️ frontmatter 有 sdd_phase 冲突，定稿前需清理或换用更干净的 Task Spec） | 第二章 SpecAnchor 角色 / 第四章 故事串联 |
| `.specanchor/tasks/2026-04-04_lifecycle-and-frontend-hotupdate.md` | 前序 Task Spec：lifecycle + frontend hot-update 的规划和执行 | 第四章 故事 2、3 的前因 |
| `.specanchor/tasks/2026-04-02_gateway-lifecycle-supervisor-redesign.md` | supervisor-first 架构的设计决策记录 | 第三章 半闭环 / 第五章 闭环落地 |

### 作为 "Sidecar 架构" 说明

| 文件 | 用途 | 在哪一章引用 |
|------|------|------------|
| `.specanchor/2026-03-24-15-48-文档-Sidecar架构与MonkeyPatch实践说明.md` | Sidecar + Monkey Patch 的完整技术说明，包含安全拦截、记忆补强等真实案例 | 第三章 / 第五章 |
| `.specanchor/global/architecture.md` + `ava/README.md` | 架构规范 + 快速上手指南的组合 | 第三章 系统全貌 |

---

## 附录 B：准备 Checklist

### 演示材料

- [ ] OpenClaw 新闻截图（视觉 hook）
- [ ] 三个来源（OpenAI / Anthropic / Learn HE）核心观点三栏对比
- [ ] Harness 五子系统图
- [ ] **Ava Harness 五子系统映射表**（最重要的一页！）
- [ ] SpecAnchor 定位一句话页（governance layer，不是完整 harness）
- [ ] Nanobot + Ava 架构全景图
- [ ] 代码行数统计（nanobot/ vs ava/）
- [ ] 1-2 分钟 demo 录屏（带人工监督的 AI 改 AI 流程）
- [ ] "半闭环"示意图（哪些环已通，哪些还需人工）
- [ ] 3 个故事的 Before/After 截图
- [ ] AI 误改 nanobot/ 的真实 git commit
- [ ] Continuation budget 流程图
- [ ] 前端 auto-rebuild 逻辑示意图
- [ ] Monkey Patch 真实 diff（loop_patch.py）
- [ ] 三层能力总结 slide
- [ ] .specanchor/ 文件截图（见附录 A）

### 内容节奏

- 前 5 分钟：OpenClaw hook + 问题引入（抓注意力）
- 5-13 分钟：Harness Engineering 三个来源 + Ava 映射 + SpecAnchor 定位（建立框架 + 证明落地）
- 13-23 分钟：Ava 系统全貌 + demo（展示能力）
- 23-38 分钟：三个故事（核心高潮）
- 38-43 分钟：个人优势 + 可复用模式（升华）
- 43-50+ 分钟：Q&A（互动）

### 参考来源

- OpenAI: [Harness engineering](https://openai.com/index/harness-engineering/)
- Anthropic: [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Anthropic: [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- Learn Harness Engineering: [walkinglabs/learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering)
- LangChain: [Improving Deep Agents with Harness Engineering](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/)
- Martin Fowler: [Harness Engineering](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html)
- OpenClaw: [GitHub repo](https://github.com/openclaw/openclaw)
- 第三方 OpenClaw 安全报告: [SecurityBoulevard](https://securityboulevard.com/2026/02/openclaw-open-source-ai-agent-application-attack-surface-and-security-risk-system-analysis/)
- SpecAnchor: [spec-anchor repo](https://github.com/aone-open-skill/spec-anchor)
