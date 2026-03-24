---
specanchor:
  level: task
  task_name: "console-ui 移动端 P0 适配"
  author: "@git_user"
  created: "2026-03-24"
  status: "in_progress"
  related_modules:
    - ".specanchor/modules/console-ui.spec.md"
  branch: "feat/0.0.1"
---

# Task Spec: console-ui 移动端 P0 适配

## 1. 现状分析

### 已有能力
- DashboardPage 使用了 `md:grid-cols-2 xl:grid-cols-4`，有基础响应式
- SceneTabs 使用 `overflow-x-auto`，天然支持横滑
- MessageBubble 使用 `max-w-[80%]`，不会撑满全屏
- index.css 有 `word-break: break-words`，长文本不溢出

### 核心问题
| 组件 | 问题 | 严重度 |
|------|------|--------|
| Layout.tsx | 纯桌面 `flex` + 固定 Sidebar，小屏无法使用 | P0 |
| Sidebar.tsx | 固定 `w-60`/`w-16`，无移动端隐藏机制 | P0 |
| ChatPage/index.tsx | `-m-6 h-[calc(100vh)]` 硬编码；SessionSidebar `w-64` 固定 | P0 |
| SessionSidebar.tsx | `w-64 shrink-0` 在小屏占满甚至溢出 | P0 |
| ChatInput.tsx | 无 safe-area padding，iPhone 底部被遮挡 | P0 |
| useResponsiveMode.ts | 不存在，spec 中声称已实现 | P0 |
| navItems.ts | 不存在，导航数据硬编码在 Sidebar.tsx | P0 |
| MemoryPage.tsx | `w-48` 固定左侧菜单，小屏编辑区被挤压 | P1 |
| PersonaPage.tsx | `w-48` 固定左侧菜单，同上 | P1 |
| MessageArea.tsx | header 信息过长，小屏可能溢出 | P1 |

## 2. 改动清单

### P0 - 没有这些移动端基本不可用

1. **创建 `useResponsiveMode` hook**
   - 文件：`src/hooks/useResponsiveMode.ts`（新建）
   - 断点：`<768px` = mobile, `>=768px` = desktop
   - 支持 Auto/Desktop/Mobile 手动切换 + localStorage 持久化
   - 导出 `{ effectiveMode, mode, setMode, isMobile }`

2. **抽离 `navItems.ts`**
   - 文件：`src/components/layout/navItems.ts`（新建）
   - 从 Sidebar.tsx 抽出导航数据，供桌面侧栏和移动端顶部导航共用

3. **改造 Layout.tsx**
   - 移动端：隐藏 Sidebar，显示顶部横滑导航 + 底部无阻碍
   - 桌面端：保持现有侧栏布局不变
   - 新增 MobileHeaderNav 内联组件（横向滚动 nav items）

4. **ChatPage SessionSidebar 移动端抽屉化**
   - ChatPage 接入 `useResponsiveMode`
   - 移动端：SessionSidebar 默认隐藏，通过按钮打开为全屏/侧滑抽屉
   - 消息区全宽显示

5. **消息气泡和输入框适配**
   - MessageBubble: `max-w-[80%]` → 移动端 `max-w-[90%]`
   - ChatInput: 添加 `pb-[env(safe-area-inset-bottom)]`
   - ChatPage 容器：`h-[calc(100vh)]` → `h-dvh`

6. **移动端 CSS 基础**
   - `index.css` 添加 `100dvh` 支持、safe-area padding、touch-action 优化

### P1 - 体验改善

7. MemoryPage/PersonaPage 左侧菜单移动端改为顶部 tab 或下拉选择
8. MessageArea header 小屏信息折叠
9. ViewModeSwitch 组件（Auto/Desktop/Mobile 切换器）

### P2 - 锦上添花

10. MobileBreadcrumb 面包屑导航
11. 移动端手势支持（滑动切换会话等）

## 3. 实现方案

### 3.1 useResponsiveMode

```typescript
// Auto 模式下根据 window.innerWidth 判断
// 手动模式写入 localStorage('nanobot-view-mode')
// 通过 matchMedia 监听断点变化
export function useResponsiveMode() {
  // mode: 'auto' | 'desktop' | 'mobile'
  // effectiveMode: 'desktop' | 'mobile' (最终计算结果)
  // isMobile: boolean (= effectiveMode === 'mobile')
}
```

### 3.2 Layout 移动端结构

```
移动端:
┌─────────────────────────────────┐
│ [MobileHeaderNav] sticky top    │
│  Dashboard Chat Tasks Config .. │
├─────────────────────────────────┤
│ 内容区（<Outlet />）            │
│ 单一滚动容器                    │
└─────────────────────────────────┘

桌面端: 不变
┌────────┬────────────────────────┐
│Sidebar │ <Outlet />             │
│        │                        │
└────────┴────────────────────────┘
```

### 3.3 ChatPage 移动端结构

```
┌─────────────────────────────────┐
│ SceneTabs (横滑)                │
├─────────────────────────────────┤
│ Session header + [≡] 打开列表   │
├─────────────────────────────────┤
│ MessageArea (全宽)              │
├─────────────────────────────────┤
│ ChatInput + safe-area           │
└─────────────────────────────────┘

点击 [≡] → 侧滑 SessionSidebar 覆盖层
```

## 4. 验收标准

- [ ] 375px 宽度下可完成：切换页面、进入聊天、选择会话、发送消息
- [ ] 移动端顶部导航可横滑，active 高亮明确
- [ ] ChatPage 会话列表为可关闭的抽屉/覆盖层，不挤占消息区
- [ ] 输入框不被 iPhone 底部横条遮挡
- [ ] 消息气泡不溢出屏幕
- [ ] 桌面端 (>=768px) 功能和样式无回归
