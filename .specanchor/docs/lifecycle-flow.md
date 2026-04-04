# Ava 生命周期完整调度流程

> 本文档描述 Ava Sidecar 的三层生命周期管理架构及完整调度流程。

---

## 1. 架构总览

```
 +-----------------------------------------------------------------+
 |                    外部 Supervisor 层                             |
 |  Docker (restart: unless-stopped) / systemd (Restart=always)     |
 |  职责: 检测进程退出 -> 自动拉起新进程                               |
 +-------------------------------+---------------------------------+
                                 | 进程退出 / 拉起
                                 v
 +-----------------------------------------------------------------+
 |                    Ava 进程内控制面                                |
 |                                                                  |
 |  +--------------------+  +----------------+  +----------------+  |
 |  |  LifecycleManager  |  | GatewayControl |  | GatewayService |  |
 |  | (ava/runtime/      |  | Tool           |  | (Console API)  |  |
 |  |  lifecycle.py)     |  | (status/restart)|  |                |  |
 |  +--------+-----------+  +-------+--------+  +-------+--------+  |
 |           |                      |                    |           |
 |  +--------+--------+   +--------+--------+  +--------+--------+  |
 |  | Runtime State    |   | Agent (LLM)     |  | Console UI      |  |
 |  | ~/.nanobot/      |   | 调用 tool       |  | 调用 REST API   |  |
 |  | runtime/         |   | action          |  |                 |  |
 |  +------------------+   +-----------------+  +-----------------+  |
 |                                                                   |
 |  +-------------------------------------------------------------+  |
 |  |            三条正交生命周期链路                                  |  |
 |  |  A. Gateway 重启 --- 全进程优雅退出 -> supervisor 拉起          |  |
 |  |  B. 前端热更新 ----- npm build -> 版本检测 -> 浏览器刷新        |  |
 |  |  C. Runner 重启 ---- 子进程 kill -> 自动 restart               |  |
 |  +-------------------------------------------------------------+  |
 +-------------------------------------------------------------------+
```

---

## 2. 启动流程

```
python -m ava gateway
        |
        v
+-- ava/launcher.py -----------------------+
|  apply_all_patches()                      |
|  +-- context_patch                        |
|  +-- loop_patch        <-- 初始化入口     |
|  +-- tools_patch                          |
|  +-- templates_patch                      |
|  +-- ...                                  |
+-------------------------------------------+
        |
        v
+-- loop_patch.patched_init() ----------------------------------------+
|                                                                      |
|  1. Database (SQLite)                                                |
|  2. BackgroundTaskStore                                              |
|  3. LifecycleManager  <-- 核心初始化                                 |
|     |                                                                |
|     +-- 读取 ~/.nanobot/runtime/state.json                           |
|     +-- boot_generation += 1                                         |
|     +-- _detect_supervisor()                                         |
|     |   +-- AVA_SUPERVISOR env var (优先)                             |
|     |   +-- /proc/1/cgroup -> Docker                                 |
|     |   +-- INVOCATION_ID -> systemd                                 |
|     +-- recover_orphan_tasks()                                       |
|     |   +-- running/queued -> interrupted                            |
|     +-- check_pending_restart()                                      |
|     |   +-- 标记 restart_applied                                     |
|     +-- 写入新 state.json                                            |
|                                                                      |
|  4. tools_patch: 注册 gateway_control tool                           |
|  5. post-init: 回填 _lifecycle 到 gateway_control                    |
|  6. Console UI + FastAPI routes                                      |
|     +-- /api/gateway/status                                          |
|     +-- /api/gateway/health                                          |
|     +-- /api/gateway/restart                                         |
|     +-- /api/gateway/console/rebuild                                 |
+----------------------------------------------------------------------+
        |
        v
    Gateway 就绪
    /api/gateway/health -> { ready: true, boot_generation: N }
```

---

## 3. 链路 A: Gateway 优雅重启

### 3.1 触发入口

| 入口 | 调用方式 | 限制 |
|------|---------|------|
| Agent LLM | `gateway_control(action="restart", reason="...")` | 仅 cli/console 上下文 |
| Console UI | `POST /api/gateway/restart` | 仅 admin 角色 |

### 3.2 完整时序

```
调用者 (Agent / Console)
  |
  v
GatewayControlTool / GatewayService
  |
  +-- 检查 supervised == true ?
  |   +-- false -> 返回 "unsupervised, 请手动重启"
  |   +-- true  -> 继续
  |
  v
LifecycleManager.request_restart()
  |
  +-- 1. 写入 restart_request.json
  |      { requested_at, requested_by,
  |        task_id, origin_session_key,
  |        reason, force }
  |
  +-- 2. _initiate_shutdown()
  |      |
  |      +-- 标记 _shutting_down = true
  |      |
  |      +-- BackgroundTaskStore:
  |      |   遍历 active tasks -> update_status("interrupted")
  |      |   添加 event: "Interrupted by gateway restart"
  |      |
  |      +-- 写入 state.json:
  |      |   last_exit_reason = "restart requested by ..."
  |      |
  |      +-- os.kill(pid, SIGTERM)
  |
  v
进程退出 (exit code 0)
  |
  v
Supervisor 检测退出
  +-- Docker: restart: unless-stopped -> 自动拉起
  +-- systemd: Restart=always -> 自动拉起
  |
  v
新进程启动 -> 回到 S2 启动流程
  |
  +-- boot_generation += 1
  +-- recover_orphan_tasks()
  +-- check_pending_restart()
      |
      +-- 读取 restart_request.json
      +-- 标记 restart_applied = true
      +-- 删除 restart_request.json
      +-- (未来: 通过 origin_session_key 回写通知)
```

### 3.3 Supervisor 检测逻辑

```
AVA_SUPERVISOR 环境变量
        |
        +-- "docker"  -> supervised=true,  supervisor="docker"
        +-- "systemd" -> supervised=true,  supervisor="systemd"
        +-- "none"    -> supervised=false, supervisor="none"
        +-- "" / "auto" (默认)
                |
                +-- /proc/1/cgroup 包含 docker/containerd
                |   -> supervised=true, supervisor="docker"
                |
                +-- INVOCATION_ID env 存在
                |   -> supervised=true, supervisor="systemd"
                |
                +-- 都不匹配
                    -> supervised=false, supervisor="none"
```

### 3.4 force 模式

| 参数 | 默认 | force=true |
|------|------|-----------|
| 后台任务处理 | 标记 interrupted | 标记 interrupted |
| 总体超时 | 30s | 3-5s |
| 适用场景 | 正常运维 | 紧急修复 |

---

## 4. 链路 B: 前端热更新 (零中断)

### 4.1 触发入口

| 入口 | 调用方式 |
|------|---------|
| Console UI | Dashboard "Rebuild UI" 按钮 |
| REST API | `POST /api/gateway/console/rebuild` (admin) |

### 4.2 完整时序

```
管理员点击 "Rebuild UI"
  |
  v
POST /api/gateway/console/rebuild
  |
  v
rebuild_console_ui()
  |
  +-- 检查 asyncio.Lock (防并发)
  |   +-- 已锁定 -> 返回 "Rebuild already in progress"
  |
  +-- asyncio.Lock 加锁
  |
  +-- run_in_executor:
  |   _build_console_ui(console_ui_dir)
  |   +-- shutil.which("npm")
  |   +-- subprocess: npm run build
  |       +-- tsc -b
  |       +-- vite build
  |           +-- versionJsonPlugin -> dist/version.json
  |
  +-- write_version_json(dist/)
  |   +-- 遍历 dist/assets/ 计算 sha256
  |   +-- 写入 { hash, timestamp, built_at }
  |
  +-- 返回 RebuildResult { success, duration_ms, version_hash }
  |
  v
前端 useVersionCheck hook (60s 轮询)
  |
  +-- GET /version.json?_t=timestamp (no-cache)
  |
  +-- 首次请求 -> 记录 initialHash
  |
  +-- 后续请求 -> hash 变化 ?
      |
      +-- true  -> 显示 "前端新版本可用" banner
      |            用户点击 "刷新加载" -> window.location.reload()
      |
      +-- false -> 继续轮询
```

**零中断保证:**
- Gateway 进程不重启
- WebSocket 连接不断
- 后台任务不受影响
- Telegram bot 不断
- 只有浏览器刷新后生效

### 4.3 缓存策略

| 请求 | 来源 | Cache-Control |
|------|------|--------------|
| index.html | SPA fallback | no-cache, no-store, must-revalidate |
| version.json | 静态文件 | no-cache, no-store, must-revalidate |
| /assets/*.js | StaticFiles mount | 默认 (Vite content hash 保证唯一性) |
| /assets/*.css | StaticFiles mount | 默认 (同上) |

---

## 5. 链路 C: Runner 独立重启

### 5.1 触发入口

| 入口 | 调用方式 |
|------|---------|
| Agent LLM | `page_agent(action="restart_runner")` |
| Console API | `POST /api/page-agent/restart-runner` |

### 5.2 完整时序

```
调用 restart_runner
  |
  v
PageAgentTool._do_restart_runner()
  |
  +-- _shutdown_runner()
  |   +-- 发送 JSON-RPC: { method: "shutdown" }
  |   +-- wait_for(process.wait(), timeout=5s)
  |   +-- 超时 -> process.kill()
  |
  +-- self._process = None
  +-- cancel reader_task
  +-- cancel idle_task
  |
  v
返回: "Runner stopped. Will restart on next page_agent call."
  |
  v
下次 page_agent(action="execute/screenshot/...")
  |
  v
_ensure_runner() -> 检测 process is None
  |
  +-- asyncio.create_subprocess_exec(node, page-agent-runner.mjs)
  +-- 启动 stdout/stderr reader
  +-- 启动 idle watchdog
  +-- 发送 init RPC
  |
  v
Runner 就绪, 继续执行操作
```

---

## 6. Self-Improvement Loop 集成

### 6.1 完整闭环时序

```
用户/调度器 下发 coding 任务
  |
  v
BackgroundTaskStore.submit()
  |  task_id = "abc123"
  |  origin_session_key = "telegram:xxx"
  |
  v
claude_code / codex 执行代码修改
  |
  v
验证通过 (git diff + pytest + specanchor-check)
  |
  v
判断修改类型
  |
  +-- 仅前端改动 (.tsx / .css / .html)
  |   |
  |   +-- 调用 rebuild API (零中断)
  |       +-- 等待 version.json 更新 -> 完成
  |
  +-- Python 代码改动
  |   |
  |   +-- gateway_control(action="restart",
  |         reason="Applied feature X",
  |         task_id="abc123")
  |       |
  |       +-- LifecycleManager:
  |           +-- 写入 restart_request.json (含 task_id)
  |           +-- 标记 bg_tasks interrupted
  |           +-- SIGTERM -> 进程退出
  |               |
  |               v
  |           Supervisor 拉起新进程
  |               |
  |               v
  |           LifecycleManager.initialize()
  |           +-- boot_generation += 1
  |           +-- check_pending_restart()
  |           |   +-- 读取 restart_request.json
  |           |       task_id="abc123"
  |           |       origin_session_key="telegram:xxx"
  |           +-- 标记 restart_applied
  |           +-- (TODO: 回写到 origin session)
  |
  +-- page-agent-runner 相关改动
      |
      +-- page_agent(action="restart_runner") -> ~2s
```

### 6.2 任务状态流转

```
                    +----------+
                    |  queued  |
                    +----+-----+
                         | _run() 开始
                         v
                    +----------+
                    | running  |
                    +----+-----+
                         |
          +--------------+-------------+--------------+
          |              |             |              |
     正常完成      异常/错误      用户取消      进程重启
          |              |             |              |
          v              v             v              v
    +----------+  +----------+  +----------+  +-------------+
    |succeeded |  |  failed  |  |cancelled |  | interrupted |
    +----------+  +----------+  +----------+  +-------------+
                                    |              |
                                CancelledError  recover_orphan_tasks()
                                (/stop 命令)    (LifecycleManager 启动时)
```

---

## 7. 运行时文件布局

```
~/.nanobot/
+-- runtime/
|   +-- state.json              <-- LifecycleManager 运行时状态
|   |   { pid, boot_time, boot_generation,
|   |     supervised, supervisor, last_exit_reason }
|   |
|   +-- restart_request.json    <-- 重启请求 (临时文件)
|       { requested_at, requested_by,
|         task_id, origin_session_key, reason, force }
|
+-- nanobot.db                  <-- SQLite 数据库
|   +-- bg_tasks                    后台任务状态
|   +-- token_stats                 Token 使用统计
|
+-- workspace/
    +-- TOOLS.md                <-- 工具文档 (含 gateway_control)

console-ui/dist/
+-- index.html                  <-- SPA 入口 (Cache-Control: no-cache)
+-- version.json                <-- 版本哈希 (Cache-Control: no-cache)
+-- assets/
    +-- index-xxx.js            <-- Vite content-hash 产物
    +-- index-xxx.css
```

---

## 8. API 端点速查

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/gateway/status` | GET | viewer+ | 返回完整 lifecycle 状态 |
| `/api/gateway/health` | GET | 无 | 健康检查 (supervisor 用) |
| `/api/gateway/restart` | POST | admin | 请求优雅重启 |
| `/api/gateway/console/rebuild` | POST | admin | 触发前端重建 |
| `/api/page-agent/restart-runner` | POST | 无 | 重启 page-agent runner |
| `/api/page-agent/sessions` | GET | 无 | 列出活跃 session |

---

## 9. 工具调用速查

| 工具 | 动作 | 说明 |
|------|------|------|
| `gateway_control` | `status` | 查询 PID/uptime/supervisor/boot_generation |
| `gateway_control` | `restart` | 请求优雅重启 (仅 cli/console) |
| `page_agent` | `restart_runner` | 停止 runner (下次自动重启) |

---

## 10. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AVA_SUPERVISOR` | `auto` | supervisor 声明: `docker` / `systemd` / `none` / `auto` |
| `NANOBOT_CONSOLE_PORT` | `6688` | Console UI 端口 |

---

## 11. 关键设计决策

| 决策 | 理由 |
|------|------|
| Supervisor-first | 应用进程不应自己拉起自己; 由基础设施层负责 |
| 三链路正交 | 前端改动不需要杀 Python 进程; runner 改动不需要重启 gateway |
| 显式 contract 优先 | `AVA_SUPERVISOR` 环境变量比 heuristic 更可靠 |
| interrupted 状态 | 区分"用户取消"和"进程重启导致的中断" |
| restart_request 落盘 | 跨进程传递 task_id 和 reason, 支持 self-improvement 闭环 |
| version.json content hash | 不依赖时间戳或 git commit, 基于实际产物内容 |
| Lock 保护 rebuild | 防止并发 npm build 互相干扰 |
