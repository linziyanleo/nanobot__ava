---
specanchor:
  level: task
  task_name: "console-ui 移动端适配可行性研究"
  author: "@git_user"
  created: "2026-03-24"
  status: "done"
  last_change: "收到用户反馈并转入移动端 MVP 方案设计，研究结论归档"
  related_modules:
    - ".specanchor/modules/console-ui.spec.md"
  related_global:
    - ".specanchor/global/architecture.spec.md"
  writing_protocol: "research"
  research_phase: "DONE"
  branch: "feat/0.0.1"
---

# Research: console-ui 移动端适配可行性研究

## 1. Research Question

- **核心问题**: 现有 `console-ui` 是否可以在不重写前后端架构的前提下，支持手机端可用的操作与监控。
- **调研范围**: 布局系统、导航结构、核心页面（Chat/Memory/Persona/Dashboard）在小屏下的可用性与改造成本。
- **范围边界（不调研什么）**: 不实施代码改造，不做真实移动设备自动化测试，不做原生 App 方案。
- **成功标准（什么算调研完成）**: 给出可行性结论、分阶段改造路径、优先级与风险清单。
- **决策背景**: 用户希望“可以用手机控制 console-ui”，优先考虑低成本快速可落地方案。

## 2. Explore

### 2.1 调研方法

- 阅读布局入口与全局容器：`Layout.tsx`、`Sidebar.tsx`、`App.tsx`。
- 审查核心业务页面结构：`ChatPage`、`MemoryPage`、`PersonaPage`、`DashboardPage`。
- 扫描 Tailwind 响应式断点使用与固定宽高样式（`w-64`、`w-48`、`h-[calc(100vh-3rem)]` 等）。

### 2.2 调研过程

#### 方向 1: 全局布局与导航是否具备移动兼容基础

- 调研内容: 检查主布局和侧边栏在窄屏下是否会自动退化。
- 关键发现:
  - `Layout` 固定为 `Sidebar + main` 二栏布局，未区分移动端容器策略。
  - `Sidebar` 使用 `w-60 / w-16` + `h-screen` + `sticky`，未提供抽屉模式或顶部折叠入口。
  - `main` 使用固定 `p-6`，对小屏有效内容空间侵占较大。
- 数据/证据: `console-ui/src/components/layout/Layout.tsx`、`console-ui/src/components/layout/Sidebar.tsx`

#### 方向 2: 核心页面在手机端的主要阻塞点

- 调研内容: 评估聊天、记忆、人格管理页面在小屏上的结构冲突。
- 关键发现:
  - ChatPage 里会话侧栏固定 `w-64`，页面外层还用了 `-m-6` 与视口高度布局，小屏容易挤压消息区。
  - Memory/Persona 页面普遍存在左栏 `w-48` + 右栏编辑器的双栏结构，缺少堆叠/切页模式。
  - 多个页面使用 `h-[calc(100vh-3rem)]` 固定高度，移动端浏览器地址栏伸缩会造成可视区域跳动。
- 数据/证据: `console-ui/src/pages/ChatPage/*`、`MemoryPage.tsx`、`PersonaPage.tsx`

#### 方向 3: 现有响应式基础与可复用能力

- 调研内容: 查找是否已有响应式断点实践，可用于快速扩展。
- 关键发现:
  - 部分页面已有 `md`/`lg` 栅格（例如 Dashboard、Skills、TokenStats），说明 Tailwind 响应式能力已在使用。
  - 但关键交互页（Chat/Memory/Persona）仍以桌面优先布局为主，未形成统一移动设计规范。
  - 现有后端 API 为 REST + WS，移动端适配主要是前端布局与交互改造，不需要后端协议重做。
- 数据/证据: `DashboardPage.tsx`、`SkillsPage.tsx`、`TokenStatsPage.tsx`、`api/client.ts`

### 2.3 实验/原型（如有）

- 本轮未制作可运行原型，仅完成静态代码结构与适配成本评估。

## 3. Findings

### 3.1 关键事实

1. 当前 `console-ui` 具备基础响应式能力，但缺少“统一移动布局框架”（导航/内容区/页面级断点策略）。
2. 造成手机不可用的核心不是后端接口，而是前端双栏固定宽度与桌面交互密度。
3. 聊天页是移动端控制价值最高页面，同时也是适配阻力最高页面（会话列表 + 消息流 + 输入区）。
4. 现有 REST + WS 能直接支持移动端，不存在协议层硬阻塞。
5. 采用“渐进式移动适配（先框架后页面）”可在 1-2 个迭代内明显提升可用性。

### 3.2 对比分析（如有多方案）

| 维度 | 方案 A：渐进式响应式改造（推荐） | 方案 B：全量移动优先重构 | 方案 C：独立移动端（PWA/App） |
| --- | --- | --- | --- |
| 改造成本 | 中 | 高 | 高 |
| 首版速度 | 快（1-2 迭代） | 慢 | 中慢 |
| 风险 | 低中 | 中高 | 中高 |
| 对现有代码侵入 | 中 | 高 | 低（前端分叉高） |
| 长期维护 | 可控 | 可控 | 双端维护成本高 |

### 3.3 Trade-offs

- **方案 A（推荐）**:
  - Pros: 兼容现有页面和 API；能快速覆盖核心手机场景（聊天、状态查看、任务触发）。
  - Cons: 早期会有“桌面代码 + 响应式补丁”并存，需持续治理。
- **方案 B（全量重构）**:
  - Pros: 架构最干净，长期一致性好。
  - Cons: 周期长、回归面广，不适合当前“尽快可用”目标。
- **方案 C（独立移动端）**:
  - Pros: 可针对手机交互做深度优化。
  - Cons: 需要单独路由/组件体系，迭代和测试成本明显上升。

### 3.4 未解决的问题

- 是否需要“手机端最小功能集”边界（只保留 Chat + Dashboard + Tasks）？
- Chat 页在手机端是采用“会话列表抽屉”还是“独立会话列表页”？
- Monaco Editor 类页面（Memory/Persona）在手机端是保留可编辑还是降级只读？

## 4. Challenge & Follow-up

> 用户已确认 Findings，并要求“进入移动端 MVP 方案设计，生成对应 Task Spec”。

### 4.1 Agent 追问

- 是否确认采用“渐进式响应式改造（方案 A）”作为 MVP 主路径？
- MVP 是否先聚焦高频路径（Chat / Dashboard / Tasks）？
- 复杂编辑页（Memory/Persona）是否先以“可查看优先”策略落地？

### 4.2 用户反馈

- 用户反馈：`进入移动端 MVP 方案设计，生成对应的task spec`

### 4.3 方向调整（基于追问）

- 方向确认：从“可行性研究”切换到“实现型设计（sdd-riper-one）”。
- 目标收敛：优先保证手机端可控性，不追求全页面首版等价能力。
- 产出要求：创建可执行 Task Spec，供后续按 checklist 落地。

## 5. Conclusion

### 5.1 Action Items

- [x] 用户确认 Findings，并进入 Challenge 阶段。
- [x] 明确进入移动端 MVP 方案设计。
- [x] 基于方案 A 创建实现型 Task Spec（`sdd-riper-one`）。

### 5.2 最终建议

- **推荐方案**: 采用方案 A（渐进式响应式改造），先做移动端 MVP，再逐页扩展。
- **推荐理由**: 在不改后端协议前提下，最快实现手机可控目标，风险与成本最平衡。
- **风险提示**: 早期会存在桌面与移动逻辑并存，需要阶段性重构清理。
- **下一步**: 执行 `sdd-riper-one` Task Spec：`.specanchor/tasks/console-ui/2026-03-24_console-ui-mobile-mvp.spec.md`
