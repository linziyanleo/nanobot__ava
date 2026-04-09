---
specanchor:
  level: module
  module_name: "浏览器预览页"
  module_path: "console-ui/src/pages/BrowserPage"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-04-03"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "按 SpecAnchor 最新 Module Spec 模板重生，合并 legacy spec 与当前代码扫描结果"
  status: "active"
  depends_on:
    - "ava/console/__init__.py"
    - "ava/console/models.py"
    - "nanobot/agent/tools/base.py"
    - "ava/console/routes/page_agent_routes.py"
    - "ava/tools/page_agent.py"
---

# 浏览器预览页 (console_browser_page)

## 1. 模块职责
- 该模块只负责“展示链路”：
- console 后端暴露 session 查询和 WebSocket 转发
- console-ui 前端展示会话列表、实时画面、活动流和当前状态

## 2. 业务规则
- 页面状态以局部 hooks 为主，服务端不可用时不阻塞整个 Console
- WebSocket / 轮询链路允许丢帧与断连恢复，但不能造成页面崩溃
- 页面只消费后端暴露的稳定接口，不直接假设 Python 内部对象形状

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `ActivityPanel` | `React component` | ActivityPanel.tsx 默认导出组件 |
| `ScreencastView` | `React component` | ScreencastView.tsx 默认导出组件 |
| `BrowserPage` | `React component` | index.tsx 默认导出组件 |
| `list_sessions()` | `list_sessions(user: UserInfo = Depends(auth.require_role('admin', 'editor', 'viewer')))` | 返回当前活跃的 page-agent session 列表。 |
| `restart_runner()` | `restart_runner(user: UserInfo = Depends(auth.require_role('admin', 'editor', 'viewer')))` | 停止 page-agent runner 进程，下次调用时自动重启。 |
| `page_agent_ws()` | `page_agent_ws(websocket: WebSocket, session_id: str)` | WebSocket 端点：实时转发 screencast 帧和 activity 事件。 |
| `PageAgentTool` | `class` | Control web pages using natural language via page-agent + Playwright. |
| `PageAgentTool.execute()` | `execute(action: str, response_format: str = 'text', **kwargs) -> str` | 公共方法 |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| sessions | useState | index.tsx 页面状态 |
| activeSession | useState | index.tsx 页面状态 |
| connected | useState | index.tsx 页面状态 |
| frame | useState | index.tsx 页面状态 |
| activities | useState | index.tsx 页面状态 |
| status | useState | index.tsx 页面状态 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | /sessions | 路由入口 |
| POST | /restart-runner | 路由入口 |
| WEBSOCKET | /ws/{session_id} | 路由入口 |

## 4. 模块内约定
- ava.console.auth
- ava.console.app.get_services()
- page_agent_runtime 模块暴露的订阅、会话和 screencast 接口
- console-ui/src/api/client.ts

## 5. 已知约束 & 技术债
- [ ] 无 session 时页面必须停留在“未连接 / 等待状态”，不能误报 runner 故障或触发前端异常。

## 6. TODO
- [ ] 页面接口或事件协议变化后同步更新前后端双方 Spec @ZiyanLin
- [ ] 补齐针对断连重连、无 session 和 runner 重启的回归检查 @ZiyanLin

## 7. 代码结构
- **入口**: `console-ui/src/pages/BrowserPage`
- **核心链路**: BrowserPage/index.tsx → api/client → page_agent_routes.py → PageAgentTool
- **数据流**: 轮询/WS 建连 → 收集 session/frame/activity → 更新页面状态 → 渲染预览与活动面板
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `console-ui/src/pages/BrowserPage/ActivityPanel.tsx` | 模块目录下的关键实现文件 |
| `console-ui/src/pages/BrowserPage/ScreencastView.tsx` | 模块目录下的关键实现文件 |
| `console-ui/src/pages/BrowserPage/index.tsx` | 模块目录下的关键实现文件 |
| `console-ui/src/pages/BrowserPage/types.ts` | 模块目录下的关键实现文件 |
| `ava/console/routes/page_agent_routes.py` | 关联链路文件 |
| `ava/tools/page_agent.py` | 关联链路文件 |
- **外部依赖**: `ava/console/__init__.py`、`ava/console/models.py`、`nanobot/agent/tools/base.py`、`ava/console/routes/page_agent_routes.py`、`ava/tools/page_agent.py`

## 8. 迁移说明
- 本文件由 legacy spec `console-ui-src-pages-BrowserPage.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
