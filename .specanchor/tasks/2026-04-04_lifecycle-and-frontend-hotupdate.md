---
specanchor:
  level: task
  task_name: "统一生命周期管理与前端热更新"
  author: "@fanghu"
  created: "2026-04-04"
  status: "draft"
  last_change: "v1: 综合 supervisor redesign + restart 分析 + Codex 锐评"
  related_modules:
    - ".specanchor/modules/ava-patches-console_patch.spec.md"
    - ".specanchor/modules/ava-patches-tools_patch.spec.md"
  related_tasks:
    - ".specanchor/tasks/2026-04-02_gateway-lifecycle-supervisor-redesign.md"
    - ".specanchor/tasks/2026-04-04_coding-cli-and-self-improvement-loop.md"
  supersedes:
    - ".specanchor/tasks/2026-04-04_restart-flow-analysis.md"
  related_global:
    - ".specanchor/global-patch-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "PLAN"
  branch: "refactor/sidecar"
---

# SDD Spec: 统一生命周期管理与前端热更新

## 0. Open Questions

- [x] 旧 `restart_gateway` 脚本体系是否保留？
  → **否**。整体删除 `ava/skills/restart_gateway/`，不做兼容保留。（继承 supervisor redesign spec 决策）
- [x] `restart` 的职责边界？
  → 只负责"当前进程有状态地退出"，由 supervisor（Docker / systemd）拉起。不再 `nohup` 自己拉起。
- [x] 前端更新是否需要 gateway 重启？
  → **不需要**。前端是独立的 build + 版本检测链路，与 gateway 生命周期正交。
- [x] page-agent-runner 重启是否需要 gateway 重启？
  → **不需要**。runner 是子进程，通过 tool action 独立管控。
- [x] Codex 锐评中"restart 应该变成 self-improvement task 可依赖的 lifecycle contract"？
  → **采纳**。restart request 关联 task_id / origin_session_key / reason，新进程启动后由 lifecycle manager 验证并回写。
- [x] supervisor 检测机制：怎么判断 supervised vs unsupervised？
  → **显式 contract 优先**：通过 `AVA_SUPERVISOR=docker|systemd|none|auto` 环境变量声明。
  → `auto` 模式下可做 Docker/systemd 探测，但仅用于**状态展示**，不作为 restart 放行条件。
  → restart 放行条件 = "显式声明 supervised" 或 "auto 且检测结果为强阳性（Docker cgroup / systemd INVOCATION_ID）"。
  → 不靠 ppid 等弱启发式。
- [x] graceful exit 分层设计？
  → 不是单一超时值，而是分层协议：
  → 1. 立即停止接收新请求
  → 2. 广播 `gateway_restarting` 事件（WS + 前端感知）
  → 3. in-flight HTTP/turn 处理 drain：默认 15s
  → 4. 后台 coding task 不等待完成，直接标 `interrupted`
  → 5. 总体 hard cap 30s；`force=true` 缩到 3-5s
- [x] "restart 成功" 的验收面是什么？
  → 最低配：`/api/gateway/status` 返回 `boot_generation` 递增
  → 更稳：新增 `/api/gateway/health` 返回明确的 ready 信号（所有核心服务初始化完成）
  → 该 health 端点同时服务 self-improvement loop 的 restart verification

---

## 1. Problem Framing

### 1.1 正确的问题

**不是**："怎么把 restart 流程做顺一点"（operator UX）
**而是**："怎么把 restart 变成 self-improvement task 可依赖的 lifecycle contract"（runtime loop）

当前缺失的核心能力是 **可信生命周期控制面**：
- 旧脚本是 `kill + nohup nanobot gateway`，违反 sidecar 入口（`python -m ava`）和 supervisor-first 原则
- `GatewayStatus` 只有 `running/pid/uptime/port`，没有 `supervised/restart_pending/last_exit_reason/boot_generation` 等闭环字段
- coding task 无法请求"改完代码后安全重启"，也无法验证"新进程是否用了新代码"
- 前端改动被迫触发全量重启（杀 Python 进程 + Telegram bot + 所有 WS + bg_tasks）

### 1.2 已有能力盘点

以下 self-improvement loop 前置条件已实现：

| 能力 | 状态 | 实现位置 |
|------|------|---------|
| BackgroundTaskStore | ✅ | `ava/agent/bg_tasks.py` |
| session_key 直传 | ✅ | `ava/patches/loop_patch.py` |
| context digest 注入 | ✅ | `ava/patches/context_patch.py` |
| Claude Code async wiring | ✅ | `ava/tools/claude_code.py` |
| Codex tool | ✅ | `ava/tools/codex.py` |
| Token stats + 异常终止 | ✅ | `ava/patches/loop_patch.py` |
| Page Agent + 浏览器持久化 | ✅ | `ava/tools/page_agent.py` |

**现在缺的就是 lifecycle backend + 前端热更新。**

### 1.3 与现有 Spec 的关系

| Spec 文件 | 关系 |
|-----------|------|
| `2026-04-02_gateway-lifecycle-supervisor-redesign.md` | **继承并扩展**。该 Spec 定义了 supervisor-first 方向、文件变更清单、测试覆盖。本 Spec 在其基础上补充：前端热更新链路、self-improvement loop 集成、restart 验证协议 |
| `2026-04-04_restart-flow-analysis.md` | **替代（deprecated）**。该分析报告的现状梳理有价值，但优化方案与 supervisor-first 方向冲突（"保持现有，精简脚本"）。有价值的增量（前端 rebuild、page-agent 独立重启、版本检测）已合并到本 Spec |
| `2026-04-04_coding-cli-and-self-improvement-loop.md` | **衔接**。该 Spec 的 Phase 3（自改进编排）依赖本 Spec 提供的 lifecycle contract |

---

## 2. Research Findings

### 2.1 现状问题（继承 restart-flow-analysis.md §1）

**调用链全景：**

```text
Console UI (DashboardPage)
  → POST /api/gateway/restart
    → GatewayService.restart()
      → bash restart_gateway.sh --delay 5000 --confirm
        → exec restart_wrapper.sh
          → bash restart_daemon.sh &
            → sleep → kill gateway → nohup nanobot gateway
```

**核心问题：**

1. **入口违规**：`nohup nanobot gateway` 而非 `python -m ava gateway`
2. **自拉起反模式**：应用进程自己 kill + nohup 重启，绕过 supervisor
3. **全有全无**：修改前端 CSS → 必须杀整个 Python 进程
4. **无闭环字段**：`GatewayStatus` 缺少 lifecycle 状态
5. **状态丢失**：bg_tasks running 的任务变为"丢失"
6. **脚本冗余**：三层 shell 脚本 + watchdog + launchd plist，维护成本高

### 2.2 可利用的已有能力

1. **Docker supervisor**：`docker-compose.yml` 已配置 `restart: unless-stopped`
2. **StaticFiles 无缓存读取**：FastAPI StaticFiles 每次请求从磁盘读取，`npm run build` 后新文件即时可用
3. **Vite hash 文件名**：build 产物自带 content hash，浏览器缓存安全
4. **page-agent-runner 已有 shutdown hook**：`_shutdown_runner()` + 自动 `_ensure_runner()`
5. **atexit 清理**：runner 子进程已注册 atexit 清理

### 2.3 supervisor-first 设计结论（继承 supervisor redesign spec §2.2）

- 生命周期分层：Supervisor 负责 crash 重拉 → Ava 进程内负责状态、请求、优雅退出
- `restart` ≠ "拉起新进程"，而是 "当前进程有状态地退出，由 supervisor 拉起"
- "watchdog""平台 daemon""自动汇报" 不应与基础 restart 绑定

---

## 3. Architecture

### 3.1 三层架构总览

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        Lifecycle Control Plane                        │
│                                                                       │
│  ┌───────────────────┐  ┌────────────────────┐  ┌──────────────────┐ │
│  │ Gateway Lifecycle  │  │ Frontend Hot Update │  │ Runner Lifecycle │ │
│  │ (supervisor-first) │  │  (orthogonal)       │  │ (child process)  │ │
│  └─────────┬─────────┘  └────────┬───────────┘  └────────┬─────────┘ │
│            │                      │                       │           │
│            ▼                      ▼                       ▼           │
│  lifecycle.py              console rebuild API    page_agent tool     │
│  + gateway_control tool    + version.json         action=restart_runner│
│  + GatewayService          + WS broadcast         + _shutdown_runner  │
│            │                      │                       │           │
│            ▼                      ▼                       ▼           │
│  进程优雅退出              npm run build            子进程 kill+restart│
│  supervisor 拉起           浏览器刷新提示           自动 _ensure_runner│
│  (~13s, 全中断)           (~4s, 零中断)            (~2s, 页面中断)    │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Layer A: Gateway Lifecycle Backend

**文件**：`ava/runtime/lifecycle.py`

**职责**：
- 启动时写入 runtime 状态到 `~/.nanobot/runtime/`
- 记录 PID、启动时间、boot generation（单调递增）
- 检测是否受 supervisor 管理
- 接收和落盘 restart request（含 requester 元数据）
- 协调优雅退出（drain in-flight → SIGTERM → force timeout）
- 新进程启动后检查 pending restart request，标记 `restart_applied` / `restart_failed`

**Runtime 状态文件**：`~/.nanobot/runtime/state.json`

```json
{
  "pid": 12345,
  "boot_time": 1712234567.0,
  "boot_generation": 7,
  "supervised": true,
  "supervisor": "docker",
  "entry_point": "python -m ava gateway",
  "last_exit_reason": null,
  "restart_request": null
}
```

**Restart Request 结构**：

```json
{
  "requested_at": 1712234600.0,
  "requested_by": "console",
  "task_id": "abc123",
  "origin_session_key": "console:session_xyz",
  "reason": "Code changes applied, restart required",
  "force": false
}
```

**Supervisor 检测逻辑（显式 contract 优先）**：

```python
def _detect_supervisor() -> tuple[bool, str]:
    """检测是否受 supervisor 管理。

    优先级：显式声明 > 强阳性探测 > 默认 unsupervised。
    弱启发式（如 ppid）仅用于状态展示，不用于 restart 放行。
    """
    # 一等真相：显式环境变量 AVA_SUPERVISOR
    env_val = os.environ.get("AVA_SUPERVISOR", "").lower()
    if env_val in ("docker", "systemd"):
        return True, env_val
    if env_val == "none":
        return False, "none"

    # auto 模式（默认）：强阳性探测
    # Docker: /proc/1/cgroup 包含 docker/containerd
    if Path("/proc/1/cgroup").exists():
        try:
            cgroup = Path("/proc/1/cgroup").read_text()
            if "docker" in cgroup or "containerd" in cgroup:
                return True, "docker"
        except OSError:
            pass
    # systemd: INVOCATION_ID 存在（强信号）
    if os.environ.get("INVOCATION_ID"):
        return True, "systemd"

    return False, "none"
```

**restart 放行条件**：
- `supervised == True` → 允许
- `supervised == False` 且 `AVA_SUPERVISOR` 未设置 → 返回 unsupported 提示
- `supervised == False` 且 `AVA_SUPERVISOR=none` → 明确拒绝，返回"请手动重启"

### 3.3 Layer B: Gateway Control Tool

**文件**：`ava/tools/gateway_control.py`

**动作**：`status` / `restart`

**约束**：
- `restart` 仅允许 `cli` / `console` 上下文
- `restart` 在 unsupervised 模式下返回 `"unsupported without supervisor"`
- `restart` 不直接拉起新进程

**Self-improvement loop 集成**：

```python
class GatewayControlTool(Tool):
    async def execute(self, action, reason=None, force=False, **kwargs):
        if action == "status":
            return self._lifecycle.get_status()

        if action == "restart":
            # 限制上下文
            if self._channel not in ("cli", "console"):
                return "restart 仅允许在 cli/console 上下文执行"
            # 检查 supervisor
            if not self._lifecycle.supervised:
                return "当前为 unsupervised 模式，不支持自动重启。请手动重启进程。"
            # 写入 restart request（关联 task_id）
            self._lifecycle.request_restart(
                requested_by=f"{self._channel}:{self._chat_id}",
                task_id=kwargs.get("task_id"),
                origin_session_key=self._session_key,
                reason=reason or "Manual restart requested",
                force=force,
            )
            return "Restart request submitted. Process will exit gracefully."
```

### 3.4 Layer C: Frontend Hot Update（与 Gateway 生命周期正交）

**实现方案**：

1. **Build API**：`POST /api/console/rebuild`
   - 复用 `ava/console/ui_build.py` 的 `_build_console_ui()` 逻辑（已有 npm 检测、输出捕获、错误处理）
   - 新增异步封装 `rebuild_console_ui()` → 返回 build 状态（成功/失败/日志/耗时）
   - 路由挂在 `gateway_routes.py`（已有 admin 认证中间件），不新建 `console_routes.py`
   - Admin only（需认证）

2. **版本检测**：
   - Vite 插件：build 后生成 `console-ui/dist/version.json`（包含 `{ hash, timestamp, version }`）
   - 前端 hook `useVersionCheck()`：60s 轮询 `GET /version.json`
   - hash 不匹配 → toast "新版本可用，点击刷新"
   - 可选增强：build 完成后通过 WS 广播 `{ type: "console_updated", version }`

3. **缓存策略**：
   - `index.html`：`Cache-Control: no-cache`（在 `ava/console/app.py` 的 `spa_fallback` 中设置响应头）
   - Vite 产物：content hash 文件名（自然过期）
   - 无需清理旧 build 产物（hash 不同，不冲突）

**零中断保证**：Gateway 进程、WS 连接、bg_tasks、Telegram bot 全部不受影响。

### 3.5 Layer D: Runner 独立管控

**已有基础**：`page_agent.py` 的 `_shutdown_runner()` + `_ensure_runner()`

**新增**：
- Tool action `page_agent(action="restart_runner")`
- Console API `POST /api/page-agent/restart-runner`

**实现**：

```python
# page_agent.py 新增分支
if action == "restart_runner":
    await self._shutdown_runner()
    # 下次 _ensure_runner() 调用时自动重启
    return "Runner stopped. Will restart on next page_agent call."
```

### 3.6 Self-Improvement Loop 的 Restart 集成

**闭环时序**：

```text
1. Coding task 完成代码修改（claude_code / codex）
2. Task 运行验证：git diff + pytest + specanchor-check.sh
3. 验证通过 → Task 判断是否需要重启
   3a. 仅前端改动 → 调用 rebuild API（零中断）
   3b. Python 代码改动 → 调用 gateway_control(action="restart", reason=..., task_id=...)
4. lifecycle manager 落盘 restart_request（含 task_id + origin_session_key）
5. 当前进程 drain in-flight requests → 优雅退出
6. Supervisor（Docker / systemd）检测退出 → 拉起新进程
7. 新进程 lifecycle manager 启动：
   7a. 读取 pending restart_request
   7b. boot_generation += 1
   7c. 验证：新进程可达 + API healthy
   7d. 标记 restart_applied（附 boot_generation）
   7e. 通过 BackgroundTaskStore 回写到 origin_session_key
8. 原始 session 收到通知：restart 成功/失败
```

**bg_tasks orphan recovery**：

> **前置变更**：需要先将 `interrupted` 纳入 `BackgroundTaskStore` 的正式状态枚举。
> 当前 `TaskStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]`，
> 需扩展为 `Literal["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]`。
> 同步更新：DB schema 的 CHECK 约束（如有）、UI 查询口径、Console 前端状态颜色映射。

```python
# bg_tasks.py 状态枚举扩展
TaskStatus = Literal[
    "queued", "running", "succeeded", "failed", "cancelled",
    "interrupted",  # 进程重启导致的非正常终止
]

# lifecycle manager 启动时
def recover_orphan_tasks(self):
    """将上一代 running/queued 的任务标记为 interrupted"""
    orphans = self._bg_store.query_by_status(["running", "queued"])
    for task in orphans:
        self._bg_store.update_status(
            task.task_id,
            status="interrupted",
            error_message=f"Interrupted by gateway restart (gen {self.boot_generation})"
        )
    return len(orphans)
```

---

## 4. Plan (Contract)

### 4.1 Phase A: Lifecycle Backend（P0）

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 1 | `ava/runtime/__init__.py` | 新增 | 包初始化 |
| 2 | `ava/runtime/lifecycle.py` | 新增 | LifecycleManager：runtime state / restart request / 退出协调 / supervisor 检测 / orphan recovery |
| 3 | `ava/tools/gateway_control.py` | 新增 | `status` / `restart` 两个动作，cli/console only |
| 4 | `ava/patches/tools_patch.py` | 修改 | 注册 `gateway_control` 工具 |
| 5 | `ava/patches/console_patch.py` | 修改 | Gateway 启动时初始化 LifecycleManager，写 PID/boot state |
| 6 | `ava/console/services/gateway_service.py` | 修改 | 移除 shell subprocess，改走 LifecycleManager |
| 7 | `ava/console/models.py` | 修改 | `GatewayStatus` 新增 `supervised` / `supervisor` / `restart_pending` / `boot_generation` |
| 8 | `ava/console/routes/gateway_routes.py` | 修改 | restart/status API 改为 LifecycleManager 语义 |
| 9 | `ava/agent/bg_tasks.py` | 修改 | 新增 orphan recovery（启动时 running → interrupted） |
| 10 | `ava/skills/restart_gateway/` | 删除 | 旧 skill 全目录删除 |
| 11 | `ava/console/services/config_service.py` | 修改 | 移除 `restart_gateway.json` 可编辑配置入口 |

### 4.2 Phase B: Frontend Hot Update（P1，与 Phase A 并行开发）

> **复用基础设施**：`ava/console/ui_build.py` 已有启动时 build/freshness 检查逻辑和测试
> （`tests/console/test_ui_build.py`）。rebuild API 应复用 `_build_console_ui()`，不另造一套。

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 12 | `ava/console/routes/gateway_routes.py` | 修改 | 新增 `POST /api/console/rebuild`（复用现有 router，不新建 console_routes） |
| 13 | `ava/console/ui_build.py` | 修改 | 新增 `rebuild_console_ui()` 异步封装（调用现有 `_build_console_ui`） |
| 14 | `console-ui/vite.config.ts` | 修改 | build 后生成 `version.json` |
| 15 | `console-ui/src/hooks/useVersionCheck.ts` | 新增 | 60s 轮询版本 + toast 提示 |
| 16 | `console-ui/src/pages/DashboardPage.tsx` | 修改 | 三路操作按钮 + 版本信息展示 |
| 17 | `ava/console/app.py` | 修改 | SPA fallback 中 `index.html` 返回时设置 `Cache-Control: no-cache` |

### 4.3 Phase C: Runner 独立重启（P2）

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 18 | `ava/tools/page_agent.py` | 修改 | 新增 `restart_runner` action |
| 19 | `ava/console/routes/page_agent_routes.py` | 修改 | `POST /api/page-agent/restart-runner` |

### 4.4 Phase D: 文档与清理

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 20 | `README.md` | 修改 | supervisor 示例统一为 `python -m ava gateway` |
| 21 | `ava/templates/TOOLS.md` | 修改 | 新增 `gateway_control` 工具文档 |
| 22 | `.specanchor/tasks/2026-04-04_restart-flow-analysis.md` | 修改 | 标记 deprecated，指向本 Spec |

### 4.5 Tests

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 23 | `tests/runtime/test_lifecycle_manager.py` | 新增 | runtime state / restart request / supervisor 检测 / orphan recovery / graceful shutdown 分层 |
| 24 | `tests/tools/test_gateway_control.py` | 新增 | status / restart / 上下文限制 / unsupervised 拒绝 / task_id 关联 |
| 25 | `tests/console/test_gateway_service.py` | 修改 | 确认不再 shell 到脚本 |
| 26 | `tests/security/test_no_embedded_secrets.py` | 新增 | 扫描仓库禁止 bot token / 私钥 |
| 27 | `tests/console/test_ui_build.py` | 修改 | 新增 `rebuild_console_ui()` 异步封装测试 |
| 28 | `tests/agent/test_bg_tasks.py` | 修改 | 新增 `interrupted` 状态覆盖：orphan recovery、查询、UI 映射 |

---

## 5. Interfaces

### 5.1 LifecycleManager

```python
# ava/runtime/lifecycle.py

class LifecycleManager:
    """进程生命周期管理器"""

    def __init__(self, runtime_dir: Path | None = None, bg_store=None):
        self.runtime_dir = runtime_dir or Path.home() / ".nanobot" / "runtime"
        self.boot_generation: int = 0
        self.boot_time: float = 0.0
        self.supervised: bool = False
        self.supervisor: str = "none"
        self._bg_store = bg_store

    def initialize(self) -> None:
        """启动时调用：写 state / 检测 supervisor / recovery"""
        ...

    def get_status(self) -> dict:
        """返回完整 lifecycle 状态"""
        ...

    def request_restart(
        self,
        *,
        requested_by: str,
        task_id: str | None = None,
        origin_session_key: str | None = None,
        reason: str = "",
        force: bool = False,
    ) -> None:
        """落盘 restart request → 触发优雅退出"""
        ...

    async def graceful_shutdown(self, drain_timeout: float = 15.0, hard_cap: float = 30.0) -> None:
        """分层优雅退出：
        1. 立即停止接收新请求
        2. 广播 gateway_restarting 事件
        3. drain in-flight HTTP/turn（drain_timeout 秒）
        4. 后台 coding task 标记 interrupted（不等待完成）
        5. 设置 exit reason → sys.exit
        force=True 时 hard_cap 缩至 3-5s
        """
        ...

    def recover_orphan_tasks(self) -> int:
        """启动时将上一代 running 的 bg_tasks 标记为 interrupted"""
        ...

    def check_pending_restart(self) -> dict | None:
        """启动时检查是否有未完成的 restart request"""
        ...

    def mark_restart_applied(self, request: dict) -> None:
        """标记 restart 已完成，回写到 BackgroundTaskStore"""
        ...
```

### 5.2 GatewayStatus（扩展）

```python
class GatewayStatus(BaseModel):
    running: bool
    pid: int | None = None
    uptime_seconds: float | None = None
    gateway_port: int | None = None
    console_port: int | None = None
    # 新增 lifecycle 字段
    supervised: bool = False
    supervisor: str | None = None
    restart_pending: bool = False
    boot_generation: int = 0
    last_exit_reason: str | None = None
```

### 5.3 GatewayControlTool

```python
class GatewayControlTool(Tool):
    name = "gateway_control"
    description = "查询网关状态或请求重启"
    parameters = {
        "action": {"type": "string", "enum": ["status", "restart"]},
        "reason": {"type": "string", "description": "重启原因"},
        "force": {"type": "boolean", "default": False},
    }

    async def execute(self, action: str, **kwargs) -> str: ...
```

---

## 6. Implementation Checklist

### Phase A: Lifecycle Backend

- [x] A0. `ava/agent/bg_tasks.py`：`TaskStatus` 枚举扩展，新增 `"interrupted"`
  - [x] query_history WHERE 子句包含 interrupted
  - [x] 新增 `recover_orphan_tasks()` 方法
  - [ ] Console 前端 interrupted 状态颜色/图标映射（Phase B 时一并处理）
- [x] A1. `ava/runtime/lifecycle.py`：LifecycleManager 实现
  - [x] runtime state 写入 `~/.nanobot/runtime/state.json`
  - [x] PID / boot_time / boot_generation 记录
  - [x] supervisor 检测（显式 `AVA_SUPERVISOR` 优先 → Docker cgroup / systemd INVOCATION_ID 强阳性 → 默认 unsupervised）
  - [x] restart request 落盘（含 task_id / origin_session_key / reason）
  - [x] 分层优雅退出（interrupted 标记 → SIGTERM）
  - [x] orphan bg_tasks recovery（running/queued → interrupted）
  - [x] pending restart 检查与清除
  - [x] `/api/gateway/health` 端点（ready 信号）
- [x] A2. `ava/tools/gateway_control.py`：status / restart
  - [x] `restart` 限制 cli/console 上下文
  - [x] unsupervised 模式返回 unsupported
  - [x] `restart` 关联 task_id 用于闭环回写
- [x] A3. `ava/patches/tools_patch.py`：注册 `gateway_control`
- [x] A4. `ava/patches/loop_patch.py`：初始化 LifecycleManager + post-init 回填
- [x] A5. `ava/console/services/gateway_service.py`：移除 shell subprocess，走 LifecycleManager
- [x] A6. `ava/console/models.py`：GatewayStatus 新增 5 个字段
- [x] A7. `ava/console/routes/gateway_routes.py`：改为 LifecycleManager 语义 + health 端点
- [x] A8. `ava/agent/bg_tasks.py`：启动时 orphan recovery（由 LifecycleManager.initialize 调用）
- [x] A9. 删除 `ava/skills/restart_gateway/` 全目录（7 个文件）
- [x] A10. GatewayService 不再需要 skill_dir / shell subprocess

### Phase B: Frontend Hot Update

- [x] B1. `ava/console/ui_build.py`：新增 `rebuild_console_ui()` 异步封装 + `write_version_json()` + `RebuildResult` dataclass
- [x] B2. `ava/console/routes/gateway_routes.py`：新增 `POST /api/gateway/console/rebuild` 路由（admin only + audit）
- [x] B3. `console-ui/vite.config.ts`：`versionJsonPlugin()` build 后生成 `version.json`（hash + timestamp）
- [x] B4. `console-ui/src/hooks/useVersionCheck.ts`：60s 轮询 `/version.json` + `updateAvailable` 状态
- [x] B5. `console-ui/src/pages/DashboardPage.tsx`：三路操作（Rebuild UI / Restart / Force）+ lifecycle 状态面板 + 版本更新 banner
- [x] B6. `ava/console/app.py`：SPA fallback 中 `index.html` 和 `version.json` 设置 `Cache-Control: no-cache, no-store, must-revalidate`

### Phase C: Runner 独立重启

- [x] C1. `page_agent.py`：新增 `restart_runner` action + `_do_restart_runner()` 方法
- [x] C2. `page_agent_routes.py`：新增 `POST /api/page-agent/restart-runner` 端点

### Phase D: 文档与测试

- [x] D1. Tests：`test_gateway_service.py`（8 测试）+ `test_no_embedded_secrets.py`（3 测试）+ `test_ui_build.py` 扩展（5 测试）
- [x] D2. `ava/README.md` supervisor 示例统一（Docker / systemd / 本地 + `AVA_SUPERVISOR` 说明）
- [x] D3. TOOLS.md 新增 `gateway_control` 工具文档（Phase A 已完成）
- [x] D4. 标记 `restart-flow-analysis.md` deprecated（已完成）
- [x] D5. `test_no_embedded_secrets.py` secret regression test

---

## 7. Verification Protocol

### 7.1 Lifecycle 验证

```text
1. 启动：/api/gateway/status 返回 boot_generation=N, supervised=true/false
2. 请求重启：gateway_control(action="restart", reason="test")
3. 分层退出：
   3a. 前端收到 gateway_restarting WS 事件
   3b. in-flight 请求 15s drain
   3c. 后台 coding task 标记 interrupted
   3d. state.json 记录 last_exit_reason + restart_request
4. Supervisor 拉起新进程：boot_generation=N+1
5. Health check：/api/gateway/health 返回 ready=true
6. Orphan recovery：上一代 running/queued 的 bg_tasks 标记为 interrupted
7. Restart applied：原始 session 收到 restart 成功通知
```

### 7.2 Frontend 验证

```text
1. 修改前端代码 → POST /api/console/rebuild → 返回 success
2. version.json 更新 → useVersionCheck 检测到 → toast 提示
3. 用户刷新 → 加载新版本 → Gateway 进程、WS 连接、bg_tasks 未中断
```

### 7.3 Runner 验证

```text
1. page_agent(action="restart_runner") → runner 停止
2. page_agent(action="execute", ...) → runner 自动重启 → 正常执行
```

---

## 8. Risk & Mitigation

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| supervisor 检测误判（false positive） | 中 | 非 supervised 环境下允许 restart → 进程退出后无人拉起 | `restart` 返回前二次确认 supervised 状态 |
| 优雅退出超时导致 in-flight 请求丢失 | 低 | 用户 LLM 请求被中断 | 30s drain timeout + 前端 WS 自动重连 |
| 前端 version.json 被强缓存 | 低 | 版本检测失效 | `Cache-Control: no-cache` + query string timestamp |
| 旧脚本删除后本地开发环境 restart 无法工作 | 中 | 开发者需要手动重启 | unsupervised 模式返回明确提示 + README 说明 |

---

## 9. Execute Log

- [x] 2026-04-04 v1: Phase A 实装
  - **新增** `ava/runtime/__init__.py` + `ava/runtime/lifecycle.py` — LifecycleManager 完整实现
    - Runtime state 持久化到 `~/.nanobot/runtime/state.json`
    - Supervisor 检测（显式 `AVA_SUPERVISOR` 优先 → Docker cgroup / systemd INVOCATION_ID）
    - Restart request 落盘（含 task_id / origin_session_key / reason / force）
    - 分层优雅退出（停新请求 → interrupted 标记 → SIGTERM）
    - Pending restart 检查 + restart_applied
    - Orphan bg_tasks recovery
  - **新增** `ava/tools/gateway_control.py` — status / restart 工具
    - cli/console 上下文限制
    - unsupervised 拒绝
  - **修改** `ava/tools/__init__.py` — 导出 GatewayControlTool
  - **修改** `ava/patches/tools_patch.py` — 注册 gateway_control
  - **修改** `ava/patches/loop_patch.py` — 初始化 LifecycleManager + post-init 回填
  - **重写** `ava/console/services/gateway_service.py` — 移除 shell subprocess，走 LifecycleManager
  - **修改** `ava/console/models.py` — GatewayStatus 新增 supervised/supervisor/restart_pending/boot_generation/last_exit_reason
  - **修改** `ava/console/routes/gateway_routes.py` — 新增 `/api/gateway/health` 端点
  - **修改** `ava/console/app.py` — GatewayService 构造改用 lifecycle 参数
  - **修改** `ava/agent/bg_tasks.py` — TaskStatus 扩展 "interrupted" + recover_orphan_tasks() + query_history 包含 interrupted
  - **删除** `ava/skills/restart_gateway/` — 旧 skill 全目录（7 个文件）
  - **修改** `ava/templates/TOOLS.md` — 新增 gateway_control 工具文档 + Quick Map
  - **新增** `tests/runtime/test_lifecycle_manager.py` — 20 个测试
  - **新增** `tests/tools/test_gateway_control.py` — 13 个测试
  - 全量回归 1019 passed, 0 failed
- [x] 2026-04-04 v2: Phase B 实装
  - **修改** `ava/console/ui_build.py` — 新增 `rebuild_console_ui()` 异步封装 + `write_version_json()` + `RebuildResult`
  - **修改** `ava/console/routes/gateway_routes.py` — 新增 `POST /api/gateway/console/rebuild` 路由
  - **修改** `console-ui/vite.config.ts` — `versionJsonPlugin()` build 后生成 `version.json`
  - **新增** `console-ui/src/hooks/useVersionCheck.ts` — 60s 轮询版本 + updateAvailable 状态
  - **修改** `console-ui/src/pages/DashboardPage.tsx` — 三路操作 + lifecycle 面板 + 版本 banner
  - **修改** `ava/console/app.py` — SPA fallback Cache-Control: no-cache
  - **修改** `tests/console/test_ui_build.py` — 新增 5 个测试（version_json + rebuild）
  - TypeScript 编译通过，10 个 ui_build 测试全通过
- [x] 2026-04-04 v3: Phase C + D 实装
  - **修改** `ava/tools/page_agent.py` — 新增 `restart_runner` action + `_do_restart_runner()` 
  - **修改** `ava/console/routes/page_agent_routes.py` — 新增 `POST /api/page-agent/restart-runner`
  - **新增** `tests/console/test_gateway_service.py` — 8 个测试
  - **新增** `tests/security/test_no_embedded_secrets.py` — 3 个测试（Telegram token / OpenAI key / PEM）
  - **修改** `ava/README.md` — supervisor 示例 + `AVA_SUPERVISOR` 环境变量说明

---

## 10. Review Verdict

- Spec coverage: `PASS`（覆盖 lifecycle backend、frontend hot update、runner 独立重启、self-improvement loop 集成）
- Behavior check: `N/A`（当前为任务 Spec）
- Regression risk: `Low`（当前仅新增 Spec）
- Follow-ups:
  - Phase A 是 P0，Phase B 可并行
  - 删除旧 `restart_gateway` 前先确认所有引用点已替换
  - 实施严格限定在 `ava/` 内完成

---

## 11. Plan-Execution Diff

- Any deviation from plan: `None`
- 备注：
  - 本 Spec 综合了三个来源：supervisor redesign spec（方向）、restart-flow-analysis（现状分析）、Codex 锐评（self-improvement loop 视角）
  - supervisor redesign spec 的 Checklist 和 Test Coverage 已合并到本 Spec 的 §6 和 §4.5
  - restart-flow-analysis 标记为 deprecated，其中有价值的内容（前端 rebuild、page-agent 独立重启、版本检测）已在 §3.4、§3.5 中覆盖
