# SDD Spec: nanobot 上游多模态能力 PR（以 ava Vision 为参考）

**状态**: `LOCKED`
**创建时间**: `2026-03-29`
**当前本地分支**: `refactor/sidecar`
**推荐开发分支**: `feat/upstream-vision-tool`（基于 `upstream/nightly`）
**目标上游分支**: `nightly`
**例外理由**: `upstream feature` + `PR prep`

---

## 0. Open Questions

- [ ] Maintainer 是否接受先合入“内置 `vision` 工具”这一最小切片，而不是一次性做完整多模态架构。
- [ ] 首个 PR 是否允许新增 `vision_model` 配置；若不接受，需退回为“直接复用当前主模型”。
- [ ] 首个 PR 的范围是否只做 `image`，将 `audio/video` 明确拆到后续 issue / PR。

## 1. Requirements (Context)

- **Goal**: 以当前 `ava/tools/vision.py` 为参考，给 `nanobot` 提交一个更容易被接受的上游多模态能力 PR。
- **In-Scope**:
  - 明确分支策略与上游提交路径
  - 识别 `ava vision` 中可上游化的最小能力切片
  - 形成分阶段 roadmap 与 PR 包装策略
  - 约束首个 PR 的文件范围、签名和测试面
- **Out-of-Scope**:
  - 将整个 Sidecar 机制搬进上游
  - 把 `token_stats`、`console`、`memory`、`image_gen`、`sticker` 一并带入 PR
  - 一次性覆盖 `image + audio + video`
  - 在本 spec 阶段直接修改 `nanobot/`

## 1.1 Context Sources

- Requirement Source:
  - 用户请求：基于 `ava/tools/vision.py` 规划上游多模态 PR，并输出 task spec
- Design Refs:
  - `CONTRIBUTING.md`
  - `README.md` 中 `Contribute & Roadmap`
  - `.specanchor/global-patch-spec.md`
- Code Refs:
  - `ava/tools/vision.py`
  - `ava/patches/tools_patch.py`
  - `nanobot/agent/context.py`
  - `nanobot/agent/loop.py`
  - `nanobot/providers/base.py`
  - `nanobot/providers/anthropic_provider.py`
  - `nanobot/providers/openai_codex_provider.py`
  - `nanobot/providers/openai_compat_provider.py`
- Upstream Signals:
  - README roadmap包含 `Multi-modal — See and hear (images, voice, video)`
  - `CONTRIBUTING.md` 明确新功能 / refactor 默认投 `nightly`
  - GitHub issue `#2563`：`nightly` 于 `2026-03-29` 刷新
  - GitHub PR `#2614`：当前已有 channel 侧 multimodal 相关活跃工作
  - GitHub PR `#2324` / `#2259`：上游已有“媒体输入 + image rehydration”相关先例

## 1.5 Codemap Used (Feature/Project Index)

- Codemap Mode: `targeted-research`
- Codemap File: `N/A（本轮未单独生成 codemap，基于定向代码检索）`
- Key Index:
  - Entry Points / Architecture Layers:
    - `AgentLoop._register_default_tools()` 负责默认工具注册
    - `ContextBuilder.build_messages()` / `_build_user_content()` 负责把 `media` 转为 `image_url` blocks
  - Core Logic / Cross-Module Flows:
    - channel / tool 传入 `media` -> `ContextBuilder` 生成多模态消息 -> provider 转换并请求模型
  - Dependencies / External Systems:
    - provider 层已经支持 OpenAI 风格 `content` blocks
    - Anthropic / Codex 已有 `image_url` 转换逻辑

## 1.6 Context Bundle Snapshot (Lite)

- Bundle Level: `Lite`
- Bundle File: `N/A`
- Key Facts:
  - 上游并非“没有多模态底座”，而是已经具备多模态消息表示和 provider 适配能力
  - 当前 `ava/tools/vision.py` 本质上是一个“显式视觉调用工具”，不是完整多模态架构本身
  - 当前本地分支 `refactor/sidecar` 不适合直接拿去向上游发 PR
- Open Questions:
  - 上游更偏好“内置工具”还是“自动感知式多模态交互”

## 2. Research Findings

### 2.1 代码事实

- `nanobot/agent/context.py` 已能把 `media` 中的图片转成 `image_url` blocks，并注入用户消息。
- `nanobot/providers/anthropic_provider.py`、`nanobot/providers/openai_codex_provider.py` 已对 `image_url` 做 provider 侧转换。
- `nanobot/providers/base.py` 还包含图片降级 / strip 逻辑，说明上游已经把多模态消息当作一等输入处理。
- `ava/tools/vision.py` 的价值主要在于：
  - 统一本地路径 / URL 到模型可消费的图片输入
  - 以显式工具方式暴露 OCR / 描述 / VQA 能力
  - 提供一个“最小、清晰、可测试”的上游候选切片

### 2.2 结论

- 你**应该新拉一个分支**，而且应当从 `upstream/nightly` 开，而不是继续在 `refactor/sidecar` 上开发上游 PR。
- 首个 PR 不应该宣称“把 `vision.py` 作为 nanobot 多模态底层架构”。
- 更准确的 framing 是：
  - `nanobot` 已经有多模态消息底座
  - 你要上游化的是一个“基于现有消息底座的内置视觉能力切片”
- 如果第一刀就做“完整多模态架构升级”，大概率会因为范围过大、和现有 channel / provider 工作重叠、混入 sidecar 设计而降低接受率。

### 2.3 分支策略

建议命令：

```bash
git fetch upstream
git switch -c feat/upstream-vision-tool upstream/nightly
```

不建议：

```bash
# 不要直接在当前 sidecar 分支上整理出一个巨型 PR
git push origin refactor/sidecar
```

原因：

- `CONTRIBUTING.md` 明确：新功能与行为改动默认投 `nightly`
- `nightly` 在 `2026-03-29` 刚 refresh，基线最新、冲突最少
- `refactor/sidecar` 包含大量上游不会接受的本地架构决策

### 2.4 PR 更易被接受的原则

- 只提交一个“focused patch”，不要把 sidecar 附带能力一起塞进去。
- 不要引入 `ava/`、Monkey Patch、token 统计、console 等本地上下文。
- 复用上游已有消息块结构，而不是重新定义一套多模态协议。
- 首个 PR 只做 `image`，把 `audio/video` 明确写成 follow-up。
- 首个 PR 优先新增测试，而不是新增抽象层。
- PR 描述里强调：
  - 上游已有多模态 message/provider 基础
  - 本 PR 只补“显式视觉工具”这一缺口
  - diff 小、行为清晰、易回滚、易 cherry-pick 到 `main`

## 2.1 Next Actions

- 先在上游开一个 issue / discussion，确认 maintainer 接受“内置 `vision` 工具优先”的切法。
- 从 `upstream/nightly` 建立干净分支，不复用当前 sidecar 分支历史。
- 按“PR1 最小切片 -> PR2 配置增强 -> PR3 其他模态”分阶段推进。

## 3. Innovate (Options & Decision)

### Option A: 先上游一个最小 `VisionTool`（推荐）

- Pros:
  - 与现有 `ava/tools/vision.py` 对应关系最清晰
  - 变更集中，容易解释与测试
  - 不需要推翻上游现有多模态消息结构
- Cons:
  - 只解决“显式视觉能力”，不是完整自动多模态体验

### Option B: 直接做完整多模态核心架构

- Pros:
  - 一步到位，理论上长期价值更大
- Cons:
  - 范围过大
  - 很容易与现有 provider / channel 演进方向冲突
  - review 成本高，PR 接受概率低

### Option C: 先做某个 channel 的多模态增强

- Pros:
  - 用户价值直观
  - 上游已有类似先例
- Cons:
  - 无法把 `ava/tools/vision.py` 的价值直接上游化
  - 会把“通用能力”问题降级成“单 channel 特性”

### Decision

- Selected: `Option A`
- Why:
  - 最符合“最简有效方案”
  - 最容易在上游 review 中建立共识
  - 可以把 sidecar 里的 `vision.py` 抽象为一个通用、最小、可测试的 upstream slice

### Skip

- Skipped: `false`
- Reason: 本任务是中等复杂度的上游方案设计，必须比较至少 2 条路线后再定方案

## 4. Plan (Contract)

### 4.1 分阶段路线图

#### PR1: 内置 `VisionTool` 最小切片

- 目标：让 nanobot 具备一个默认可用的视觉工具，基于现有 provider 多模态支持做图片分析
- 范围：
  - 新增工具类
  - 在默认工具注册中挂载
  - 补最小文档与测试
- 明确不做：
  - 新 console / token stats
  - 新 sidecar 架构
  - 音频 / 视频
  - 大规模 agent loop 重构

#### PR2: 视觉模型配置增强（可选）

- 目标：若 maintainer 接受，再增加 `vision_model` 或更通用的 model role 配置
- 前提：PR1 已被认可，且维护者确认希望解耦主对话模型与视觉模型

#### PR3: 其他模态与自动策略（后续）

- 目标：在上游 issue 讨论后，考虑音频 / 视频或自动调用策略
- 前提：先证明 image 路径可维护

### 4.2 File Changes（PR1）

- `nanobot/agent/tools/vision.py`
  - 新增上游内置 `VisionTool`
  - 基于 `ava/tools/vision.py` 提炼，但去掉 sidecar 特有耦合
- `nanobot/agent/loop.py`
  - 在 `_register_default_tools()` 中注册 `vision`
- `README.md`
  - 增加视觉工具的简要说明 / 用法
- `tests/tools/test_vision_tool.py`
  - 新增 `VisionTool` 单测
- `tests/agent/test_loop_default_tools.py`
  - 校验默认工具中包含 `vision`

### 4.3 Signatures（PR1）

- `class VisionTool(Tool): ...`
- `def __init__(self, provider: LLMProvider, model: str | None = None) -> None`
- `@property def name(self) -> str`
- `@property def description(self) -> str`
- `@property def parameters(self) -> dict[str, Any]`
- `@staticmethod def _resolve_image_url(url: str) -> str`
- `async def execute(self, url: str, prompt: str | None = None, **kwargs: Any) -> str`
- `def AgentLoop._register_default_tools(self) -> None`

### 4.4 Implementation Checklist

- [ ] 1. 在上游 issue / discussion 中确认“PR1 仅做内置 `vision` 工具”的切法
- [ ] 2. 从 `upstream/nightly` 新建干净分支 `feat/upstream-vision-tool`
- [ ] 3. 新增 `nanobot/agent/tools/vision.py`，从 `ava/tools/vision.py` 提炼最小实现
- [ ] 4. 去除 sidecar 私有耦合项：`token_stats`、`ava` 命名、console 相关依赖
- [ ] 5. 在 `nanobot/agent/loop.py` 注册默认 `vision` 工具
- [ ] 6. 补测试：URL 输入、本地图片输入、非图片文件、文件不存在、provider 调用消息结构
- [ ] 7. 补一个最小 README 说明，避免引入大段文档
- [ ] 8. 编写 PR 描述：问题、为什么是最小切片、测试清单、后续范围边界

### 4.5 PR 包装要求

- 标题建议：
  - `feat(tools): add built-in vision tool for image analysis`
- PR 描述必须包含：
  - Why now: roadmap 已有 `Multi-modal`
  - Why small: 复用现有 message/provider 底座，仅补一个显式工具
  - What not included: audio / video / auto-routing / sidecar extras
  - Test plan: 单测 + 1 个最小手动场景

## 5. Execute Log

- [ ] 尚未进入 Execute
- [ ] 等待后续 `Plan Approved` 或用户要求进入实现阶段

## 6. Review Verdict

- Spec coverage: `PASS`
- Behavior check: `N/A（尚未实现）`
- Regression risk: `Low（当前仅为方案与边界定义）`
- Follow-ups:
  - 若 maintainer 明确拒绝新增 `vision` 工具，则回到 `Research`，改为 issue-first 或 channel-first 路线

## 7. Plan-Execution Diff

- Any deviation from plan: `None`
- 备注：
  - 当前用户真正需要优先回答的问题不是“要不要新建分支”，而是“首个 upstreamable slice 应该切多小”
  - 新建分支的答案是明确的：`要，而且要基于 upstream/nightly`
