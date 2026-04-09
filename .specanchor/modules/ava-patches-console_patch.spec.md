---
specanchor:
  level: module
  module_name: "Console 启动 Patch"
  module_path: "ava/patches/console_patch.py"
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
    - "ava/console/mock_bundle_runtime.py"
    - "ava/launcher.py"
    - "ava/console/__init__.py"
    - "ava/console/middleware.py"
    - "ava/console/models.py"
    - "ava/console/ui_build.py"
---

# Console 启动 Patch (console_patch)

## 1. 模块职责
- 将 Web Console 作为独立 uvicorn 服务注入 gateway 启动流程，与 nanobot Gateway 在同一事件循环中并行运行。
- 优先使用带 live `AgentLoop` 引用的 full mode，拿不到 loop 时降级到 standalone mode。
- 保证 Console 启停失败不会拖垮 Gateway 主服务。

## 2. 业务规则
- **原始行为**：gateway 命令回调调用 asyncio.run(main_coro) 启动 Gateway 服务
- **修改后行为**：遍历 cli_mod.app.registered_commands 找到 gateway 命令并替换 callback
- 包装 callback 会临时拦截 `asyncio.run()`，把原始 `main_coro` 包进 `_with_console()` 协程
- `_with_console()` 负责创建 Console 后台任务、等待原始 Gateway 主协程，并在退出时回收 Console

## 3. 对外接口契约

### 3.1 导出 API
| 函数/组件 | 签名 | 说明 |
|---|---|---|
| `apply_console_patch()` | `apply_console_patch() -> str` | 公共函数 |
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
- nanobot.cli.commands.app — Typer 应用实例
- nanobot.cli.commands.app.registered_commands — 注册的命令列表
- ava.console.app.create_console_app — full mode 工厂（直接持有 AgentLoop）
- ava.console.app.create_console_app_standalone — standalone mode 工厂（HTTP proxy）

## 5. 已知约束 & 技术债
- [ ] Typer app 中找不到 `gateway` 命令时必须 skip，不能把 patch 失败伪装成启动成功。
- [ ] `create_console_app()` 或 full mode 初始化失败时只允许 warning，并退回 standalone / gateway-only 路径。

## 6. TODO
- [ ] 代码行为变化后同步更新接口表、关键文件表和 module-index @ZiyanLin
- [ ] 如上游新增同类能力，重新评估 keep / narrow / delete / upstream 的 patch 策略 @ZiyanLin

## 7. 代码结构
- **入口**: `ava/patches/console_patch.py`
- **核心链路**: `console_patch.py` → 上游拦截点 → sidecar 补丁逻辑 → 原始运行时输出
- **数据流**: 触发 patch 注册 → 校验目标存在 → 包装/替换目标方法 → 返回 launcher/调用方可见结果
- **关键文件**:
| 文件 | 职责 |
|---|---|
| `ava/patches/console_patch.py` | 模块主入口 |
| `ava/console/app.py` | 关联链路文件 |
- **外部依赖**: `ava/console/mock_bundle_runtime.py`、`ava/launcher.py`、`ava/console/__init__.py`、`ava/console/middleware.py`、`ava/console/models.py`、`ava/console/ui_build.py`

## 8. 迁移说明
- 本文件由 legacy spec `ava-patches-console_patch.spec.md` 重生成，是当前 canonical Module Spec。
- legacy 命名文件已删除；本文件是唯一 canonical Module Spec。
