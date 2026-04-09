---
specanchor:
  level: task
  task_name: "sync 模式后台任务可视化（不发 Telegram）"
  author: "@Ziyan Lin"
  created: "2026-04-09"
  status: "draft"
  last_change: "已实现 v2：sync task 注册/回填、execution_mode 持久化、bg-tasks sync 标签与取消隐藏、定向测试补齐"
  related_modules:
    - ".specanchor/modules/claude_code_tool_spec.md"
  related_global:
    - ".specanchor/global/architecture.spec.md"
  related_tasks:
    - ".specanchor/tasks/ava-skills/2026-04-06_console-ui-dev-loop.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "SPEC"
  branch: "feat/0.1.1"
---

# SDD Spec: sync 模式后台任务可视化（不发 Telegram）

## 0. Open Questions

- [ ] `execution_mode` 字段是否也适用于未来的 codex sync 模式？
  - 初步倾向：是，`submit_sync_task` 已是通用接口，对所有 task_type 生效。
- [ ] 前端 TaskCard 展开时是否需要实时流式展示 sync 任务的中间输出？
  - 初步倾向：v1 不做流式。sync 任务通常几十秒内完成，完成后一次性展示 full_result 即可。如需流式，后续迭代。

## 0.1 Review Log

### v1 → v2（Codex review，2026-04-09）

采纳全部 4 项修订：

| # | 问题 | 修订 |
|---|------|------|
| P1 | `_on_complete` 会把结果写入 session.messages，sync turn 已被 AgentLoop 持久化，导致重复 assistant message 污染对话 | sync 任务的 `complete_sync_task` **不调用 `_on_complete`**，只做 DB 持久化和状态转移 |
| P1 | sync task 出现在 `/bg-tasks` 但 `cancel()` 只认 `_tasks` dict，cancel 按钮形同虚设 | 前端对 `execution_mode="sync"` 的任务**隐藏取消按钮** |
| P2 | `result.startswith("Error:")` 不匹配真实返回值（`[Claude Code ERROR]`、non-JSON output 等） | 改为在 `_execute_sync` 内部返回结构化 tuple `(parsed, formatted)`，用 `parsed.get("is_error")` 判定 |
| P2 | `silent` 字段不会自动落入 DB row / history / 前端 TaskItem | 拆为 `execution_mode` 列存储在 `bg_tasks` 表 + extra JSON，在 `_ensure_tables` 迁移、`_snapshot_from_db_row` / `query_history` / `_persist_task` / 前端 `TaskItem` 全链路覆盖 |

## 1. Requirements (Context)

### 1.1 问题

`console_ui_dev_loop` 的 Coding Round 使用 `claude_code(mode="sync")` 同步阻塞执行。当前 sync 模式**完全绕过** `BackgroundTaskStore`，导致：

1. Console UI 的后台任务页面（`/bg-tasks`）看不到 sync 任务的存在
2. 无法观察 sync 任务的输入 prompt 和输出 result
3. dev_loop 的 coding round 对用户来说是"黑盒"——只能等结果，不知道发生了什么

### 1.2 目标

让 `mode="sync"` 的 claude_code 调用也在 `BackgroundTaskStore` 中注册，使其在 Console UI 的后台任务页面可见（prompt、result、timeline、状态），但：

- **不发送 Telegram/Feishu 完成通知**（不调用 `bus.publish_outbound`）
- **不写入额外 assistant message 到 session**（避免与 AgentLoop 的正常 turn 持久化冲突）
- **不触发 auto_continue**

### 1.3 In-Scope

- 在 sync 执行前后向 `BackgroundTaskStore` 写入 task 记录（submitted → running → succeeded/failed）
- sync 任务的完成走独立的轻量路径（仅 DB + 内存状态转移，不触发 `_on_complete`）
- sync 任务在前端 bg-tasks 页面正常展示（TaskCard、Timeline、Detail）
- 前端 TaskCard 对 sync 任务隐藏取消按钮、显示 "sync" 标签
- `execution_mode` 字段全链路持久化（DB 列 + extra JSON + `_snapshot_from_db_row` + `query_history` + 前端 `TaskItem`）

### 1.4 Out-of-Scope

- 修改 `nanobot/` 目录
- sync 任务的实时流式输出（v1 不做）
- 修改 async 模式的任何行为
- sync 任务的取消支持（sync 调用在当前 turn 内阻塞，无法从外部中断）

## 2. Design

### 2.1 核心思路

在 `BackgroundTaskStore` 新增 `execution_mode` 字段（`"async"` | `"sync"`）。sync 模式调用 `submit_sync_task` 注册任务、`complete_sync_task` 回填结果。`complete_sync_task` **不走 `_on_complete`**，只做 DB 写入和内存状态迁移，避免会话污染和通知副作用。

### 2.2 数据流

```
claude_code.execute(mode="sync")
  ↓
  task_id = task_store.submit_sync_task(prompt, project_path)   # 注册，状态=running
  ↓
  parsed, formatted = await _execute_sync(prompt, project)      # 阻塞执行，返回结构化结果
  ↓
  task_store.complete_sync_task(                                 # 回填（不触发 _on_complete）
      task_id,
      status="failed" if parsed.get("is_error") else "succeeded",
      result_text=formatted,
      session_id=parsed.get("session_id", ""),
  )
  ↓
  return formatted   # 同步返回给调用方（行为不变）
```

### 2.3 BackgroundTaskStore 变更

#### 2.3.1 TaskSnapshot 新增字段

```python
@dataclass
class TaskSnapshot:
    ...
    execution_mode: str = "async"   # "async" | "sync"
```

#### 2.3.2 新增方法：`submit_sync_task`

用于 sync 模式在执行前注册任务。与 `submit_coding_task` 不同，**不创建 `asyncio.Task`**，不注册到 `_tasks` dict——调用方自行执行并回填结果。

```python
def submit_sync_task(
    self,
    *,
    origin_session_key: str,
    prompt: str,
    project_path: str,
    task_type: str = "coding",
) -> str:
    """注册一个 sync 任务，返回 task_id。调用方负责执行和回填。"""
    task_id = uuid.uuid4().hex[:12]
    now = time.time()
    snapshot = TaskSnapshot(
        task_id=task_id,
        task_type=task_type,
        origin_session_key=origin_session_key,
        status="running",
        prompt_preview=prompt[:200],
        project_path=project_path,
        started_at=now,
        timeline=[
            TimelineEvent(timestamp=now, event="submitted", detail=prompt[:100]),
            TimelineEvent(timestamp=now, event="started", detail="sync mode"),
        ],
        execution_mode="sync",
    )
    self._active[task_id] = snapshot
    self._persist_task(snapshot, full_prompt=prompt)
    self._persist_event(task_id, "submitted", prompt[:100])
    self._persist_event(task_id, "started", "sync mode")
    return task_id
```

**注意**：不写入 `self._tasks[task_id]`，因此 `cancel()` 对 sync 任务会返回 `"Task {id} not found."`，这是预期行为。

#### 2.3.3 新增方法：`complete_sync_task`

**不调用 `_on_complete`**，只做 DB 持久化和内存状态迁移。

```python
async def complete_sync_task(
    self,
    task_id: str,
    *,
    status: Literal["succeeded", "failed"],
    result_text: str = "",
    error_message: str = "",
    session_id: str = "",
) -> None:
    """回填 sync 任务结果。仅做 DB 持久化，不触发通知/会话写入/auto_continue。"""
    snapshot = self._active.get(task_id)
    if not snapshot:
        return
    now = time.time()
    snapshot.status = status
    snapshot.finished_at = now
    snapshot.elapsed_ms = int((now - (snapshot.started_at or now)) * 1000)
    snapshot.result_preview = result_text
    snapshot.error_message = error_message
    snapshot.cli_session_id = session_id

    event_name = "succeeded" if status == "succeeded" else "failed"
    self._record_event(task_id, event_name, (result_text or error_message)[:100])
    self._update_task_status(task_id, status, snapshot, full_result=result_text)

    # 内存状态迁移：active → finished
    self._finished[task_id] = self._active.pop(task_id, snapshot)
    self._prune_finished()
    # 注意：不调用 _on_complete()——
    #   1. 避免写入额外 assistant message（sync turn 已被 AgentLoop 持久化）
    #   2. 避免 bus.publish_outbound（不发 Telegram）
    #   3. 避免 auto_continue（sync 调用方自行控制后续逻辑）
```

#### 2.3.4 `_on_complete` 不变

async 模式的 `_on_complete` 逻辑完全不动。sync 任务不经过此路径。

### 2.4 ClaudeCodeTool 变更

#### 2.4.1 `_execute_sync` 返回结构化结果

当前 `_execute_sync` 返回 `str`（格式化后的文本），无法区分成功/失败。改为**内部**返回 `tuple[dict, str]`（parsed JSON + formatted text），外部接口（`execute` 的返回值）仍然是 `str`，不影响调用方。

```python
async def _execute_sync(
    self,
    prompt: str,
    project: str,
    session_id: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Execute Claude Code synchronously. Returns (parsed_json, formatted_output)."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return (
            {"is_error": True},
            "Error: claude not found in PATH. Install Claude Code CLI globally: npm install -g @anthropic-ai/claude-code",
        )

    cmd = self._build_command(prompt, project, "standard", session_id)
    stdout, stderr = await self._run_subprocess(cmd, project, self._timeout)

    if stderr and not stdout:
        return (
            {"is_error": True},
            f"Error: Claude Code failed.\n{stderr[:2000]}",
        )

    parsed = self._parse_result(stdout)
    if parsed.get("_parse_error"):
        raw = stdout[:_MAX_OUTPUT_CHARS] if stdout else "(no output)"
        return (
            {"is_error": True},
            f"Claude Code returned non-JSON output:\n{raw}",
        )

    self._record_stats(parsed, prompt)
    return (parsed, self._format_output(parsed, "sync"))
```

#### 2.4.2 `execute` sync 分支

```python
async def execute(self, prompt, project_path=None, mode="standard", session_id=None, **kwargs):
    project = self._resolve_project(project_path)
    if not Path(project).is_dir():
        return f"Error: Project directory does not exist: {project}"

    if mode == "sync":
        # 注册 sync 任务
        task_id = None
        if self._task_store:
            task_id = self._task_store.submit_sync_task(
                origin_session_key=self._session_key,
                prompt=prompt,
                project_path=project,
                task_type="claude_code",
            )

        parsed, formatted = await self._execute_sync(prompt, project, session_id)

        # 回填结果（使用 parsed.is_error 判定，而非字符串前缀匹配）
        if task_id and self._task_store:
            is_error = parsed.get("is_error", False)
            await self._task_store.complete_sync_task(
                task_id,
                status="failed" if is_error else "succeeded",
                result_text=formatted,
                error_message=formatted if is_error else "",
                session_id=parsed.get("session_id", ""),
            )

        return formatted  # 外部返回值类型不变（str）

    # ... 异步模式逻辑不变 ...
```

### 2.5 SQLite 存储变更

**在 `_ensure_tables()` 中**（`ava/agent/bg_tasks.py`，不是 `ava/storage/database.py`）新增迁移：

```python
def _ensure_tables(self) -> None:
    ...
    # 现有建表语句不变

    # 迁移：新增 execution_mode 列
    try:
        self._db.execute(
            "ALTER TABLE bg_tasks ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'async'"
        )
        self._db.commit()
    except Exception:
        pass  # 列已存在则忽略
```

#### `_persist_task` 变更

在写入 `extra` JSON 时包含 `execution_mode`：

```python
extra = {
    ...  # 现有字段
    "execution_mode": snapshot.execution_mode,
}
```

同时写入独立列：

```sql
INSERT INTO bg_tasks (..., execution_mode) VALUES (..., ?)
```

#### `_snapshot_from_db_row` 变更

```python
def _snapshot_from_db_row(self, row: Any) -> TaskSnapshot:
    ...
    extra = self._load_extra_json(self._row_val(row, "extra", "{}"))
    return TaskSnapshot(
        ...
        execution_mode=self._row_val(row, "execution_mode", None)
                        or extra.get("execution_mode", "async"),
    )
```

双重回退策略：优先读独立列，列不存在时从 extra JSON 读，都没有则默认 `"async"`。

#### `query_history` 变更

`query_history` 内部调用 `_snapshot_from_db_row`，自动获得 `execution_mode`，无需额外改动。

### 2.6 前端变更

#### `TaskItem` 类型扩展

```typescript
interface TaskItem {
  ...
  execution_mode?: 'async' | 'sync'  // 新增，可选（兼容旧数据）
}
```

#### TaskCard 标签

```tsx
{task.execution_mode === 'sync' && (
  <span className="px-1.5 py-0.5 text-[10px] rounded bg-blue-500/10 text-blue-400 font-medium">
    sync
  </span>
)}
```

#### 取消按钮：sync 任务隐藏

```tsx
{isActive && task.execution_mode !== 'sync' && (
  <button onClick={...}>取消</button>
)}
```

### 2.7 API 层

`bg_task_routes.py` 中 `get_status()` / `get_detail()` 返回的 dict 已通过 `dataclass → dict` 序列化，`execution_mode` 字段自动包含。history API 同理（经 `_snapshot_from_db_row` 重建）。**无需修改 API 路由代码。**

## 3. Risks & Mitigations

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| sync 执行期间进程崩溃，task 卡在 running | 前端显示僵尸任务 | `recover_orphan_tasks` 已在启动时将 running/queued 标记为 interrupted，sync 任务同样受益 |
| `_execute_sync` 返回值从 `str` 改为 `tuple`，破坏现有调用点 | 编译/运行错误 | `_execute_sync` 是私有方法，唯一调用点是 `execute()` 的 sync 分支，改动同步进行 |
| `execution_mode` 列在旧版 DB 不存在 | 查询报错 | `ALTER TABLE ... ADD COLUMN ... DEFAULT 'async'` + `except pass` 安全迁移；`_snapshot_from_db_row` 双重回退 |
| sync 任务结果可能很大 | 数据库膨胀 | 复用现有 `_format_output` 中的 `_MAX_OUTPUT_CHARS` 截断策略 |

## 4. Implementation Checklist

### Phase 1: 后端核心（`ava/agent/bg_tasks.py`）

- [x] `TaskSnapshot` 添加 `execution_mode: str = "async"`
- [x] `_ensure_tables()` 新增 `execution_mode` 列迁移
- [x] `_persist_task()` 写入 `execution_mode`（独立列 + extra JSON）
- [x] `_snapshot_from_db_row()` 读取 `execution_mode`（列优先，回退 extra JSON）
- [x] 新增 `submit_sync_task()` 方法
- [x] 新增 `complete_sync_task()` 方法（不调用 `_on_complete`）

### Phase 2: 工具集成（`ava/tools/claude_code.py`）

- [x] `_execute_sync()` 返回值改为 `tuple[dict, str]`
- [x] `execute()` sync 分支：调用 `submit_sync_task` + `complete_sync_task`，用 `parsed.get("is_error")` 判定状态

### Phase 3: 前端（`console-ui/src/pages/BgTasksPage.tsx`）

- [x] `TaskItem` 接口新增 `execution_mode?: 'async' | 'sync'`
- [x] TaskCard 对 `execution_mode="sync"` 显示 "sync" 标签
- [x] TaskCard 对 `execution_mode="sync"` 隐藏取消按钮

### Phase 4: 测试（`tests/agent/test_bg_tasks.py`）

- [x] 测试 `submit_sync_task` + `complete_sync_task` 生命周期
- [x] 测试 `complete_sync_task` 不触发 bus 通知、不写入 session message、不触发 auto_continue
- [x] 测试 sync task 在 `get_status()` 中正常出现且 `execution_mode="sync"`
- [x] 测试 `cancel()` 对 sync task 返回 not found（预期行为）
- [x] 测试 DB 重载后 `execution_mode` 正确恢复
