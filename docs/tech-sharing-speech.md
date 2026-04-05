# 技术分享演讲稿：怎么让 AI 帮你改代码，但不把项目改坏

> 从 OpenClaw 的困境到 Nanobot/Ava 的 Harness 实践
> 主讲人：方壶 | 预计时长：60 分钟

---

## 一、开场：OpenClaw 的爆火与龙虾悖论（5 分钟）

大家好，我是方壶。今天想跟大家聊一个我最近一直在琢磨的问题——**怎么让 AI 帮你改代码，但不把项目改坏**。这个命题很大，从我上次和大家聊过的SDD-RIPER-ONE到今天讲的这个，都是对这个命题的探索。现在业界比较火的 Harness Engineering 也是如此。我今天来是跟大家分享我自己对这个命题的探索和实践。

先从一个现象说起。

OpenClaw 大家现在已经都很熟悉了——就是那个 GitHub 上三十多万星的 AI 桌面助手。它能接管你的键盘鼠标，帮你自动整理文件、起草邮件、填写表格。听起来特别酷，对吧？

但这里有一个很微妙的矛盾，我管它叫**"龙虾悖论"**：

> **你想让它做的事情越多，给它的权限就必须越大；权限越大，安全风险就越高。**

这不是我自己编的——第三方安全报告显示，OpenClaw 3000 多个插件中，大约 10.8% 包含恶意代码。用户账户被盗刷、文件被一键清空的事情真实发生过。

`[📊 slide：OpenClaw 新闻截图 + 龙虾悖论一句话定义]`

大家想一下，这个问题其实不只是 OpenClaw 的。我们日常用 Cursor、Claude Code、Codex 写代码的时候，是不是也面临类似的困境？我们经常被弹窗要求赋予各种权限，一开始还装模作样的看一下，后面索性直接全允许，现在我都不看到底给什么权限了，反正有弹窗我就点允许。

AI 足够聪明，但"聪明"恰恰是问题的一部分——它会**自己决定**改哪里、怎么改、什么时候算"完成了"。

打个比方：**AI 就像一个特别能干但没有边界感的实习生**。你让它帮你改一个按钮的颜色，它可能顺手把你的组件库重构了。你让它修一个 bug，它可能觉得改上游源码更快。能力是真的强，但如果没有边界，能力越强，翻车越狠。

这就引出了我今天想分享的核心：**怎么给 AI 设计边界？**

我自己在做一个 AI 助手项目的过程中，摸索出了一些实践。不敢说是什么最佳方案，但确实解决了几个让我很头疼的真实问题。希望今天的分享能给大家一些参考。

---

## 二、Harness Engineering：一个正在形成的工程范式（8 分钟）

在讲我自己的实践之前，先跟大家分享一个最佳很火的概念——**Harness Engineering**，我叫他

这个词最近在 AI 工程圈里被频繁提到。不同的公司从不同角度得出了类似的结论，我觉得特别有意思。

### 三个来源，一个共识

`[📊 slide：三栏对比——OpenAI / Anthropic / Learn Harness Engineering]`

**OpenAI 那边**，Codex 团队用 Agent 构建了超过百万行代码的应用。他们总结出一个核心观点：**Humans steer, Agents execute**——人类负责掌舵，Agent 负责执行。工程师的工作从"亲手写每一行代码"转向"设计环境、表达意图、搭反馈回路"。

**Anthropic 那边**，他们发现长时程 Agent——就是那种需要跑几个小时甚至几天的任务——必须靠一系列机制才能跨 context 持续推进。没有这些机制的 Agent 和有这些机制的 Agent，差距不是"好一点"，是"能不能用"的质变。

**Learn Harness Engineering** 这个社区把上面这些做法收束成了五个子系统：

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

用一个大家可能更熟悉的类比：**Harness 之于 AI Agent，就像 CI/CD 之于人类开发者。**

CI/CD 不会让你写代码写得更好，但它确保了你提交的代码必须通过 lint、通过测试、通过 review 才能上线。Harness 做的是同样的事，只不过对象从人变成了 AI。

或者换一个更生活化的比方：**Harness 就像给 AI 这个新生宝宝准备的铺满软垫的游乐场**。它不管 AI 在里面怎么玩，但它确保 AI 不会玩出圈。游乐场不让你玩得更好，但让你的"好"更可靠。

### 我的项目里的 Harness 落地

我自己在做 Ava 这个项目的时候，其实一开始并没有"Harness"这个概念，这个概念当时也没在网上有人讨论。是踩了几次坑之后，回头看才发现：我做的这些东西，刚好映射到了这五个子系统。

`[📊 slide：Ava Harness 五子系统映射表——这是全场最重要的一页]`

| Harness 子系统 | 一句话解释 | Ava 当前实现 |
|---|---|---|
| **Instructions** | 告诉 AI 该做什么、不该做什么 | AGENTS.md / CLAUDE.md / 工具描述里的委托策略 / SpecAnchor 全局规范 |
| **State** | 让 AI 知道"做到哪了" | SpecAnchor 三级 Spec 体系 / 后台任务状态机 / 会话持久化 |
| **Verification** | 验证 AI 做对了没 | .githooks/pre-commit 拦截 / guardrail 测试（5 个） / 前端产物新鲜度检测 |
| **Scope** | 限制 AI 一次只能动哪里 | nanobot/ 禁改规则 + ALLOW_NANOBOT_PATCH 例外机制 / Sidecar 架构天然约束 |
| **Lifecycle** | 管理 AI 任务的开始和结束 | python -m ava 启动 → patch 加载 → 后台任务自动续跑 → 前端自动重建 → supervisor 重启 |

大家可能注意到 SpecAnchor 出现在了好几个子系统里。简单说一下它的定位：**SpecAnchor 是面向 AI 开发的 spec 治理层**。它不管你怎么写 spec，它管的是——项目里的 spec 变多以后，放在哪、该加载哪份、是否过期。在 Ava 的 Harness 里，它同时承担了 State（让 AI 获取最新的模块上下文）和 Scope（通过模块契约约束 AI 的改动范围）的角色。后面讲故事的时候会再提到它。

这里我特别想强调一点：**这些不是设计出来的，是被问题逼出来的。** 每一个子系统的背后，都有一个让我当时很头疼的真实故事。后面我会详细讲。

---

## 三、Nanobot/Ava：我做了一个怎样的系统（10 分钟）

好，接下来给大家介绍一下我这个项目的全貌。

### 为什么选择 Nanobot

市面上做类似 OpenClaw 的 AI Agent 的框架很多，我选择 Nanobot 的原因很简单：**它足够轻、足够可读**。

Nanobot 的 README 里有一句自述："Inspired by OpenClaw, 99% fewer lines"。意思是它受 OpenClaw 启发，但只用了 1% 的代码量。核心能力——工具调用、记忆、多轮对话、多通道接入——一个不少，但规模让个人开发者能真正理解和掌控。

这就像**你可以选择买一台顶配的 Mac Studio，也可以选择自己组装一台台式电脑**。Mac Studio是通用的工业流水线作品，每个问题几乎都可以在社区找到解答或者是现成的解决方案，但自己组装一台电脑会让你拧到每一颗螺丝，真正理解电脑的构成。如果你的目标是"学会怎么组装电脑 & 真正理解电脑的构成"，台式电脑反而是更好的选择。

### Ava 是我基于 Nanobot 做的个人 AI 助手

Ava 不是 Nanobot 的 fork，而是 **Sidecar**。

什么意思？打个比方：**fork 就像把别人的房子的图纸抄过来拆了重建，Sidecar 就像在旁边搭了一个连廊**。房子（nanobot/）保持原样，连廊（ava/）可以任意装修。等上游更新了，你只需要刷新房子那边，连廊不受影响。

从数字上看：

- nanobot/ 上游代码约 **23,000 行**
- ava/ 我写的 Sidecar 扩展约 **14,000 行**

`[📊 slide：代码行数统计对比图]`

### 已有能力一览

`[📊 slide：Ava 架构全景图——Nanobot 核心 + Ava Sidecar + Console + Tools]`

**14 个 Monkey Patch 模块**，涵盖：

- 配置 Schema 扩展（a_schema_patch）
- 消息总线监听（bus_patch）
- 上下文压缩 + 记忆注入（context_patch）
- 核心循环注入——数据库、Token 统计、后台任务、生命周期管理（loop_patch）
- 技能发现（skills_patch）
- SQLite 持久化（storage_patch）
- 8 个自定义工具注册（tools_patch）
- 前端 Console 启动注入（console_patch）
- 等等

**8 个自定义工具**：

- Claude Code CLI / Codex CLI（代码任务委托）
- 网关控制（restart/status）
- 图片生成 / 视觉识别 / 表情包发送
- 分层记忆系统
- 网页浏览

**Web Console**（React + TypeScript）：

- 实时聊天界面（WebSocket 流式输出）
- 后台任务监控
- Token 用量统计
- 记忆管理
- 技能管理
- 配置热更新

**后台任务系统**：

- 编码任务异步执行 → 完成通知 → 自动续跑（最多 5 次）
- 任务状态持久化到 SQLite
- 时间线事件追踪

**Supervisor 生命周期管理**：

- 支持 Docker / systemd 自动拉起
- 优雅关闭（drain → 中断标记 → 退出）
- 启动代次追踪（用于孤儿任务恢复）

### 带人工监督的研发半闭环

这是我觉得最有意思的部分。我用 AI（Cursor + Claude Code）来给 Ava 写功能。而 Ava 自己也是一个 AI Agent。

**已经打通的部分**：

- 开发闭环：任务委托 → 后台执行 → 自动续跑 → 前端自动重建
- 运行闭环：supervisor-first 生命周期、网关控制

**尚未打通的部分**：

- 发布闭环：自动 commit / 自动 PR / 自动部署——目前这些还是我手动做的

所以我管它叫**"半闭环"**——AI 是主要执行者，但人类仍然是最终决策者。

`[📊 slide："半闭环"示意图——哪些环已通（绿色），哪些还需人工（黄色）]`

### Demo

`[🎬 播放 1-2 分钟 demo 录屏：展示一次完整的"通过 Telegram 给 Ava 派一个编码任务 → 后台执行 → 自动续跑 → Console 查看结果"的流程]`

---

## 四、三个真实故事（15 分钟）

好，前面讲了很多"是什么"，接下来讲"为什么"。

我想分享三个我真实遇到的问题。每个问题都让我当时很头疼，但也正是这些问题，逼着我一步步搭出了现在这套东西。

---

### 故事 1：改错地方——AI 越过边界改了上游代码

#### 症状

有一天我让 AI 修一个 bug。AI 分析了半天，最后得出结论："这个 bug 改上游代码最简单。"然后它就直接改了 nanobot/ 目录里的文件。

问题是，nanobot/ 是上游框架代码，我的原则是不碰它。

#### 为什么会这样

我在 CLAUDE.md 里明明写了"禁止修改 nanobot/ 目录"。但 AI 会在"效率"和"规则"之间做权衡——如果它觉得改上游更快，它就会选择"更快"。

这就像你跟实习生说"别碰生产数据库"，但它发现直接改数据库能比改代码快 10 倍。如果没有 DBA 权限控制，它真的可能就改了。

**规则在提示词里，不在架构里——AI 有能力违反。**

#### 怎么修：三层防御

`[📊 slide：Before/After 截图——git diff 显示 nanobot/ 被误改]`

**Layer 1（Instructions）**：加强 CLAUDE.md 和 AGENTS.md 的措辞，把"禁止修改"写得更明确。同时通过 SpecAnchor 的模块级 Spec，让 AI 在开始工作前就能加载到"这个模块的边界是什么、该改哪里不该改哪里"的上下文。光靠一个全局的 CLAUDE.md 写"禁止改 nanobot/"是不够的——AI 需要的是**具体到模块粒度的契约**，而不只是一条笼统的禁令。

但光靠文档和 Spec 还是不够的。就像光靠写"请勿践踏草坪"并不能阻止所有人走捷径。

**Layer 2（Verification）**：写了 guardrail 测试，CI 里自动检测是否有文件改到了 nanobot/。

```
# tests/guardrails/test_nanobot_guardrail.py
# 验证 pre-commit hook 存在且包含 nanobot/ 保护逻辑
```

**Layer 3（Scope）**：在 .githooks/pre-commit 里加了硬门禁。默认情况下，任何修改了 nanobot/ 的 commit 都会被拦截：

```bash
# 如果有改动 nanobot/ 的文件，commit 直接被 BLOCKED
# 唯一的例外：ALLOW_NANOBOT_PATCH=1 git commit ...
```

而 Sidecar 架构本身就是一层结构性约束——所有扩展代码都在 ava/ 里，AI 默认工作在 ava/ 目录下。

这三层加在一起：**文档告诉 AI 不该做，测试发现 AI 做了，Hook 阻止 AI 的结果进入代码库**。

`[📊 slide：约束分层图——Layer 1/2/3 + Sidecar 结构约束]`

---

### 故事 2：改完不收尾——后台任务完成但 Agent 不继续

#### 症状

我通过 Telegram 让 Ava 帮我改一段代码。它把任务委托给 Claude Code 在后台执行，完成后 Telegram 通知了我："任务完成了。"

然后呢？然后就没有然后了。

Agent 通知了我，但它自己不会自动处理后续步骤——比如检查改动、跑测试、看看有没有遗留问题。

#### 为什么会这样

打个比方：**这就像一个员工做完了任务，发了一封邮件给你说"做完了"，然后就下班了。** 他不会自己检查有没有遗留问题，也不会主动安排下一步。

技术上说，是因为完成回调只做了"通知用户"，没有触发 Agent Loop 继续处理。

#### 怎么修：auto_continue 机制

`[📊 slide：Continuation Budget 工作流程图]`

我加了一个 **auto_continue** 机制：

1. 后台任务完成后，自动在原会话中注入任务结果
2. 给 Agent 一个提示："请基于以上结果继续处理后续步骤"
3. Agent 收到这个提示后，会自动继续——检查结果、做后续处理

但这里有一个很重要的安全措施——**Continuation Budget**：

- 每个会话最多自动续跑 **5 次**
- 防止 AI 陷入无限循环（"我发现一个问题 → 修复 → 又发现一个问题 → 修复 → ..."）
- 用户发新消息时 budget 自动重置

这就像给了 AI 一个**"加班额度"**。它可以自己加班 5 次，但超过 5 次就必须等你第二天来上班再给它批新的加班单。

---

### 故事 3：改完看不到——前端改了但没有效果

#### 症状

我让 AI 改了 Console 前端的 TypeScript 代码。AI 改完后截了个图告诉我"已完成"。

我打开页面一看——**什么都没变**。

#### 为什么会这样

因为 AI 不知道改完前端代码还需要 `npm run build`。它改了源码，但没有重新构建。

这在 Harness Engineering 里叫 **"confidence ≠ correctness"**——AI 觉得自己完成了，不等于它真的完成了。

打个产品同学更熟悉的比方：**这就像设计师改了 Figma 稿，但忘了导出切图给开发。** Figma 上看着是对的，但实际产品没有任何变化。

#### 怎么修：前端产物新鲜度检测

`[📊 slide：前端 auto-rebuild 逻辑示意图]`

我做了一个 **post-task hook**：每次编码任务完成后，自动检测前端产物是否过期。

原理很简单：

```
如果 src/ 下任何文件的修改时间 > dist/ 下文件的修改时间
    → 说明源码比产物新 → 需要重新 build
```

检测到过期后，自动触发 `npm run build`，构建完成后还会计算一个版本哈希写入 `dist/version.json`，方便追踪。

整个过程不依赖 AI 记住"改完前端要 build"。**你不需要 AI 记住每一个流程步骤——你需要一个系统级的兜底。**

---

### 约束的分层设计（三个故事的总结）

把三个故事画到一张图上，就是这样的分层结构：

```
┌──────────────────────────────────────────┐
│ Layer 4: CI / Guardrail Tests            │ ← 最终兜底
├──────────────────────────────────────────┤
│ Layer 3: Post-task Hooks                 │ ← 自动补救
│   (auto rebuild / auto continue)         │
├──────────────────────────────────────────┤
│ Layer 2: Tool Description + Spec         │ ← 影响 AI 决策
│   (委托优先 / SpecAnchor 模块契约)        │
├──────────────────────────────────────────┤
│ Layer 1: CLAUDE.md / AGENTS.md           │ ← 文档规范
└──────────────────────────────────────────┘
        + Sidecar 架构约束（结构性保障）
```

注意 Layer 2 里的 SpecAnchor 模块契约——它的作用是让 AI 在动手之前就知道"这个模块的边界在哪、改动应该落在哪个文件"。这属于**上下文治理**：不是限制 AI 的能力，而是确保 AI 拿到的上下文是准确的、最新的。AI 基于错误的上下文做决策，再聪明也会改错地方。

**关键洞察：每一层不需要 100% 可靠。四层组合 + 架构约束，覆盖面就够了。**

就像瑞士奶酪模型——每一片奶酪都有洞，但把多片叠在一起，光就透不过去了。

---

## 五、Sidecar 架构：一个关键的设计决策（5 分钟）

三个故事讲完了，我想单独聊一下 Sidecar 这个架构决策，因为它是整套治理体系的地基。

### Fork vs Sidecar

当你依赖一个开源项目但需要深度定制时，最直觉的做法是 **fork**。但 fork 有一个大问题：**每次上游更新，你都要手动合并**。时间一长，要么你放弃合并（和上游渐行渐远），要么合并冲突让你痛不欲生。

Sidecar 的做法不同：**上游代码一个字不改，所有定制通过运行时注入。**

具体来说，Ava 用 **Monkey Patch** 来实现注入。每个 patch 文件都有：

1. **Guard 检查**：先确认要 patch 的目标还在（上游可能改了）
2. **跳过逻辑**：如果目标不在了，不报错，只告警并跳过
3. **幂等保证**：同一个 patch 执行两次 = 第二次跳过
4. **自注册**：每个 patch 文件末尾调用 `register_patch()` 自动注册

`[📊 slide：Monkey Patch 真实 diff——以 loop_patch.py 为例]`

### 14 个 Patch 的执行顺序

所有 patch 按文件名字母序加载。这不是巧合——命名就是依赖管理：

```
a_schema_patch  →  b_config_patch（互斥：a 成功则 b 跳过）
       ↓
  bus_patch → channel_patch → console_patch → context_patch
       ↓
  loop_patch（核心枢纽：注入数据库、Token统计、后台任务、生命周期管理）
       ↓
  skills_patch → storage_patch → tools_patch → templates_patch → transcription_patch
```

### 这个决策的代价

Sidecar 不是没有成本。每次上游大改，我都需要：

1. 检查 patch 的拦截点是否还存在
2. 如果 API 变了，更新对应的 patch
3. 如果语义变了，可能需要重写

但比起 fork 的全量合并，这个成本要小得多、可控得多。

我在 `.specanchor/patch_map.md` 里维护了一个"热区图"，标注每个 patch 的风险等级和上游变更影响：

| Patch | 风险等级 | 上游变更影响 |
|-------|---------|-------------|
| loop_patch | HIGH | 核心枢纽，影响面最大 |
| context_patch | HIGH | 依赖 loop_patch 注入的组件 |
| a_schema_patch | CRITICAL | 如果上游 schema 大改需要同步 fork |
| channel_patch | MEDIUM | 平台相关，变化频率中等 |
| skills_patch | LOW | 接口稳定 |

---

## 六、我在这个过程中的一些思考（5 分钟）

做这个项目大概断断续续两个多月了。有几个思考想跟大家分享。

### 关于架构判断

选择 Sidecar 而不是 fork，这个决定我当时纠结了挺久的。fork 更简单直接，但我预感到后面会很痛苦。事后来看，这个判断省了我很多时间。14 个 patch 模块每个都有 guard 检查，上游更新时我只需要逐个检查拦截点。

我觉得**判断"不做什么"比"做什么"更难**。什么放 patch、什么放 fork、什么该提 PR 给上游——这个边界的把握，是我在这个项目里学到的很重要的一课。

### 关于治理意识

一开始我也觉得写个好的 prompt，AI 就会乖乖听话。后来发现不是这样。

**Prompt 是软护栏，它影响 AI "想做什么"。但 AI 有能力不做你想让它做的事。**

所以我开始把 prompt 失效的地方，一个一个变成了硬护栏：测试、Hook、运行时控制。

这个思维转变对我来说挺重要的。产品同学可能会有共鸣——**你不能期望用户 100% 按你设计的路径走，你需要在关键路口加上"不可能绕过的"引导。** AI 也是一样。

还有一点：除了约束 AI "不能做什么"，同样重要的是确保 AI "知道什么"。SpecAnchor 做的就是这件事——通过 Global / Module / Task 三级 Spec，让 AI 在每次工作时按需加载最新的项目上下文，而不是靠一个巨大的提示词把所有信息一股脑塞进去。**上下文的质量决定了 AI 决策的质量。**

### 关于闭环

我发现，**看到问题不难，难的是把问题变成代码**：

- "AI 改完了但没闭环" → continuation + auto rebuild
- "AI 不听话改了上游" → guardrail tests + Hook + Sidecar 架构
- "经验会丢失" → SpecAnchor 三级 Spec + Task 知识回流

这些东西每一个单独拎出来都不难。难的是**持续地把"不舒服"变成"自动化"**。

---

## 七、你今天就能带走的三个模式（3 分钟）

最后，我想把今天的内容收束成三个可复用的模式。不管你是不是在做 AI Agent 项目，这些模式在日常 AI Coding 中都用得上。

### 模式 1：Sidecar 扩展

> **依赖开源项目但需要深度定制？不要 fork，在旁边扩展。**

前提：上游代码有足够的可 patch 点。
成本：patch 维护 + 上游变更追踪。
收益：日常同步的冲突从结构上降到最小。

### 模式 2：软硬护栏组合

> **软护栏（提示词 / Spec）决定 AI "想做什么"。硬护栏（测试 / CI / Hook）决定 AI "能做什么"。两者缺一不可。**

你不需要每一层都 100% 可靠。但你需要至少两层——因为任何单层都有盲区。

这个模式其实大家已经在用了：代码 review（软）+ CI 自动检查（硬）。把同样的思路用到 AI 身上就行。

### 模式 3：Post-task 自动化

> **AI 改完代码后有固定后续步骤（build、lint、deploy）？不依赖 AI 记住，用 Hook 系统级兜底。**

这个特别适合前端同学。改完代码要 build、改完样式要跑 visual regression、改完 API 要更新 SDK——这些步骤 AI 不一定每次都记得，但 hook 永远不会忘。

---

## 八、接下来打算做的事情（2 分钟）

最后简单说一下后续计划：

1. **发布闭环**：目前 commit / PR / 部署还是手动的。打算把这一段也自动化，真正实现从"收到需求"到"上线"的全流程。

2. **SpecAnchor 的进一步完善**：目前三级 Spec 体系已经有了框架，但 Task Spec 的知识回流到 Module Spec 的机制还比较粗糙，打算做得更自动化。

3. **多 Agent 协同**：现在是单 Agent 模式。后续想试试让多个 Agent 协同工作——比如一个负责写代码，一个负责 review，一个负责测试。

这些都还在规划阶段，等有了更多实践再跟大家分享。

---

## 九、Q&A（5-10 分钟）

以上就是我今天的分享。核心想跟大家传达的是：**在 AI Coding 的过程中，给 AI 设计边界——把约束从提示词变成架构、测试和自动化——这件事情对团队和个人都有很高的价值。**

AI 越来越强，但"强"不等于"可靠"。**让 AI 的输出更可靠，可能比让 AI 更强更重要。**

欢迎大家提问和讨论。

---

### 预设 Q&A

**Q: Monkey Patch 会不会很脆弱，上游改了就挂？**

A: 会。所以每个 patch 里有 guard 检查——先看拦截点是否还在，不在就跳过并告警。这是维护成本的一部分，但比 fork 的全量合并冲突要可控得多。我还维护了一个 patch_map，标注每个 patch 的风险等级，方便上游更新时优先检查高风险区域。

**Q: 这套约束体系对小项目值得吗？**

A: 如果项目持续迭代 3 个月以上且频繁用 AI Coding，那值得。否则 CLAUDE.md 或 AGENTS.md 加几条规则就够了——这本身就是 Harness 的最小形态。不需要从零搭一个完整的体系，从一条规则开始、遇到问题加一层就好。

**Q: 能不能直接让 AI 自己设计约束？**

A: 可以。我这个项目里很多约束就是 AI 参与设计的。但 AI 设计的约束在边界情况容易遗漏，必须人来 review。这也是为什么叫"半闭环"——人类仍然是最终决策者。

**Q: Token 消耗和成本怎么样？**

A: Harness 文件（CLAUDE.md、Spec 等）确实会增加上下文消耗。但它们减少了返工——AI 一次做对比反复修改省得多。我还做了上下文压缩（HistoryCompressor）和历史摘要（HistorySummarizer），把旧对话压缩成精简版，节省 Token 的同时保留关键信息。

**Q: Nanobot 和 OpenClaw 的区别？**

A: 规模和定位不同。OpenClaw 是一个成熟的 Agent 产品，功能全面。Nanobot 更轻、更可读，自述 "Inspired by OpenClaw, 99% fewer lines"。我选它不是因为它"更好"，而是因为它的规模让我能真正理解每一行代码，也让 Harness 实验更可行。

**Q: SpecAnchor 和 Spec Kit / OpenSpec / Kiro 的区别？**

A: Spec Kit / OpenSpec / Kiro 更偏 spec authoring 和 workflow——回答"这次需求怎么写成 spec"。SpecAnchor 更偏 spec governance——回答"项目里的 spec 变多以后，怎么组织、加载、同步和治理"。它们可以互补。

---

## 附录：内容节奏参考

| 时间段 | 内容 | 目标 |
|--------|------|------|
| 0-5 min | OpenClaw hook + 龙虾悖论 | 抓注意力 |
| 5-13 min | Harness Engineering 三个来源 + Ava 映射 | 建立框架，证明落地 |
| 13-23 min | Ava 系统全貌 + Demo | 展示能力 |
| 23-38 min | 三个真实故事 | 核心高潮 |
| 38-43 min | Sidecar 架构 + 个人思考 | 深度 + 升华 |
| 43-46 min | 三个可复用模式 | 行动指南 |
| 46-48 min | 后续计划 | 展望 |
| 48-60 min | Q&A | 互动 |

## 附录：需要准备的演示材料 Checklist

### Slides

- [ ] OpenClaw 新闻截图（视觉 hook）
- [ ] 龙虾悖论一句话定义
- [ ] 三个来源（OpenAI / Anthropic / Learn HE）核心观点三栏对比
- [ ] Harness 五子系统图
- [ ] **Ava Harness 五子系统映射表**（全场最重要的一页）
- [ ] Ava 架构全景图（Nanobot 核心 + Ava Sidecar + Console + Tools）
- [ ] 代码行数统计对比（nanobot/ ~23K vs ava/ ~14K）
- [ ] "半闭环"示意图（已通 / 待通）
- [ ] 三个故事的 Before/After 截图（git diff 或代码对比）
- [ ] Continuation Budget 工作流程图
- [ ] 前端 auto-rebuild 逻辑示意图
- [ ] 约束分层图（Layer 1-4 + Sidecar）
- [ ] Monkey Patch 真实 diff（loop_patch.py）
- [ ] Patch 执行顺序图
- [ ] patch_map 热区表
- [ ] 三个可复用模式总结 slide
- [ ] .specanchor/ 文件截图（global-patch-spec.md / patch_map.md / architecture.md）

### Demo

- [ ] 1-2 分钟录屏：完整展示一次"Telegram 派任务 → 后台执行 → 自动续跑 → Console 查看结果"
- [ ] 找到 git log 中 AI 误改 nanobot/ 的真实 commit（故事 1 素材）

### 参考来源

- OpenAI: [Harness Engineering](https://openai.com/index/harness-engineering/)
- Anthropic: [Effective Harnesses for Long-running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Anthropic: [Harness Design for Long-running Apps](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- Learn Harness Engineering: [walkinglabs/learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering)
- LangChain: [Improving Deep Agents with Harness Engineering](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/)
- Martin Fowler: [Harness Engineering](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html)
