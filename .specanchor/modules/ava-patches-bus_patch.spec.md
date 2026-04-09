---
specanchor:
  level: module
  module_name: "Bus Console 监听器"
  module_path: "ava/patches/bus_patch.py"
  version: "1.0.0"
  owner: "@ZiyanLin"
  author: "@ZiyanLin"
  reviewers: []
  created: "2026-03-26"
  updated: "2026-04-09"
  last_synced: "2026-04-09"
  last_change: "按 SpecAnchor 最新 Module Spec 模板重生，合并 legacy spec 与当前代码扫描结果"
  status: "active"
  depends_on:
    - "nanobot/bus/events.py"
    - "ava/launcher.py"
    - "ava/console/__init__.py"
    - "ava/console/middleware.py"
    - "ava/console/mock_bundle_runtime.py"
    - "ava/console/models.py"
---

# Bus Console 监听器 (bus_console_listener)

## 1. 模块职责
- 为 nanobot 的消息总线（MessageBus）添加两套监听机制：
- **Console 监听器**：按 session_key 管理 Console WebSocket 的 OutboundMessage 队列（覆盖式注册，用于双向会话）
- **Observe 监听器**：按 session_key 管理 observe WebSocket 的 dict 生命周期事件队列（追加式注册，支持多页面同时观察同一 session）
- **总线桥接**：包装 publish_outbound，自动把 console 消息路由到对应 session 队列

## 2. 业务规则
- 使用 self._console_listeners: dict[str, asyncio.Queue] 存储（lazy init）
- 覆盖式注册：同 session_key 重复注册替换旧队列
- dispatch_to_console_listener 使用 queue.put_nowait(...) 写入事件
- 队列满时打印 warning 并丢弃消息

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `apply_bus_patch()` | `apply_bus_patch() -> str` | 公共函数 |
| `Services` | `class` | 核心类 |
| `get_services()` | `get_services() -> Services` | 公共函数 |
| `get_services_for_user()` | `get_services_for_user(user: UserInfo | None = None) -> Services` | 公共函数 |
| `create_console_app()` | `create_console_app(nanobot_dir: Path, workspace: Path, agent_loop, config, token_stats_collector: TokenStatsCollector | None = None, db = None) -> FastAPI` | 公共函数 |
| `create_console_app_standalone()` | `create_console_app_standalone(nanobot_dir: Path, workspace: Path, gateway_port: int = 18790, console_port: int = 6688, secret_key: str = 'change-me-in-production', expire_minutes: int = 480, session_cookie_name: str = 'ava_console_session', session_cookie_secure: bool = False, session_cookie_samesite: str = 'lax', token_stats_dir: str = '') -> FastAPI` | Create a console app that runs independently from the gateway process. |

### 3.2 内部状态
| Store/Context | 字段 | 说明 |
|---|---|---|
| _services | module | 模块级共享状态或常量 |

### 3.3 API 端点（如有）
| 方法 | 路径 | 用途 |
|---|---|---|
| — | — | 该模块不直接暴露 HTTP / WS 端点 |

## 4. 模块内约定
- nanobot.bus.queue.MessageBus — 注入目标
- ava.console.app — Console 子应用的 WebSocket 端点（消费者）
- ava.launcher.register_patch — 自注册机制
- console_patch 启动 Console uvicorn server（提供 WebSocket 端点）

## 5. 已知约束 & 技术债
- [ ] 需随着代码继续演进同步更新本 Spec，避免再次出现 legacy 术语漂移。

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/bus_patch.py`
- **核心链路**: `bus_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/bus_patch.py` | 模块主入口 |
| `ava/console/app.py` | 关联链路文件 |
- **外部依赖**: `nanobot/bus/events.py`、`ava/launcher.py`、`ava/console/__init__.py`、`ava/console/middleware.py`、`ava/console/mock_bundle_runtime.py`、`ava/console/models.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-bus_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
