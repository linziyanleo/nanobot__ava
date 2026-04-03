# Module Spec: console_browser_page — console-ui 浏览器预览链路

> 相关文件：`ava/console/app.py`、`ava/console/routes/page_agent_routes.py`、`console-ui/src/App.tsx`、`console-ui/src/components/layout/navItems.ts`、`console-ui/src/pages/BrowserPage/index.tsx`、`console-ui/src/pages/BrowserPage/ScreencastView.tsx`、`console-ui/src/pages/BrowserPage/ActivityPanel.tsx`、`console-ui/src/pages/BrowserPage/types.ts`
> 状态：✅ 已实现（2026-04-03，仅 full mode 可用）

---

## 1. 模块职责

把 page-agent 的运行时画面和活动事件接到 console-ui 的 `/browser` 页面，让已登录用户可以观看当前活跃 session 的浏览器预览，而不直接控制浏览器。

该模块只负责“展示链路”：

- console 后端暴露 session 查询和 WebSocket 转发
- console-ui 前端展示会话列表、实时画面、活动流和当前状态

真正的浏览器执行、screencast 采集和事件产生都在 `page_agent_runtime` 模块内完成。

---

## 2. 链路总览

```text
console_patch 启动 full-mode console
  -> create_console_app() include_router(page_agent_routes)
  -> GET /api/page-agent/sessions
  -> WS /api/page-agent/ws/{session_id}
  -> BrowserPage 轮询 session 并建立 WS
  -> ScreencastView 渲染 frame
  -> ActivityPanel 渲染 activity/status/page_url
```

### 2.1 后端链

| 环节 | 说明 |
|------|------|
| `create_console_app()` | 注册 `page_agent_routes.router` |
| `_get_page_agent_tool()` | 从 `ChatService._agent.tools` 中取 `page_agent` 实例 |
| `GET /api/page-agent/sessions` | 返回当前活跃 session 列表 |
| `WS /api/page-agent/ws/{session_id}` | 鉴权、订阅事件、启动 screencast、回发初始 `page_info`、转发队列事件 |

### 2.2 前端链

| 环节 | 说明 |
|------|------|
| `console-ui/src/App.tsx` | 注册受保护路由 `/browser` |
| `navItems.ts` | 把“浏览器”加入左侧导航 |
| `BrowserPage/index.tsx` | 轮询 session、管理 WS、维护页面状态 |
| `ScreencastView.tsx` | 把 base64 JPEG 写入 `<img>` |
| `ActivityPanel.tsx` | 展示事件流、状态灯、URL、stepCount |

---

## 3. 后端契约

### 3.1 工具发现与可用性

- 后端不会自行 new `PageAgentTool`
- 只从当前 `ChatService` 持有的 `AgentLoop.tools` 查找 `page_agent`
- 因此该页面只在 full mode console 中可用
- `create_console_app_standalone()` 没有注册 `page_agent_routes`，standalone console 不支持 `/browser` 预览

### 3.2 WebSocket 处理流程

1. `auth.get_ws_user()` 校验 token
2. `tool.subscribe(session_id, on_event)` 注册订阅
3. 尝试 `tool.start_screencast(session_id)`；失败只记 warning，不阻断 activity 转发
4. 调 `tool.get_page_info(session_id)` 并主动推送 `page_info`
5. sender 协程从 `asyncio.Queue(maxsize=100)` 读事件并发送给前端
6. receiver 协程只负责保持连接活跃
7. 断开时 `unsubscribe()`，并调用 `stop_screencast()`

### 3.3 实时性策略

- 队列满时直接丢弃新事件，优先保实时，不保全量历史
- `frame` 数据不做二次解码，直接文本转发 base64 JPEG
- `page_info` 只在连接建立时主动发送一次；后续 URL 变化依赖重新连接或上层事件扩展

---

## 4. 前端状态契约

### 4.1 Session 发现

- 无 session 时每 2 秒轮询一次 `/api/page-agent/sessions`
- 有 session 后放慢到每 5 秒
- 首次发现 session 且当前未选中时，默认选第一条

### 4.2 WebSocket 消息消费

| 事件类型 | 前端行为 |
|----------|----------|
| `frame` | 更新 `frame` state，交给 `ScreencastView` 渲染 |
| `activity` | 追加为 `ActivityEntry`，新事件在前，最多保留 100 条 |
| `status` | 更新状态灯 |
| `page_info` | 更新当前 `pageUrl` |

补充说明：

- `stepCount` 不是来自独立 `step` 事件，而是每次 `activity.type === "executed"` 时加一
- `types.ts` 中定义了 `StepEvent`，但当前 `BrowserPage` 尚未消费该类型

### 4.3 UI 结构

- 左侧主区域：`ScreencastView`
- 右侧边栏：`ActivityPanel`
- 顶部栏：标题、session 选择器、连接状态
- 状态区并未拆出独立 `StatusBar.tsx`，而是合并在 `ActivityPanel` 底部

---

## 5. 权限与限制

- 路由受 `ProtectedRoute` 保护，需要已登录用户，但不是 admin-only
- 当前页面只读观看，不提供暂停/停止/点击预览等控制能力
- 没有活跃 session 时页面展示空状态，而不是主动创建浏览器
- 如果后端没有注册 `page_agent` 工具：
  - `GET /sessions` 返回空数组
  - WS 会以 `1011` 关闭

---

## 6. 依赖关系

### Sidecar 内部依赖

- `ava.console.auth`
- `ava.console.app.get_services()`
- `page_agent_runtime` 模块暴露的订阅、会话和 screencast 接口

### 前端依赖

- `console-ui/src/api/client.ts`
- `localStorage.token`
- `react-router-dom`

---

## 7. 测试与验收要点

| 场景 | 验收内容 |
|------|----------|
| 已有活跃 page-agent session | `/browser` 页面能看到画面和活动流 |
| 首次连接 | 可收到 `page_info`，URL 展示正确 |
| 无 session | 页面显示未连接 / 等待状态 |
| 多 session | 顶部下拉切换后能重连新 session |
| standalone console | 无 `/browser` 预览能力，不应误判为 page-agent 故障 |
