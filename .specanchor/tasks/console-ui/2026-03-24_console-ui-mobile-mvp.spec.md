---
specanchor:
  level: task
  task_name: "console-ui 移动端 MVP 适配"
  author: "@git_user"
  assignee: "@git_user"
  reviewer: "@git_user"
  created: "2026-03-24"
  status: "draft"
  last_change: "根据用户反馈更新为“顶部横滑菜单 + 面包屑 + 内容区”移动端结构"
  related_modules:
    - ".specanchor/modules/console-ui.spec.md"
  related_global:
    - ".specanchor/global/coding-standards.spec.md"
    - ".specanchor/global/architecture.spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "feat/0.0.1"
---

# SDD Spec: console-ui 移动端 MVP 适配

## 0. Open Questions

- [ ] 移动端断点定义：以 `< 768px` 为 MVP 范围是否可接受？
- [ ] Memory/Persona 在移动端是否允许编辑（Monaco）还是先只读？
- [ ] 顶部横滑菜单是否保留全部侧栏入口，还是先保留核心入口（Dashboard/Chat/Tasks/Config）？
- [ ] 交付形态优先级：响应式 Web（浏览器直接访问） vs PWA/WebView 封装 vs React Native 独立端？

## 1. Requirements (Context)

- **Goal**: 让用户在手机上可完成核心控制动作（查看状态、进入聊天、发送消息、切换会话、执行关键管理操作）。
- **In-Scope**:
  - 全局布局移动适配：移动端采用三段式结构 `顶部横向菜单（可滑动） -> 面包屑导航 -> 内容区`。
  - Chat 页面移动优先改造：会话列表可展开、消息区全宽、输入区可稳定操作。
  - Dashboard 与关键页面在小屏下可读可点（卡片/按钮尺寸与间距适配）。
  - 增加安全区（safe-area）和移动端视口高度兼容处理。
- **Out-of-Scope**:
  - 原生 App/PWA 离线能力。
  - 所有后台页面完整功能等价（MVP 先保证高频路径）。
  - 后端 API 协议改造（本任务仅前端体验层）。

## 1.2 UX 目标结构（移动端）

```text
┌──────────────────────────────────────────────┐
│ [MobileHeaderNav] 横向滑动菜单（sticky top） │
│  Dashboard  Chat  Tasks  Config  ...         │
├──────────────────────────────────────────────┤
│ [MobileBreadcrumb] 当前位置 / 子页跳转       │
│  控制台 / 聊天 / 会话列表                    │
├──────────────────────────────────────────────┤
│ 内容区（页面自身滚动，避免双滚动）           │
│  - Chat：会话列表抽屉/面板 + 消息流 + 输入   │
│  - Dashboard：卡片栅格自适应                │
└──────────────────────────────────────────────┘
```

- **横滑菜单**:
  - 优先展示一级页面入口（与桌面侧栏一致），支持左右滑动与 active 高亮。
  - 菜单项点击立即切换路由，尽量不弹出遮罩层，降低操作成本。
- **面包屑**:
  - 显示当前路由层级（一级/二级）。
  - 二级节点可点击跳转（例如 Chat 下的“会话列表/当前会话”）。
- **内容区**:
  - 保持单一滚动容器：header 固定，内容区滚动。
  - 适配 iOS/Android 地址栏伸缩：避免 `100vh` 造成跳动。

## 1.1 Context Sources

- Requirement Source: 用户“手机控制 console-ui”需求
- Design Refs: `.specanchor/tasks/_cross-module/2026-03-24_console-ui-mobile-adaptation-research.spec.md`
- Chat/Business Refs: N/A
- Extra Context: `.specanchor/modules/console-ui.spec.md`

## 2. Research Findings

- 当前主布局是桌面优先（固定侧边栏 + 主内容），手机端缺少统一导航容器。
- Chat/Memory/Persona 等核心页面存在固定宽度双栏结构，不适配窄屏。
- 后端接口（REST + WS）无需调整，移动端适配主要是前端布局与交互改造。

## 2.1 Next Actions

- 输出可执行文件改动计划（MVP 仅覆盖核心路径）。
- 拆分原子化实施清单，便于分 PR/分阶段落地。

## 3. Innovate (Optional: Options & Decision)

### Option A

- 方案：响应式重构 + 移动端顶部横滑菜单 + 面包屑 + Chat 优先适配（推荐）。
- Pros：改造成本可控、对现有代码侵入适中、可快速上线 MVP。
- Cons：会存在一段时间桌面与移动分支逻辑并存。

### Option B

- 方案：全量移动优先重写布局体系。
- Pros：架构统一，长期更干净。
- Cons：周期长、回归风险高，不符合 MVP 速度目标。

### Option C

- 方案：独立移动端（React Native）并行开发。
- Pros：可获得原生体验与更强设备能力接入。
- Cons：需要双端维护，功能同步和测试成本显著上升。

### Decision

- Selected: Option A
- Why: 能最快实现“手机可操作”目标，同时保持现有路由和 API 不变。

### Skip (for small/simple tasks)

- Skipped: false
- Reason: 存在多个可行方案且权衡差异明显，需要先定策略再实施。

## 4. Plan (Contract)

### 4.1 File Changes

- `console-ui/src/components/layout/Layout.tsx`: 增加移动容器三段式结构与内容区自适应间距。
- `console-ui/src/components/layout/Sidebar.tsx`: 保持桌面侧栏能力，抽离导航数据供移动 header 复用。
- `console-ui/src/components/layout/navItems.ts`（新建）: 导航数据源（路径、图标、label、权限）供 Sidebar/MobileHeaderNav 复用。
- `console-ui/src/components/layout/MobileHeaderNav.tsx`（新建）: 顶部横向滑动菜单（复用侧栏入口，支持快速切页）。
- `console-ui/src/components/layout/MobileBreadcrumb.tsx`（新建）: header 次级面包屑，支持查看/跳转当前子页面。
- `console-ui/src/pages/ChatPage/index.tsx`: 增加移动会话面板开关与路由内状态管理。
- `console-ui/src/pages/ChatPage/SessionSidebar.tsx`: 支持移动模式（全屏抽屉或侧滑面板）。
- `console-ui/src/pages/ChatPage/MessageArea.tsx`: 小屏 header 收敛、按钮触达优化、输入区稳定布局。
- `console-ui/src/pages/DashboardPage.tsx`: 卡片与状态块移动端栅格优化。
- `console-ui/src/pages/MemoryPage.tsx`: 双栏改为移动端堆叠/分段展示。
- `console-ui/src/pages/PersonaPage.tsx`: 双栏改为移动端堆叠/分段展示。
- `console-ui/src/index.css`: 增加 safe-area 和移动滚动行为样式。

### 4.2 Signatures

- `function Layout(): JSX.Element`
- `function Sidebar(): JSX.Element`
- `function MobileHeaderNav(props: { currentPath: string; onNavigate: (path: string) => void }): JSX.Element`
- `function MobileBreadcrumb(props: { currentPath: string }): JSX.Element`
- `function SessionSidebar(props: SessionSidebarProps & { mobile?: boolean; onCloseMobile?: () => void }): JSX.Element`
- `const [mobileSessionPanelOpen, setMobileSessionPanelOpen] = useState(false)`（`ChatPage`）

### 4.3 Implementation Checklist

- [ ] 1. 统一定义移动断点与交互规格（按钮最小触达尺寸、间距、字号）。
- [ ] 2. 改造 `Layout`，实现移动端 `横滑菜单 -> 面包屑 -> 内容区` 三段式框架。
- [ ] 3. 抽离 `navItems.ts`，确保桌面侧栏与移动横滑菜单使用同一数据源。
- [ ] 4. 新增 `MobileHeaderNav`，复用左侧菜单项并支持横向滑动快速切页。
- [ ] 5. 新增 `MobileBreadcrumb`，展示当前层级并支持子页面跳转。
- [ ] 6. 改造 Chat 页面：会话列表可展开、消息区全宽、输入区稳定。
- [ ] 7. 调整 Dashboard 卡片与状态区在手机端的分栏策略。
- [ ] 8. 调整 Memory/Persona 页面在手机端的展示策略（MVP 先可查看，再逐步增强编辑体验）。
- [ ] 9. 增加 CSS 安全区适配并验证 iOS/Android 常见视口行为。
- [ ] 10. 完成手工测试清单（iPhone/Android 常见宽度 + 桌面回归）。

## 4.4 Acceptance Criteria（移动端 MVP）

- [ ] 375px 宽度下（iPhone 常见宽度）可完成：切换页面、进入聊天、选择会话、发送消息、滚动查看消息。
- [ ] 顶部横滑菜单可左右滑动且 active 明确；点击切页无明显延迟。
- [ ] 面包屑能显示当前页面层级，并能用于跳转返回子页（至少覆盖 Chat）。
- [ ] 页面不存在“双滚动条”导致的误触；输入框不会被键盘遮挡到不可用。

## 5. Execute Log

- [ ] 待执行（本次仅输出 MVP 方案 Task Spec）

## 6. Review Verdict

- Spec coverage: TBD
- Behavior check: TBD
- Regression risk: TBD
- Module Spec 需更新: Yes（实现后需回写 `console-ui.spec.md`）
- Follow-ups: TBD

## 7. Plan-Execution Diff

- 待执行后补充
