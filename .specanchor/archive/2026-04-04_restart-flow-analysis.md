---
specanchor:
  level: task
  task_name: "Restart 链路分析与优化"
  author: "@fanghu"
  created: "2026-04-04"
  status: "deprecated"
  last_change: "v2: deprecated — 被 2026-04-04_lifecycle-and-frontend-hotupdate.md 替代"
  related_modules:
    - ".specanchor/modules/console_patch_spec.md"
  related_global:
    - ".specanchor/global-patch-spec.md"
  superseded_by: ".specanchor/tasks/2026-04-04_lifecycle-and-frontend-hotupdate.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "RESEARCH"
  branch: "refactor/sidecar"
---

# ~~Restart 链路分析与优化~~

> **⚠️ DEPRECATED**：本文档已被 [2026-04-04_lifecycle-and-frontend-hotupdate.md](./2026-04-04_lifecycle-and-frontend-hotupdate.md) 替代。
>
> **废弃原因**：§2.3 "保持现有，精简脚本"与 supervisor-first 方向冲突；P0 优先级放在前端 rebuild 而非 lifecycle contract。
> 本文档的有价值部分（现状分析、前端 rebuild 方案、page-agent 独立重启）已合并到新 Spec。
>
> 以下内容仅保留作为历史参考。

---

# （历史内容）Restart 链路分析与优化

## 1. 现状分析

### 1.1 当前 Restart 链路全景

```text
┌──────────────┐    POST /api/gateway/restart     ┌──────────────────┐
│  Console UI  │ ──────────────────────────────→   │  GatewayService  │
│ DashboardPage│                                   │  .restart()      │
│  (React SPA) │                                   └───────┬──────────┘
│              │                                           │
│ countdown ← │                                           ▼
│ reconnect ← │                               ┌────────────────────┐
│              │                               │ restart_gateway.sh │
│              │                               │        │           │
│              │                               │        ▼           │
│              │                               │ restart_wrapper.sh │
│              │                               │        │           │
│              │                               │        ▼           │
│              │                               │ restart_daemon.sh  │
│              │                               │  (setsid, 独立进程) │
│              │                               │        │           │
│              │                               │  1. sleep delay_ms │
│              │                               │  2. kill gateway   │
│              │                               │  3. nohup nanobot  │
│              │                               │     gateway        │
│              │                               │  4. create cron    │
│              │                               │     report job     │
│              │                               └────────────────────┘
└──────────────┘

耗时分解:
  delay_ms (默认 5s) + SIGTERM 优雅关闭 (最多 30s) + start (3s) + verify
  典型时间：5s + 5s + 3s = ~13s
  最坏情况：5s + 30s + 3s = ~38s
```

### 1.2 涉及的组件

| 层 | 文件 | 职责 | 重启时行为 |
|---|------|------|-----------|
| **前端 UI** | `console-ui/src/pages/DashboardPage.tsx` | 触发重启、countdown、重连 | 显示 countdown → 轮询重连 |
| **后端 API** | `ava/console/routes/gateway_routes.py` | `POST /gateway/restart` 路由 | 调用 GatewayService |
| **服务层** | `ava/console/services/gateway_service.py` | 查找脚本、启动子进程 | 启动 restart_daemon 后立即返回 |
| **脚本层** | `ava/skills/restart_gateway/scripts/` | 3 个 bash 脚本（gateway → wrapper → daemon） | 独立进程执行 kill + start |
| **WebSocket** | ChatPage / BgTasksPage / BrowserPage | 实时通信 | 连接断开 → `onclose` → 自动重连（2-3s 间隔） |
| **Console 后端** | `ava/patches/console_patch.py` | FastAPI 应用生命周期 | 随 gateway 进程一起死亡和重启 |
| **page-agent-runner** | `console-ui/e2e/page-agent-runner.mjs` | Playwright 浏览器进程 | 随 PageAgentTool 的宿主进程死亡 |

### 1.3 当前问题

#### P1: 重启是全有全无的——无法只更新前端

```text
当前：改了一行 CSS → npm run build → 重启整个 gateway（杀 Python 进程 + Telegram bot + 所有 WS 连接）
期望：改了前端 → rebuild → 无需重启 gateway
```

**根因**：Console 的前端静态文件由 `console_patch.py` 中的 FastAPI `StaticFiles` mount 服务。build 产物在 `console-ui/dist/`。FastAPI 用的是 Starlette 的 StaticFiles，它不缓存文件内容，每次请求都从磁盘读取。所以理论上 `npm run build` 后前端就已更新——但浏览器缓存（强缓存 / Service Worker）可能阻止用户看到新版本。

#### P2: 没有前端版本检测 + 强制刷新机制

当 `npm run build` 产生新的 hash 文件名（如 `index-BGV7e4HJ.js` → `index-XYZ12345.js`），旧页面持有旧 JS 引用，不刷新就不会加载新代码。当前没有：
- 版本号 / hash 检测
- 提示"新版本可用，请刷新"
- 强制缓存失效机制

#### P3: Gateway 重启时的中断影响

Gateway 重启时以下服务中断：
- 所有 WebSocket 连接（Chat / BgTasks / Browser）
- 正在处理的 LLM 请求
- 后台任务（bg_tasks 中 running 的任务被 kill）
- page-agent-runner 子进程
- Telegram bot 连接

#### P4: 重启后状态恢复不完整

- bg_tasks：running 状态的任务在重启后变为"丢失"（SQLite 中记录为 running 但实际 asyncio task 不存在）
- page-agent-runner：需要重新启动
- Chat WS：自动重连 2s 间隔，能恢复，但中间的消息可能丢失
- Token stats：已持久化到 DB，不丢失

### 1.4 调用链路详情

#### 1.4.1 DashboardPage 触发

```typescript
// console-ui/src/pages/DashboardPage.tsx
const handleRestart = async (force: boolean) => {
  if (!confirm(...)) return;
  setRestarting(true);
  const delayMs = 5000;
  await api('/gateway/restart', { method: 'POST', body: { delay_ms: delayMs, force } });
  setCountdown(Math.ceil(delayMs / 1000) + 5);  // countdown = 10s
  setGwMessage({ type: 'success', text: `网关重启将在 ${delayMs/1000}s 后执行` });
  // countdown 每秒 -1，到 0 时结束
};
```

**问题**：countdown 硬编码 `delay + 5s`，实际重启可能需要更长或更短时间。

#### 1.4.2 GatewayService

```python
# ava/console/services/gateway_service.py
async def restart(self, delay_ms=5000, force=False):
    script = self._skill_dir / "restart_gateway" / "scripts" / "restart_gateway.sh"
    cmd = ["bash", str(script), "--delay", str(delay_ms), "--confirm"]
    self._restart_task = asyncio.create_task(self._run_restart_subprocess(cmd))
    return {"status": "restart_scheduled", "delay_ms": delay_ms}
```

**问题**：`_run_restart_subprocess` 等待进程完成（`communicate()`），但该进程 exec 到 wrapper 后会立即返回（因为 daemon fork 了）。所以实际上不需要 120s timeout。

#### 1.4.3 脚本三层结构

```text
restart_gateway.sh
  ├── 新模式 → exec restart_wrapper.sh
  │     └── bash restart_daemon.sh &  (后台启动)
  │         └── sleep → kill → nohup nanobot gateway
  └── legacy 模式（内联执行，不推荐）
```

**问题**：
- 三层脚本的存在是历史演进痕迹，增加了理解和维护成本
- `restart_gateway.sh` 的 legacy 模式保留了大量代码但已不推荐使用
- daemon 日志在 `/tmp/gateway_restart_daemon.log`，不容易被发现

## 2. 优化方案

### 2.1 核心思路：三路分离

```text
┌─────────────────────────────────────────────────────────────┐
│                    Restart 控制面板                          │
│   ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐ │
│   │  前端 Rebuild │ │ Gateway 重启 │ │ page-agent 重启    │ │
│   │  (独立链路)   │ │ (现有链路)   │ │ (按需链路)         │ │
│   └──────┬───────┘ └──────┬───────┘ └────────┬───────────┘ │
│          │                │                   │             │
│          ▼                ▼                   ▼             │
│  npm run build      restart_daemon.sh   runner shutdown    │
│  + 版本通知         + kill + start      + runner restart    │
│  (≈ 4s, 零中断)    (≈ 13s, 全中断)    (≈ 2s, 页面中断)    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 链路 A：前端 Rebuild（零中断热更新）

**目标**：修改前端代码后，无需重启 gateway，用户刷新即可看到新版本。

**实现**：

1. **Build API**：新增 `POST /api/console/rebuild`
   - 在服务端执行 `npm run build`（子进程，工作目录 = `console-ui/`）
   - 返回 build 状态（成功/失败/日志）
   - FastAPI StaticFiles 自动服务新文件（每次请求读磁盘）

2. **版本检测**：
   - build 后写一个 `console-ui/dist/version.json`（包含 build hash + timestamp）
   - 前端定期轮询 `GET /version.json`（60s 间隔）
   - hash 不匹配 → 弹出 toast "新版本可用，点击刷新"
   - 或 build API 通过 WS 广播 `{ type: "console_updated", version: "..." }`

3. **缓存策略**：
   - Vite 产物已带 hash（如 `index-BGV7e4HJ.js`），浏览器缓存安全
   - `index.html` 不缓存（FastAPI 设置 `Cache-Control: no-cache`）
   - 新 build 产生新 hash → 旧引用 404 → 用户需要刷新

**优势**：零中断，gateway / WS / bg_tasks / Telegram bot 全部不受影响。

### 2.3 链路 B：Gateway 重启（保持现有，精简脚本）

**保持不变**：
- DashboardPage 触发
- GatewayService 调度
- daemon 独立进程执行

**优化项**：
- 合并三层脚本为一个 `restart_daemon.sh`（wrapper 逻辑内联）
- 重启后 bg_tasks 中 status=running 的任务标记为 interrupted（而非丢失）
- 通过 WS 广播 `gateway_restarting` 事件让前端提前感知

### 2.4 链路 C：page-agent-runner 独立重启

**场景**：page-agent-runner.mjs 代码更新后需要重启，但不需要重启整个 gateway。

**实现**：
- `page_agent.py` 已有 `_shutdown_runner()` 方法
- 新增 tool action `page_agent(action="restart_runner")`
- Console API：`POST /api/page-agent/restart-runner`

### 2.5 UI 改造

DashboardPage 控制面板改为三个独立操作：

| 操作 | 按钮 | 影响 | 耗时 |
|-----|------|------|------|
| 前端 Rebuild | 🔨 Build | 无中断，需刷新浏览器 | ~4s |
| Gateway 重启 | 🔄 Restart / ⚡ Force | 全中断 | ~13s |
| Runner 重启 | 🌐 Restart Runner | page-agent 链路短暂中断 | ~2s |

### 2.6 实施优先级

| 优先级 | 项目 | 原因 |
|--------|------|------|
| P0 | 前端 Rebuild API + 版本检测 | 最常用，ROI 最高 |
| P1 | 脚本精简 + bg_tasks interrupted 恢复 | 降低维护成本 |
| P2 | page-agent-runner 独立重启 | 使用频率较低 |

### 2.7 文件变更预估

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `ava/console/routes/console_routes.py` | 新建或修改 | `POST /api/console/rebuild` |
| `ava/console/services/console_service.py` | 新建或修改 | build 子进程管理 |
| `console-ui/src/pages/DashboardPage.tsx` | 修改 | 三路操作按钮 + 版本检测 |
| `console-ui/src/hooks/useVersionCheck.ts` | 新建 | 版本轮询 + toast 提示 |
| `console-ui/vite.config.ts` | 修改 | build 后写 `version.json` |
| `ava/console/app.py` | 修改 | `index.html` 的 `Cache-Control: no-cache` |
| `ava/skills/restart_gateway/scripts/` | 精简 | 合并为单脚本 |
| `ava/agent/bg_tasks.py` | 修改 | 启动时检测 orphan running tasks |
| `ava/tools/page_agent.py` | 修改 | 新增 `restart_runner` action |
| `ava/console/routes/page_agent_routes.py` | 修改 | `POST /api/page-agent/restart-runner` |

## 3. 关键发现

### 3.1 前端热更新可能已部分可用

FastAPI 的 `StaticFiles` 每次请求都读磁盘。如果 `npm run build` 产生新文件，理论上下一次访问就能拿到新版本。**阻塞点只是浏览器缓存和 JS 引用**。Vite 的 hash 文件名策略意味着：
- 新 build → 新 hash 文件名
- 旧 `index.html` 引用旧 hash → 能正常工作（直到旧文件被清理）
- 新 `index.html` 引用新 hash → 需要刷新页面加载新 HTML

所以核心问题是：**让浏览器知道需要刷新**。这可以通过版本检测 + toast 实现，甚至不需要 rebuild API（用户自己跑 `npm run build` 也行）。

### 3.2 Gateway 重启的"自我毁灭"困境

当 gateway 进程执行 restart：
1. API 请求到达 → 启动 daemon
2. daemon sleep → kill gateway → gateway 进程死亡
3. Console 后端（在 gateway 进程内）也死亡
4. 所有 WS 连接断开
5. daemon 启动新 gateway → Console 后端重新初始化

第 2-4 步是不可避免的（gateway 重启 = Python 进程重启）。daemon 模式已经是最优解。

### 3.3 page-agent-runner 的生命周期

runner 是 `PageAgentTool` 启动的 Node 子进程。它的生命周期绑定到 gateway 进程（atexit 清理）。runner 重启不需要 gateway 重启——只需调用 `_shutdown_runner()` 然后下次 `_ensure_runner()` 会自动重启。

## 4. 待决策

- [ ] rebuild API 是否需要认证？（建议：admin only）
- [ ] 版本检测轮询间隔？（建议：60s）
- [ ] 是否需要保留旧 build 产物以支持未刷新的浏览器标签？
- [ ] bg_tasks orphan tasks 恢复策略：标记 interrupted 还是尝试重试？
- [ ] 是否需要在 DashboardPage 显示前端版本号和 build 时间？
