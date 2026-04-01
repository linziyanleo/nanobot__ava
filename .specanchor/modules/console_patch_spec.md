# Module Spec: console_patch — Web Console 独立服务启动

> 文件：`ava/patches/console_patch.py`
> 状态：✅ 已实现（Phase 1 创建，Phase 2 重写）

---

## 1. 模块职责

将 Web Console 作为独立的 uvicorn 服务启动，与 nanobot Gateway 在同一事件循环中并行运行。Console 监听独立端口，提供 Web 管理界面；优先使用带 `AgentLoop` 引用的 full mode，拿不到 live loop 时降级到 standalone mode。

---

## 2. 拦截点列表

| 拦截点 | 类型 | 说明 |
|--------|------|------|
| Typer `gateway` 命令的 callback | 回调替换 | 包装 gateway 回调，在事件循环中注入 Console uvicorn server |
| `asyncio.run` | 临时替换 | 拦截 `asyncio.run()` 调用，在其中注入 Console 后台任务 |

### 拦截详情

- **原始行为**：`gateway` 命令回调调用 `asyncio.run(main_coro)` 启动 Gateway 服务
- **修改后行为**：
  1. 遍历 `cli_mod.app.registered_commands` 找到 `gateway` 命令
  2. 替换其 callback 为包装版本
  3. 包装版本临时替换 `asyncio.run`
  4. 拦截到的 `asyncio.run(coro)` 被替换为 `asyncio.run(_with_console())`
  5. `_with_console()` 创建 Console uvicorn server 作为后台任务，然后 `await` 原始 coro
  6. Gateway 退出时自动 cancel Console 任务

---

## 3. 配置

| 配置项 | 来源 | 默认值 | 说明 |
|--------|------|--------|------|
| `config.gateway.console.port` | 配置文件 | `6688` | Console 首选监听端口 |
| `CAFE_CONSOLE_PORT` | 环境变量 | `6688` | 未配置 `console.port` 时的端口兜底 |
| `CAFE_CONSOLE_HOST` | 环境变量 | `0.0.0.0` | Console 监听地址 |
| `config.gateway.console.secret_key` | 配置文件 | `"change-me-in-production-use-a-longer-key!"` | standalone 模式 JWT 密钥 |
| `config.gateway.console.token_expire_minutes` | 配置文件 | `480` | standalone token 过期时间 |

---

## 4. 依赖关系

### 上游依赖
- `nanobot.cli.commands.app` — Typer 应用实例
- `nanobot.cli.commands.app.registered_commands` — 注册的命令列表

### Sidecar 内部依赖
- `ava.console.app.create_console_app` — full mode 工厂（直接持有 AgentLoop）
- `ava.console.app.create_console_app_standalone` — standalone mode 工厂（HTTP proxy）
- `ava.patches.loop_patch.get_agent_loop()` — 提供 live AgentLoop 引用
- `ava.launcher.register_patch` — 自注册机制

### 外部依赖
- `uvicorn` — ASGI 服务器

---

## 5. 关键实现细节

### 5.1 三层包装
```
gateway_cmd.callback → patched_gateway → patched_asyncio_run → _with_console()
```
- 第一层：替换 Typer command callback
- 第二层：临时替换 `asyncio.run`（单次使用，`_intercepted` 标记防止递归）
- 第三层：在 async 函数中创建 Console 后台任务

### 5.2 asyncio.run 恢复
- 使用 `try/finally` 确保 `asyncio.run` 被恢复
- `_intercepted["done"]` 标记确保只拦截一次

### 5.3 Console 生命周期
- Console 作为 `asyncio.Task` 运行
- Gateway 主协程退出时，cancel Console 任务
- `CancelledError` 被静默处理

### 5.4 Full mode / standalone mode
- 若 `loop_patch` 已记录 live `AgentLoop`，优先走 `create_console_app()` full mode
- 若没有 `AgentLoop` 引用，则退回 `create_console_app_standalone()`，通过 HTTP 代理 gateway

### 5.5 优雅降级
- `gateway` 命令在 Typer app 中未找到时：跳过 patch
- `create_console_app()` 失败时：仅 warning，Gateway 正常启动

---

## 6. 测试要点

| 测试场景 | 验证内容 |
|----------|----------|
| Gateway 命令查找 | 正确找到 `gateway` 回调 |
| Gateway 未注册 | 命令不存在时优雅跳过 |
| Console 启动 | Console uvicorn server 正确启动 |
| Console 端口 | 优先读 `config.gateway.console.port`，否则回退 `CAFE_CONSOLE_PORT` |
| Full/standalone 切换 | 有无 `AgentLoop` 引用时选择正确工厂 |
| Console 失败 | `create_console_app()` 异常时 Gateway 不受影响 |
| 生命周期 | Gateway 退出时 Console 被 cancel |
| asyncio.run 恢复 | patch 后 `asyncio.run` 恢复原始版本 |
| 幂等性 | 多次调用不会多层包装 |
