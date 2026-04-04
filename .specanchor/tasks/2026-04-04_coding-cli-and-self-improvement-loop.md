---
specanchor:
  level: task
  task_name: "后台任务上下文架构与编程 CLI 闭环"
  author: "@fanghu"
  created: "2026-04-04"
  status: "draft"
  last_change: "v3.1: Phase 1 已实装（BackgroundTaskStore + session_key 路由修复 + context digest + 命令注册到 CommandRouter）；Telegram 命令注册降级为 Phase 2"
  related_modules:
    - ".specanchor/modules/claude_code_tool_spec.md"
    - ".specanchor/modules/tools_patch_spec.md"
    - ".specanchor/modules/loop_patch_spec.md"
    - ".specanchor/modules/bus_console_listener_spec.md"
    - ".specanchor/modules/context_patch_spec.md"
  related_global:
    - ".specanchor/global-patch-spec.md"
  flow_type: "standard"
  writing_protocol: "sdd-riper-one"
  sdd_phase: "EXECUTE"
  branch: "refactor/sidecar"
---

# SDD Spec: 后台任务上下文架构与编程 CLI 闭环

## 0. Open Questions

- [x] `claude_code` 的异步任务应通过什么模式管理？
  → **v2 决策**：独立 `CodingTaskRegistry`（不 patch SubagentManager）
  → **v3 修正**：提升为 `BackgroundTaskStore`，统一收口 coding/cron/subagent
- [x] 完成回调应走什么链路？
  → **v3 决策**：结果必须先落盘到 origin session history，再通过 async_result 通知前端 reload。不落盘就 reload 是空操作（v2 遗漏）
- [x] `/status` / `/cc_status` 字段哪些必须在 Phase 1？
  → **v3 修正**：粗粒度 timeline（start/end/result_digest）+ active task digest 进入 Phase 1 核心验收；streaming 实时字段（phase/todo/last_tool）仍在 Phase 2.5
- [x] session_key 路由怎么修？
  → **v3 新增**：`_set_tool_context` 传 channel+chat_id 无法还原 console 的真实 session_key（`console:{session_id}` ≠ `console:{user_id}`）。修复方式：loop_patch 存 `_current_session_key`，通过 `set_context` 直接传给工具
- [ ] BackgroundTaskStore 的持久层用现有 nanobot.db 还是独立 db 文件？
  → 倾向使用现有 nanobot.db，新增两张表

---

## 1. Requirements (Context)

- **Goal**:
  1. 建立统一的后台任务上下文层（BackgroundTaskStore），让 Nanobot 在普通 IM 对话中知道有哪些旁路任务在跑、跑完了什么
  2. 基于此层，补齐 `claude_code` 的异步闭环（Phase 1 唯一实装的任务类型）
  3. 在不碰 `nanobot/` 的前提下，为 cron/subagent 上下文注入、编程 CLI 通用化、自改进闭环留好扩展接口

- **In-Scope**:
  - 修正 session_key 路由 bug（console 场景）
  - BackgroundTaskStore：任务注册、状态机、粗粒度 timeline、持久化、active task digest
  - context_patch 注入 active task digest 到 IM 对话
  - `claude_code` async 分支接入 BackgroundTaskStore
  - 完成回调：结果落盘到 origin session + async_result 通知
  - 通用生命周期命令（/task, /task_cancel, /cc_status 降为别名）
  - `/stop` 覆盖 coding_tasks

- **Out-of-Scope**:
  - Phase 1 直接实装 cron/subagent 事件源（留好接口即可）
  - 直接实现 CodexCLI
  - 自改进 Skill / 自动 commit 流水线
  - 修改 `nanobot/` 上游文件作为 sidecar 常规实现路径
  - Streaming 实时字段（phase/todo/last_tool）

---

## 2. Research Findings

### 2.1 — 2.7 见前版（v1/v2）调研，结论不变

核心事实：`claude_code` 只有 sync 链可用，async 链断头；`/status`/`/cc_status` 消费端无生产端。

### 2.8 session_key 路由 bug（v3 新增）

Console 调用链：

```text
chat_service.send_message(session_id, message, user_id)
  → process_direct(session_key="console:{session_id}", channel="console", chat_id=user_id)
  → _process_message(...)
    → key = session_key  // 正确: "console:{session_id}"
    → _set_tool_context(msg.channel, msg.chat_id, ...)
      // 传入: channel="console", chat_id=user_id
      → ClaudeCodeTool.set_context("console", user_id)
        → self._session_key = "console:{user_id}"  // 错误！
```

**根因**：`_set_tool_context(channel, chat_id)` 的 API 签名不包含 session_key。对 Telegram 等通道没问题（session_key == `channel:chat_id`），但 console 的 session_key 是 `console:{session_id}`，而 `chat_id` 是 `user_id`。

**影响范围**：所有需要 session_key 的 sidecar 工具（当前是 claude_code、send_sticker），在 console 场景下都会路由到错误的 session。

**修复方式**：
1. `loop_patch` 在 `_process_message` 入口存 `self._current_session_key = key`
2. `patched_set_tool_context` 改为同时传 `self._current_session_key` 给工具
3. `ClaudeCodeTool.set_context` 接受 `session_key` 参数，直接使用而不再从 channel/chat_id 反推

### 2.9 async_result 链没闭环（v3 新增）

前端 `ChatPage` 收到 `async_result` 后：

```typescript
// console-ui/src/pages/ChatPage/index.tsx:75-76
} else if (data.type === 'async_result') {
    loadSessionMessagesRef.current(sessionKey)  // 只是 reload
}
```

`loadSessionMessages` 从 DB/JSONL 重新拉消息。但如果后台任务完成后没有把结果写进 session history，reload 返回的消息列表跟之前一模一样。

**结论**：`publish_outbound → async_result → reload` 链需要在 outbound 之前先把结果落盘到 origin session。

### 2.10 普通对话没有任何后台任务上下文（v3 新增）

`context_patch.build_messages` 当前注入步骤：

1. HistorySummarizer → 2. HistoryCompressor → 3. 原始 build_messages → 4. 注入分类记忆

没有第 5 步"注入后台任务 digest"。所以用户在 IM 里说"刚才那个编程任务怎样了"，模型完全不知道有什么任务在跑。

Cron 更彻底：跑在独立 `cron:{job.id}` session 里（`nanobot/cli/commands.py:669`），普通对话的 session history 里连一个 pointer 都没有。

### 2.11 `/stop` 不覆盖 coding_tasks（v3 新增）

`_cmd_stop`（`commands.py:184-194`）只取消：
- `_agent._active_tasks[session_key]` 里的 turn-level tasks
- `_agent.subagents.cancel_by_session(session_key)` 里的 subagent

如果 coding 任务改挂到 BackgroundTaskStore，`/stop` 需要同步覆盖。

---

## 3. Innovate: 架构方案

### v1/v2 方案的系统性缺陷（v3 批判）

v2 的 `CodingTaskRegistry` 方案（已优于 v1 的 subagent_patch）仍有以下问题：

1. **视野局限**：只解决了 claude_code 异步启停，没解决"IM 对话中感知不到旁路任务"这个根本问题。Cron、subagent 的上下文同样断裂。
2. **session_key 路由 bug 未发现**：v2 把 `_set_tool_context` 通用化当成修复，但 console 场景下 channel/chat_id 根本无法还原正确的 session_key。
3. **async_result 链没验证闭环**：假设 `publish_outbound → reload` 就够了，实际上结果没落盘，reload 是空操作。
4. **"通知"和"上下文注入"混为一谈**：把异步完成消息推到 IM 对话流 ≠ 模型能在后续 turn 中引用任务结果。前者是 UI 事件，后者需要进入 build_messages。
5. **Phase 1 验收标准过低**：只把"任务能启动"补上。用户问"做到哪了"时 Nanobot 还是答不出来。

### Option C（废弃）：CodingTaskRegistry 模式

见 v2 描述。因上述五个系统性缺陷而废弃。

### Option D（新增）：BackgroundTaskStore + 上下文注入层

**核心思路**：不只做 claude_code async wiring，而是建立统一的后台任务上下文架构。

**架构**：

```text
事件源（写入）                         消费端（读取）
┌──────────────┐                    ┌──────────────────────────┐
│ CodingTask   │─── record_event ──→│                          │
│ (Phase 1)    │                    │   BackgroundTaskStore    │
├──────────────┤                    │ (ava/agent/bg_tasks.py)  │
│ CronObserver │─── record_event ──→│                          │
│ (Phase 2)    │                    │  - _active: dict         │
├──────────────┤                    │  - SQLite 持久层          │
│ SubagentObs  │─── record_event ──→│  - timeline events       │
│ (Phase 2)    │                    │  - result digests         │
└──────────────┘                    └─────┬───────┬────────────┘
                                          │       │
                              ┌───────────┘       └──────────┐
                              ▼                              ▼
                    ┌──────────────────┐          ┌────────────────┐
                    │  context_patch   │          │   commands.py  │
                    │  build_messages  │          │                │
                    │  + task digest   │          │ /task /task_cancel │
                    │  注入到 system   │          │ /cc_status (别名) │
                    │  prompt          │          │ /stop (覆盖)     │
                    └──────────────────┘          └────────────────┘

完成回调链：
  Task 完成
    → store.complete_task(task_id, result)
    → 1. 写结果到 origin session history（落盘，必须先于通知）
    → 2. bus.publish_outbound(session_key=origin_session_key)
    → 3. async_result → ChatPage reload → 能看到新消息

session_key 修复：
  loop_patch._process_message 入口:
    self._current_session_key = key  // 存正确的 session_key
  patched_set_tool_context:
    tool.set_context(channel, chat_id, session_key=self._current_session_key)
```

**"写多读一"模式**：各事件源只负责向 store 写入事件（started/succeeded/failed/cancelled）；store 统一提供查询、digest、timeline 接口。Phase 1 只实装 coding 事件源，但 store 的读接口从第一天起就是通用的。

**与 v2 CodingTaskRegistry 的对比**：

| 维度 | v2 CodingTaskRegistry | v3 BackgroundTaskStore |
|------|----------------------|------------------------|
| 覆盖范围 | 只管 coding | coding + cron + subagent（渐进接入） |
| session_key | 从 channel/chat_id 反推（console 场景错） | origin_session_key 一等字段，直传不反推 |
| 结果落盘 | 不落盘，靠 reload（空操作） | 先写 session history 再通知 |
| IM 上下文 | 无 | context_patch 注入 active task digest |
| 持久化 | 纯内存 | SQLite（重启不丢历史） |
| 命令 | /cc_status 专用 | /task 通用 + /cc_status 别名 |
| /stop | 漏掉 | 覆盖 |
| Phase 1 验收 | "任务能启动" | "用户在 IM 里能感知到任务状态、能看到完成结果" |

**Phase 1 验收标准**（不是 Phase 2.5 可选）：

1. 用户触发 `claude_code(mode="standard")` → 后台启动，IM 回复 task_id
2. 用户发任意消息 → system prompt 包含 active task digest
3. 用户问"那个任务怎样了" → 模型能从 digest 引用任务状态回答
4. 任务完成 → 结果写入 origin session → async_result → ChatPage 显示新消息
5. Console UI `/task` 或 `/cc_status` 返回任务列表和粗粒度 timeline
6. Console UI `/stop` 能取消运行中的 coding 任务
7. Gateway 重启后，历史任务可查（SQLite 持久化）

> **降级说明**：Telegram 的 `/task` 等命令因上游 `~filters.COMMAND` 排除机制暂不可用。
> 上游用 `CommandHandler` 白名单处理命令，未注册的命令被 `~filters.COMMAND` 过滤器
> 吞掉。已在 `channel_patch.py` 中尝试动态注入但未生效（可能是 handler 添加时序问题）。
> 降级为 Phase 2 处理：修改上游 Telegram handler 或用 `MessageHandler` catch-all 替代。
> Console UI + context_patch digest 已验证可用。

### Decision

- **Selected**：Option D（BackgroundTaskStore + 上下文注入层）
- **Why**：
  1. 解决了 v2 遗留的 session_key 路由 bug、async_result 空 reload、IM 上下文断裂三个核心问题
  2. "写多读一"模式让 Phase 1 只需实装 coding 事件源，cron/subagent 的接入是纯增量
  3. 验收标准从"任务能启动"提升到"用户能在 IM 里感知任务"，真正满足核心诉求
  4. 变更面可控：核心新增 `bg_tasks.py`（store）+ 修改 loop_patch（session_key）+ context_patch（digest）+ commands（通用命令）
  5. origin_session_key 一等化从根本上解决了 console/Telegram/CLI 的路由统一

### Skip

- Skipped: false
- Reason: v3 是对 v2 的系统性修正，不是增量补丁。session_key 路由 bug 和 async_result 空 reload 是实装前必须解决的阻塞问题。

---

## 4. Plan (Contract)

### 4.0 前置修复（独立提交，阻塞 Phase 1）

| 文件 | 变更 |
|------|------|
| `ava/patches/loop_patch.py` | **修改**：1) `patched_init` 初始化 `self._current_session_key = "cli:direct"`；2) `_process_message` 入口存 `self._current_session_key = key`；3) `patched_set_tool_context` 遍历所有工具，传 `session_key=self._current_session_key` |

### 4.1 Phase 1 File Changes

| 文件 | 变更 |
|------|------|
| `ava/agent/bg_tasks.py` | **新建**：`BackgroundTaskStore`（任务注册/状态机/timeline/SQLite 持久层/active digest/结果落盘）+ `TaskSnapshot` + `TimelineEvent` 数据模型 |
| `ava/tools/claude_code.py` | **修改**：1) async 分支从调 `spawn_claude_code(...)` 改成调 `self._task_store.submit_coding_task(...)`；2) `set_context` 接受 `session_key` 参数；3) `cancel()` 改调 store；4) 新增 `_execute_background()` |
| `ava/patches/loop_patch.py` | **修改**：1) `patched_init` 创建 `BackgroundTaskStore` 实例挂到 `self.bg_tasks`；2) 完成回调中写结果到 session history |
| `ava/patches/tools_patch.py` | **修改**：`ClaudeCodeTool` 构造参数从 `subagent_manager=` 改成 `task_store=` |
| `ava/patches/context_patch.py` | **修改**：`patched_build_messages` 新增第 5 步：读 `self._agent_loop.bg_tasks.get_active_digest(session_key)` 注入 system prompt |
| `ava/agent/commands.py` | **修改**：1) `/status` 消费端从 `_agent.subagents.get_claude_code_status(...)` 切到 `_agent.bg_tasks.get_summary(...)`；2) `/cc_status` 降为 `/task` 别名；3) 新增 `/task` `/task_cancel` 通用命令；4) `/stop` 覆盖 `_agent.bg_tasks.cancel_by_session(...)` |
| `tests/agent/test_bg_tasks.py` | **新建**：store submit/cancel/status/timeline/digest/持久化/并发安全测试 |
| `tests/tools/test_claude_code.py` | **新建**：同步链 / async fallback / session_key 路由 / 结果落盘测试 |

### 4.1.1 Phase 2（Phase 1 稳定后）

| 文件 | 变更 |
|------|------|
| `ava/tools/coding_cli_base.py` | **新建**：抽取共享进程管理 / 截断 / 状态发布基类 |
| `ava/tools/codex_cli.py` | **新建**：Codex CLI 后端，实现 executor 接口 |
| `ava/agent/bg_tasks.py` | **修改**：新增 cron observer / subagent observer 事件源 |
| `ava/patches/tools_patch.py` | **修改**：注册 `codex_cli` |
| `ava/forks/config/schema.py` | **修改**：新增 `CodexConfig` |

### 4.1.2 Phase 2.5（可选：streaming 增强）

| 文件 | 变更 |
|------|------|
| `ava/tools/claude_code.py` | **修改**：`_run_subprocess` 改成 streaming 读取 |
| `ava/agent/bg_tasks.py` | **修改**：snapshot 支持实时更新 phase/todo/last_tool |

### 4.2 Signatures

```python
# ava/agent/bg_tasks.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal
import time

@dataclass
class TimelineEvent:
    timestamp: float
    event: str          # "submitted" | "started" | "succeeded" | "failed" | "cancelled"
    detail: str = ""    # 粗粒度描述

@dataclass
class TaskSnapshot:
    task_id: str
    task_type: str                     # "coding" | "cron" | "subagent"
    origin_session_key: str            # 一等字段，触发时直传，不从 channel/chat_id 反推
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    prompt_preview: str
    started_at: float | None = None
    finished_at: float | None = None
    elapsed_ms: int = 0
    result_preview: str = ""
    error_message: str = ""
    timeline: list[TimelineEvent] = field(default_factory=list)
    # Phase 2.5 streaming 字段
    phase: str = "executing"
    last_tool_name: str = ""
    todo_summary: dict[str, int] | None = None
    # 扩展字段（coding 专用）
    project_path: str = ""
    cli_session_id: str = ""

CodingExecutor = Callable[..., Awaitable[dict[str, Any]]]

class BackgroundTaskStore:
    def __init__(self, db=None) -> None:
        """db: ava.storage.Database 实例，用于持久化 timeline 和 task history。"""
        ...

    def submit_coding_task(
        self,
        executor: CodingExecutor,
        *,
        origin_session_key: str,
        prompt: str,
        project_path: str,
        timeout: int,
        **executor_kwargs: Any,
    ) -> str:
        """提交编程后台任务，返回 task_id。"""
        ...

    def record_event(
        self,
        task_id: str,
        event: str,
        detail: str = "",
    ) -> None:
        """记录 timeline 事件（通用接口，供 cron/subagent observer 使用）。"""
        ...

    async def cancel(self, task_id: str) -> str: ...

    async def cancel_by_session(self, session_key: str) -> int:
        """取消某 session 下所有运行中的后台任务。返回取消数量。"""
        ...

    def get_status(
        self,
        task_id: str | None = None,
        session_key: str | None = None,
        task_type: str | None = None,
        include_finished: bool = True,
    ) -> dict[str, Any]:
        """返回 {"running": int, "total": int, "tasks": list[dict]}。"""
        ...

    def get_active_digest(self, session_key: str | None = None) -> str:
        """返回适合注入 system prompt 的极短任务摘要。
        格式示例:
          ## Active Background Tasks
          - [coding:abc123] running 45s — "Fix bug in auth module..."
          - [cron:daily-report] succeeded 2m ago — "Daily report generated"
        无活跃任务时返回空字符串（不注入）。
        """
        ...

    def get_timeline(self, task_id: str) -> list[TimelineEvent]:
        """返回某任务的 timeline 事件列表。"""
        ...

    async def _on_complete(self, snapshot: TaskSnapshot, agent_loop) -> None:
        """完成回调：
        1. 写结果到 origin session history（必须先于通知）
        2. publish_outbound → async_result → ChatPage reload
        """
        ...
```

```python
# ava/tools/claude_code.py 改动要点
class ClaudeCodeTool(Tool):
    def __init__(self, ..., task_store: BackgroundTaskStore | None = None) -> None:
        self._task_store = task_store
        ...

    def set_context(self, channel: str, chat_id: str, *, session_key: str | None = None) -> None:
        self._channel = channel
        self._chat_id = chat_id
        # 优先使用直传的 session_key，不再从 channel/chat_id 反推
        self._session_key = session_key or f"{channel}:{chat_id}"

    async def execute(self, prompt, project_path, mode, session_id, **kwargs):
        ...
        if mode == "sync":
            return await self._execute_sync(prompt, project, session_id)
        if not self._task_store:
            return await self._execute_sync(prompt, project, session_id)
        task_id = self._task_store.submit_coding_task(
            executor=self._execute_background,
            origin_session_key=self._session_key,
            prompt=prompt,
            project_path=project,
            timeout=120 if mode == "fast" else self._timeout,
            mode=mode,
            session_id=session_id,
        )
        return f"Claude Code task started (id: {task_id}). Use /task to check progress."
```

```python
# ava/patches/loop_patch.py 改动要点
def patched_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    ...
    self._current_session_key = "cli:direct"
    self.bg_tasks = BackgroundTaskStore(db=db)

def patched_set_tool_context(self, channel, chat_id, message_id=None):
    original_set_tool_context(self, channel, chat_id, message_id)
    session_key = getattr(self, "_current_session_key", f"{channel}:{chat_id}")
    for tool_name in self.tools.tool_names:
        tool = self.tools.get(tool_name)
        if tool and hasattr(tool, "set_context"):
            try:
                tool.set_context(channel, chat_id, session_key=session_key)
            except TypeError:
                tool.set_context(channel, chat_id)  # 旧签名兼容

# 在 _process_message wrapper 中：
def patched_process_message(self, msg, ...):
    key = ...  # 与上游一致
    self._current_session_key = key  # 存正确的 session_key
    return await original_process_message(self, msg, ...)
```

```python
# ava/patches/context_patch.py 改动要点
def patched_build_messages(self, history, current_message, **kwargs):
    ...
    # 4. 注入分类记忆（现有）
    ...
    # 5. 注入后台任务 digest（新增）
    loop = getattr(self, "_agent_loop", None)
    if loop and hasattr(loop, "bg_tasks"):
        session_key = getattr(loop, "_current_session_key", None)
        digest = loop.bg_tasks.get_active_digest(session_key)
        if digest and messages and messages[0]["role"] == "system":
            messages[0]["content"] += f"\n\n{digest}"
    ...
```

### 4.3 SQLite Schema（新增两张表）

```sql
CREATE TABLE IF NOT EXISTS bg_tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    origin_session_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    prompt_preview TEXT,
    project_path TEXT,
    started_at REAL,
    finished_at REAL,
    result_preview TEXT,
    error_message TEXT,
    extra TEXT  -- JSON, 存 cli_session_id 等扩展字段
);

CREATE TABLE IF NOT EXISTS bg_task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES bg_tasks(task_id),
    event TEXT NOT NULL,
    detail TEXT,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bg_tasks_session ON bg_tasks(origin_session_key);
CREATE INDEX IF NOT EXISTS idx_bg_task_events_task ON bg_task_events(task_id);
```

### 4.4 Implementation Checklist

#### 前置修复 ✅
- [x] 0a. `loop_patch`：`_current_session_key` 已在 `patched_process_message` 中设置
- [x] 0b. `loop_patch`：`patched_set_tool_context` 通用化，遍历所有工具 + 传 session_key
- [x] 0c. `ClaudeCodeTool.set_context` 接受 session_key 参数

#### Phase 1 ✅（Telegram 命令降级为 Phase 2）
- [x] 1. `BackgroundTaskStore` + `TaskSnapshot` + `TimelineEvent`（`ava/agent/bg_tasks.py`）
- [x] 2. SQLite 持久层：bg_tasks + bg_task_events 两张表
- [x] 3. `claude_code.py` async 分支改用 `self._task_store.submit_coding_task(...)`
- [x] 4. `loop_patch` 创建 `BackgroundTaskStore` 实例，挂到 `self.bg_tasks`
- [x] 5. `tools_patch` 把 `task_store` 传给 `ClaudeCodeTool`
- [x] 6. 完成回调：结果写入 origin session history + publish_outbound
- [x] 7. `context_patch` 注入 active task digest（build_messages 第 5 步）
- [x] 8. 命令注册到上游 `CommandRouter`：`/task` `/task_cancel` `/cc_status` `/stop`
- [x] 9. 测试：14 个 + 全量回归 974 passed
- [ ] 8b. Telegram CommandHandler 动态注入（降级到 Phase 2）

#### Phase 2：通用编程 CLI + cron/subagent 接入 + Telegram 命令
- [ ] 10. 抽取 `CodingCLIBase`
- [ ] 11. 新增 `CodexCLI` 后端
- [ ] 12. BackgroundTaskStore 新增 cron observer / subagent observer
- [ ] 13. 更新 `tools_patch` / schema / Module Spec
- [ ] 14. Telegram 命令注册（修改上游 handler 或用 catch-all 替代 ~filters.COMMAND）

#### Phase 2.5（可选）：streaming 增强
- [ ] 15. `_run_subprocess` 改成 streaming 读取
- [ ] 16. snapshot 实时更新 phase/todo/last_tool

#### Phase 3：自改进编排
- [ ] 17. 重新评估 self-improvement loop
- [ ] 18. 若进入实现，补 Skill / verify script / git 闭环

---

## 5. Execute Log

- [x] 2026-04-04 v1: 初始代码调研，确认 sync 链可用、async 链断头
- [x] 2026-04-04 v2: 批判 Option A（subagent_patch），提出 Option C（CodingTaskRegistry）
- [x] 2026-04-04 v3: 接收 Codex 批评，确认 session_key 路由 bug + async_result 空 reload + IM 上下文断裂三个核心问题；从 CodingTaskRegistry 提升为 BackgroundTaskStore；timeline/digest 前移到 Phase 1；拆分通知与上下文注入
- [x] 2026-04-04 v3.1: Phase 1 实装
  - `ava/agent/bg_tasks.py` — BackgroundTaskStore 完整实现
  - `ava/patches/loop_patch.py` — session_key 路由修复 + store 初始化 + 命令注册到 CommandRouter
  - `ava/tools/claude_code.py` — async 分支接入 store + `_execute_background()`
  - `ava/patches/tools_patch.py` — task_store 传入 ClaudeCodeTool
  - `ava/patches/context_patch.py` — digest 注入 system prompt
  - `ava/patches/channel_patch.py` — Telegram CommandHandler 动态注入（部分生效）
  - `tests/agent/test_bg_tasks.py` — 14 个测试通过
  - 全量回归 974 passed, 0 failed
  - 降级：Telegram 命令注册因上游 ~filters.COMMAND 限制暂不可用，降级到 Phase 2
- [x] 2026-04-04 v3.2: Console UI 后台任务可视化页面
  - `ava/console/routes/bg_task_routes.py` — REST + WebSocket API 端点
  - `console-ui/src/pages/BgTasksPage.tsx` — 任务状态卡片 + Timeline 展开 + 实时刷新
  - `console-ui/src/App.tsx` — `/bg-tasks` 路由注册
  - `console-ui/src/components/layout/navItems.ts` — 侧边栏"后台任务"入口
  - `ava/console/app.py` — 两处 include_router 注册
  - `ava/console/routes/__init__.py` — 导出 bg_task_routes
  - TypeScript 编译零错误
- [ ] Phase 2 尚未执行
- [ ] Phase 3 尚未执行

---

## 6. Review Verdict

- Spec coverage: PASS（覆盖 session_key 路由、async_result 落盘、IM 上下文注入、生命周期命令）
- Behavior check: PASS（针对"架构设计"目标）
- Regression risk: Low（本次只改 `.specanchor/` 文档）
- Module Spec 需更新: Yes → `claude_code_tool_spec.md` + `context_patch_spec.md` 需同步
- Open Questions 收敛: 4/5 已决策（持久层选型倾向已定但保留灵活性）
- Follow-ups:
  - 前置修复 session_key 可独立提交和测试
  - Phase 1 验收标准是"用户在 IM 里能感知到任务状态、能看到完成结果"，不是"任务能启动"
  - `/task_timeline` 命令可在 Phase 1 后期补，不阻塞核心闭环

---

## 7. Plan-Execution Diff

- v1（2026-04-04）：完成"研究 + 计划"工件
- v2（2026-04-04）：Option A → Option C（CodingTaskRegistry），废弃 subagent_patch
- v3（2026-04-04）：Option C → Option D（BackgroundTaskStore）。核心修正：
  - 发现并修正 session_key 路由 bug
  - async_result 落盘前置于通知
  - 任务上下文从"无"到"context_patch digest 注入"
  - 粗粒度 timeline + 持久化从 Phase 2.5 可选提升为 Phase 1 核心验收
  - 生命周期命令通用化（/task），/cc_status 降为别名
  - /stop 覆盖 bg_tasks
- v3.1（2026-04-04）：Phase 1 实装完成。额外发现：
  - ava 的 `CommandRegistry`（commands.py）与上游 `CommandRouter` 是两套独立系统，命令需注册到上游 CommandRouter
  - Telegram 上游 `~filters.COMMAND` 过滤器会吞掉未注册 CommandHandler 的 / 命令，动态注入尝试未生效，降级到 Phase 2
