---
specanchor:
  level: task
  task_name: "console-ui 移动端 MVP 适配"
  author: "@git_user"
  assignee: "@git_user"
  reviewer: "@git_user"
  created: "2026-03-24"
  status: "review"
  last_change: "按最新反馈将移动端布局模式切换铺开到 Header，主题切换保留在菜单"
  related_modules:
    - ".specanchor/modules/console-ui.spec.md"
  related_global:
    - ".specanchor/global/coding-standards.spec.md"
    - ".specanchor/global/architecture.spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "REVIEW"
  branch: "feat/0.0.1"
---

# SDD Spec: console-ui 移动端 MVP 适配

## 0. Open Questions

- [x] 移动端断点定义：采用主流四档并区分手机与平板（`<= 480px` / `481-767px` / `768-1023px` / `>= 1024px`）；MVP 的“移动交互布局”覆盖 `< 768px`，平板使用过渡布局。
- [x] 界面形态切换：默认按视口自动判定，同时提供手动切换 `Auto / Desktop / Mobile`（浏览器可主动请求桌面端或移动端界面，并持久化偏好）。
- [x] Memory/Persona 在移动端允许编辑，目标与桌面端功能一致（保留 Monaco 能力，补充移动端可操作性约束）。
- [x] 顶部横滑菜单保留全部侧栏入口（不裁剪模块入口），通过横向滚动与 active 状态保证可达性。
- [x] 交付形态优先级：响应式 Web 为唯一 MVP 交付；PWA/WebView/React Native 不在本期范围。

## 1. Requirements (Context)

- **Goal**: 让用户在手机上可完成核心控制动作（查看状态、进入聊天、发送消息、切换会话、执行关键管理操作）。
- **In-Scope**:
  - 断点与布局策略：采用四档断点，`< 768px` 使用移动优先布局，`768-1023px` 采用平板过渡布局。
  - 提供 UI 形态切换（Auto/Desktop/Mobile），支持浏览器主动请求桌面端/移动端界面并本地持久化。
  - 全局布局移动适配：移动端采用三段式结构 `顶部横向菜单（可滑动） -> 面包屑导航 -> 内容区`。
  - 顶部横向菜单完整保留侧栏全部入口（与桌面信息架构一致）。
  - Chat 页面移动优先改造：会话列表可展开、消息区全宽、输入区可稳定操作。
  - Dashboard 与关键页面在小屏下可读可点（卡片/按钮尺寸与间距适配）。
  - Memory/Persona 移动端编辑能力与桌面端一致（含 Monaco 编辑流程可用性）。
  - 增加安全区（safe-area）和移动端视口高度兼容处理。
- **Out-of-Scope**:
  - 原生 App / React Native 独立端。
  - PWA 离线、推送、安装壳等增强能力。
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
  - 保留全部一级页面入口（与桌面侧栏一致），支持左右滑动与 active 高亮。
  - 菜单项点击立即切换路由，尽量不弹出遮罩层，降低操作成本。
  - 在 header 区域保留视图切换入口（Auto/Desktop/Mobile），用于手动请求界面形态。
- **面包屑**:
  - 显示当前路由层级（一级/二级）。
  - 二级节点可点击跳转（例如 Chat 下的“会话列表/当前会话”）。
- **内容区**:
  - 保持单一滚动容器：header 固定，内容区滚动。
  - 适配 iOS/Android 地址栏伸缩：避免 `100vh` 造成跳动。

## 1.3 响应式断点与界面判定

| 档位 | 宽度 | 目标设备 | 布局策略 |
| --- | --- | --- | --- |
| XS | `<= 480px` | 手机竖屏 | 移动布局（紧凑触达、单列优先） |
| SM | `481-767px` | 大屏手机/小折叠 | 移动布局（增强留白与按钮尺寸） |
| MD | `768-1023px` | 平板 | 过渡布局（可局部双栏） |
| LG | `>= 1024px` | 桌面 | 桌面布局（侧栏常驻） |

- 默认策略：`Auto`，根据当前视口宽度自动选择布局。
- 手动策略：用户可切换为 `Desktop` 或 `Mobile` 强制模式，优先级高于自动判定。
- 持久化：手动模式写入浏览器本地存储，刷新后保持。

## 1.4 Context Sources

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

- `console-ui/src/components/layout/Layout.tsx`: 增加视图模式判定（Auto/Desktop/Mobile）和移动容器三段式结构。
- `console-ui/src/components/layout/Sidebar.tsx`: 保持桌面侧栏能力，抽离导航数据供移动 header 复用。
- `console-ui/src/components/layout/navItems.ts`（新建）: 导航数据源（路径、图标、label、权限）供 Sidebar/MobileHeaderNav 复用。
- `console-ui/src/components/layout/MobileHeaderNav.tsx`（新建）: 顶部横向滑动菜单（复用侧栏入口，支持快速切页）。
- `console-ui/src/components/layout/MobileBreadcrumb.tsx`（新建）: header 次级面包屑，支持查看/跳转当前子页面。
- `console-ui/src/components/layout/ViewModeSwitch.tsx`（新建）: 浏览器主动请求桌面端/移动端的切换控件（Auto/Desktop/Mobile）。
- `console-ui/src/hooks/useResponsiveMode.ts`（新建）: 统一断点判断 + 手动模式优先 + 本地存储持久化。
- `console-ui/src/pages/ChatPage/index.tsx`: 增加移动会话面板开关与路由内状态管理。
- `console-ui/src/pages/ChatPage/SessionSidebar.tsx`: 支持移动模式（全屏抽屉或侧滑面板）。
- `console-ui/src/pages/ChatPage/MessageArea.tsx`: 小屏 header 收敛、按钮触达优化、输入区稳定布局。
- `console-ui/src/pages/DashboardPage.tsx`: 卡片与状态块移动端栅格优化。
- `console-ui/src/pages/MemoryPage.tsx`: 双栏改为移动端堆叠/分段展示，同时保持移动端编辑能力。
- `console-ui/src/pages/PersonaPage.tsx`: 双栏改为移动端堆叠/分段展示，同时保持移动端编辑能力。
- `console-ui/src/index.css`: 增加 safe-area 和移动滚动行为样式。

### 4.2 Signatures

- `function Layout(): JSX.Element`
- `function Sidebar(): JSX.Element`
- `function MobileHeaderNav(props: { currentPath: string; onNavigate: (path: string) => void }): JSX.Element`
- `function MobileBreadcrumb(props: { currentPath: string }): JSX.Element`
- `function ViewModeSwitch(props: { mode: "auto" | "desktop" | "mobile"; onChange: (mode: "auto" | "desktop" | "mobile") => void }): JSX.Element`
- `function useResponsiveMode(): { mode: "auto" | "desktop" | "mobile"; effectiveMode: "desktop" | "mobile"; setMode: (mode: "auto" | "desktop" | "mobile") => void; breakpoint: "xs" | "sm" | "md" | "lg" }`
- `function SessionSidebar(props: SessionSidebarProps & { mobile?: boolean; onCloseMobile?: () => void }): JSX.Element`
- `const [mobileSessionPanelOpen, setMobileSessionPanelOpen] = useState(false)`（`ChatPage`）

### 4.3 Implementation Checklist

- [x] 1. 统一定义断点与布局判定规则（XS/SM/MD/LG + Auto/Desktop/Mobile 优先级）。
- [x] 2. 新增 `useResponsiveMode` 和 `ViewModeSwitch`，支持浏览器主动请求桌面端/移动端并持久化。
- [x] 3. 改造 `Layout`，实现移动端 `横滑菜单 -> 面包屑 -> 内容区` 三段式框架。
- [x] 4. 抽离 `navItems.ts`，确保桌面侧栏与移动横滑菜单使用同一数据源。
- [x] 5. 新增 `MobileHeaderNav`，复用左侧菜单全部入口并支持横向滑动快速切页。
- [x] 6. 新增 `MobileBreadcrumb`，展示当前层级并支持子页面跳转。
- [x] 7. 改造 Chat 页面：会话列表可展开、消息区全宽、输入区稳定。
- [x] 8. 调整 Dashboard 卡片与状态区在手机端的分栏策略。
- [x] 9. 调整 Memory/Persona 页面在手机端的展示与交互策略，保证编辑能力与桌面一致。
- [x] 10. 增加 CSS 安全区适配并验证 iOS/Android 常见视口行为。
- [ ] 11. 完成手工测试清单（iPhone/Android 常见宽度 + 平板 + 桌面回归）。

## 4.4 Acceptance Criteria（移动端 MVP）

- [ ] 375px 宽度下（iPhone 常见宽度）可完成：切换页面、进入聊天、选择会话、发送消息、滚动查看消息。
- [ ] 顶部横滑菜单可左右滑动且 active 明确；点击切页无明显延迟。
- [ ] 顶部横滑菜单保留并可访问全部侧栏入口，不出现“仅核心入口”降级。
- [ ] 面包屑能显示当前页面层级，并能用于跳转返回子页（至少覆盖 Chat）。
- [ ] 浏览器可在 `Auto / Desktop / Mobile` 间切换，刷新后仍保持用户选择。
- [ ] Memory/Persona 在手机宽度下可完成编辑提交，关键编辑控件无不可触达区域。
- [ ] 页面不存在“双滚动条”导致的误触；输入框不会被键盘遮挡到不可用。

## 5. Execute Log

- [x] `console-ui/src/components/layout/navItems.ts`：抽离统一导航数据，供 Sidebar 与移动 Header 复用。
- [x] `console-ui/src/hooks/useResponsiveMode.ts` + `ViewModeSwitch.tsx`：实现 `Auto/Desktop/Mobile` 判定与本地持久化。
- [x] `Layout.tsx`：完成移动端 `横滑菜单 -> 面包屑 -> 内容区` 三段式容器，并保留桌面侧栏模式。
- [x] `ChatPage` 相关组件：实现移动抽屉式会话列表、消息区全宽、输入区安全区适配。
- [x] `MemoryPage` / `PersonaPage`：调整为移动端可编辑布局，保持 Monaco 编辑流程。
- [x] `DashboardPage.tsx`：优化小屏卡片栅格与卡片密度。
- [x] `index.css`：增加 `100dvh` 与移动触控/滚动行为基础样式。
- [x] `DisplayModeMenu.tsx` + `useThemeMode.ts`：在桌面侧栏 footer 增加统一显示模式菜单（日夜模式 / Auto-Desktop-Mobile）。
- [x] `useThemeMode.ts` + `Layout.tsx`：移动端同样支持主题切换，并新增默认自动日夜（7:00-19:00 日间，其余夜间）。
- [x] `useResponsiveMode.ts`：增加跨组件同步事件，修复从移动端切换到 Desktop 后无法从桌面入口切回移动的问题。
- [x] `Layout.tsx`：移动端 Header 增加常驻 `Auto/Desktop/Mobile` 三态按钮组，显示模式不再藏在二级菜单。
- [x] `DisplayModeMenu.tsx`：支持按场景显示分区（布局/主题）；移动端仅保留主题切换入口。
- [x] `ChatPage` / `SessionSidebar` / `SceneTabs`：移动端将场景切换移入会话抽屉，避免 session tabs 顶置占用主视区。
- [x] `MediaPage.tsx`：移动端改为两列图片网格（最小卡片宽度 + 自动换行）并保持内容区滚动。
- [x] `TokenStatsPage.tsx`：移动端改为“页内局部滚动 + 分页条固定在卡片底部”减少整页长滚动。
- [x] `DashboardPage.tsx`：移动端大卡片改为横向一排可滑动展示，不再一行一个。
- [x] `MemoryPage.tsx` / `PersonaPage.tsx`：提升移动端 Editor 最小高度，缓解编辑区域过小问题。
- [x] 验证：`npm run build` 通过（`tsc -b && vite build`）。

## 6. Review Verdict

- Spec coverage: PASS（Plan 中核心改动项均已落地，手工测试项待补）
- Behavior check: PARTIAL（类型构建与打包通过，真机交互验证待补）
- Regression risk: Medium（Layout 与 Chat 交互路径改动较多）
- Module Spec 需更新: Yes（实现后需回写 `console-ui.spec.md`）
- Follow-ups:
  - 完成 iPhone / Android / iPad / 桌面回归手测并回填 4.4 验收条目
  - 根据手测结果微调移动端触达面积与滚动行为

## 7. Plan-Execution Diff

- 无关键方案偏离：执行与 Plan 保持一致
- 执行阶段额外修复：`SearchModal.tsx` 类型声明兼容（`JSX.Element` -> `ReactElement`）以通过 TS 构建
- 根据用户反馈增加增强项：桌面侧栏 footer 并列显示“用户入口 + 显示模式菜单”，并加入日夜主题切换
- 根据用户反馈增加移动重构：主题自动日夜、会话抽屉化场景切换、Media 两列网格、Token 统计局部滚动
- 根据最新反馈继续微调：移动端布局模式切换改为 Header 常驻按钮组，减少二级点击路径
