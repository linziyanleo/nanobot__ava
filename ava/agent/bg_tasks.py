"""统一后台任务上下文层。

采用"写多读一"模式：各事件源（coding/cron/subagent）向 store 写入事件，
store 统一提供查询、digest、timeline 接口。

Phase 1 只实装 coding 事件源，但读接口从第一天起就是通用的。
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Literal

from loguru import logger

if TYPE_CHECKING:
    from nanobot.agent.loop import AgentLoop

TaskStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


@dataclass
class TimelineEvent:
    timestamp: float
    event: str
    detail: str = ""


@dataclass
class TaskSnapshot:
    task_id: str
    task_type: str
    origin_session_key: str
    status: TaskStatus
    prompt_preview: str
    started_at: float | None = None
    finished_at: float | None = None
    elapsed_ms: int = 0
    result_preview: str = ""
    error_message: str = ""
    timeline: list[TimelineEvent] = field(default_factory=list)
    phase: str = "executing"
    last_tool_name: str = ""
    todo_summary: dict[str, int] | None = None
    project_path: str = ""
    cli_session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timeline"] = [asdict(e) for e in self.timeline]
        return d


CodingExecutor = Callable[..., Awaitable[dict[str, Any]]]


class BackgroundTaskStore:
    """统一后台任务注册/状态机/timeline/持久化/digest。"""

    def __init__(self, db: Any | None = None) -> None:
        self._db = db
        self._active: dict[str, TaskSnapshot] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._finished: dict[str, TaskSnapshot] = {}
        self._agent_loop: AgentLoop | None = None
        self._ensure_tables()

    def set_agent_loop(self, loop: AgentLoop) -> None:
        self._agent_loop = loop

    def _ensure_tables(self) -> None:
        if not self._db:
            return
        try:
            self._db.execute("""
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
                    extra TEXT
                )
            """)
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS bg_task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    detail TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_bg_tasks_session "
                "ON bg_tasks(origin_session_key)"
            )
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_bg_task_events_task "
                "ON bg_task_events(task_id)"
            )
            self._db.commit()
        except Exception as exc:
            logger.warning("BackgroundTaskStore: failed to create tables: {}", exc)

    # ------------------------------------------------------------------
    # 写入接口
    # ------------------------------------------------------------------

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
        task_id = uuid.uuid4().hex[:12]
        now = time.time()
        snapshot = TaskSnapshot(
            task_id=task_id,
            task_type="coding",
            origin_session_key=origin_session_key,
            status="queued",
            prompt_preview=prompt[:200],
            project_path=project_path,
            started_at=now,
            timeline=[TimelineEvent(timestamp=now, event="submitted", detail=prompt[:100])],
        )
        self._active[task_id] = snapshot
        self._persist_task(snapshot)
        self._persist_event(task_id, "submitted", prompt[:100])

        async def _run() -> None:
            snapshot.status = "running"
            snapshot.started_at = time.time()
            self._record_event(task_id, "started")
            self._update_task_status(task_id, "running")
            try:
                result = await asyncio.wait_for(
                    executor(prompt=prompt, **executor_kwargs),
                    timeout=timeout,
                )
                snapshot.status = "succeeded"
                snapshot.finished_at = time.time()
                snapshot.elapsed_ms = int((snapshot.finished_at - snapshot.started_at) * 1000)
                snapshot.result_preview = str(result.get("result", ""))[:500]
                snapshot.cli_session_id = result.get("session_id", "")
                self._record_event(task_id, "succeeded", snapshot.result_preview[:100])
                self._update_task_status(task_id, "succeeded", snapshot)
                await self._on_complete(snapshot, result)
            except asyncio.TimeoutError:
                snapshot.status = "failed"
                snapshot.finished_at = time.time()
                snapshot.elapsed_ms = int((snapshot.finished_at - snapshot.started_at) * 1000)
                snapshot.error_message = f"Timed out after {timeout}s"
                self._record_event(task_id, "failed", snapshot.error_message)
                self._update_task_status(task_id, "failed", snapshot)
                await self._on_complete(snapshot, None)
            except asyncio.CancelledError:
                snapshot.status = "cancelled"
                snapshot.finished_at = time.time()
                snapshot.elapsed_ms = int((snapshot.finished_at - (snapshot.started_at or snapshot.finished_at)) * 1000)
                self._record_event(task_id, "cancelled")
                self._update_task_status(task_id, "cancelled", snapshot)
            except Exception as exc:
                snapshot.status = "failed"
                snapshot.finished_at = time.time()
                snapshot.elapsed_ms = int((snapshot.finished_at - snapshot.started_at) * 1000)
                snapshot.error_message = str(exc)[:500]
                self._record_event(task_id, "failed", snapshot.error_message[:100])
                self._update_task_status(task_id, "failed", snapshot)
                await self._on_complete(snapshot, None)
            finally:
                self._finished[task_id] = self._active.pop(task_id, snapshot)
                self._tasks.pop(task_id, None)

        task = asyncio.create_task(_run())
        self._tasks[task_id] = task
        return task_id

    def record_event(
        self, task_id: str, event: str, detail: str = "",
    ) -> None:
        """通用事件记录接口（供 cron/subagent observer 使用）。"""
        self._record_event(task_id, event, detail)

    def _record_event(self, task_id: str, event: str, detail: str = "") -> None:
        now = time.time()
        if task_id in self._active:
            self._active[task_id].timeline.append(
                TimelineEvent(timestamp=now, event=event, detail=detail)
            )
        self._persist_event(task_id, event, detail)

    # ------------------------------------------------------------------
    # 读取接口
    # ------------------------------------------------------------------

    async def cancel(self, task_id: str) -> str:
        if task_id in self._tasks:
            task = self._tasks[task_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
                return f"Task {task_id} cancelled."
            return f"Task {task_id} already finished."
        if task_id in self._finished:
            return f"Task {task_id} already finished."
        return f"Task {task_id} not found."

    async def cancel_by_session(self, session_key: str) -> int:
        cancelled = 0
        task_ids = [
            tid for tid, snap in self._active.items()
            if snap.origin_session_key == session_key
        ]
        for tid in task_ids:
            result = await self.cancel(tid)
            if "cancelled" in result.lower():
                cancelled += 1
        return cancelled

    def get_status(
        self,
        task_id: str | None = None,
        session_key: str | None = None,
        task_type: str | None = None,
        include_finished: bool = True,
        verbose: bool = False,
    ) -> dict[str, Any]:
        tasks: list[TaskSnapshot] = []

        if task_id:
            snap = self._active.get(task_id) or self._finished.get(task_id)
            if snap:
                tasks.append(snap)
        else:
            tasks.extend(self._active.values())
            if include_finished:
                tasks.extend(self._finished.values())

        if session_key:
            tasks = [t for t in tasks if t.origin_session_key == session_key]
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]

        tasks.sort(key=lambda t: t.started_at or 0, reverse=True)
        running = sum(1 for t in tasks if t.status in ("queued", "running"))

        return {
            "running": running,
            "total": len(tasks),
            "tasks": [t.to_dict() for t in tasks],
        }

    def get_active_digest(self, session_key: str | None = None) -> str:
        """返回适合注入 system prompt 的极短任务摘要。无活跃任务时返回空字符串。"""
        tasks = list(self._active.values())
        recent_finished = [
            s for s in self._finished.values()
            if s.finished_at and (time.time() - s.finished_at) < 300
        ]
        all_relevant = tasks + recent_finished

        if session_key:
            all_relevant = [t for t in all_relevant if t.origin_session_key == session_key]

        if not all_relevant:
            return ""

        lines = ["## Active Background Tasks"]
        for t in sorted(all_relevant, key=lambda x: x.started_at or 0, reverse=True)[:5]:
            if t.status in ("queued", "running"):
                elapsed = int(time.time() - (t.started_at or time.time()))
                lines.append(
                    f"- [{t.task_type}:{t.task_id}] {t.status} {elapsed}s "
                    f"— \"{t.prompt_preview}\""
                )
            else:
                ago = int(time.time() - (t.finished_at or time.time()))
                lines.append(
                    f"- [{t.task_type}:{t.task_id}] {t.status} {ago}s ago "
                    f"— \"{t.prompt_preview}\""
                )
        return "\n".join(lines)

    def get_timeline(self, task_id: str) -> list[TimelineEvent]:
        snap = self._active.get(task_id) or self._finished.get(task_id)
        if snap:
            return list(snap.timeline)
        return self._load_timeline_from_db(task_id)

    def list_tasks(self, *, include_finished: bool = False) -> list[TaskSnapshot]:
        tasks = list(self._active.values())
        if include_finished:
            tasks.extend(self._finished.values())
        return tasks

    # ------------------------------------------------------------------
    # 完成回调
    # ------------------------------------------------------------------

    async def _on_complete(
        self, snapshot: TaskSnapshot, result: dict[str, Any] | None,
    ) -> None:
        loop = self._agent_loop
        if not loop:
            logger.warning("BackgroundTaskStore: no agent_loop ref, skipping completion callback")
            return

        status_label = "SUCCESS" if snapshot.status == "succeeded" else "ERROR"
        result_text = snapshot.result_preview or snapshot.error_message or "(no output)"
        formatted = (
            f"[Background Task {snapshot.task_id} {status_label}]\n"
            f"Type: {snapshot.task_type} | Duration: {snapshot.elapsed_ms}ms\n\n"
            f"{result_text}"
        )

        try:
            session = loop.sessions.get_or_create(snapshot.origin_session_key)
            session.messages.append({
                "role": "assistant",
                "content": formatted,
                "timestamp": time.time(),
                "tools_used": [f"bg_task:{snapshot.task_type}"],
            })
            loop.sessions.save(session)
            logger.info(
                "BackgroundTaskStore: result persisted to session {} for task {}",
                snapshot.origin_session_key, snapshot.task_id,
            )
        except Exception as exc:
            logger.error("BackgroundTaskStore: failed to persist result: {}", exc)

        try:
            bus = getattr(loop, "bus", None)
            if bus and hasattr(bus, "publish_outbound"):
                from nanobot.bus.events import OutboundMessage
                parts = snapshot.origin_session_key.split(":", 1)
                channel = parts[0] if parts else "cli"
                chat_id = parts[1] if len(parts) > 1 else "direct"
                result_or_coro = bus.publish_outbound(OutboundMessage(
                    channel=channel,
                    chat_id=chat_id,
                    content=formatted,
                ))
                if asyncio.iscoroutine(result_or_coro):
                    await result_or_coro
        except Exception as exc:
            logger.warning("BackgroundTaskStore: failed to publish outbound: {}", exc)

    # ------------------------------------------------------------------
    # SQLite 持久层
    # ------------------------------------------------------------------

    def _persist_task(self, snapshot: TaskSnapshot) -> None:
        if not self._db:
            return
        try:
            import json
            self._db.execute(
                """INSERT OR REPLACE INTO bg_tasks
                   (task_id, task_type, origin_session_key, status,
                    prompt_preview, project_path, started_at, finished_at,
                    result_preview, error_message, extra)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot.task_id, snapshot.task_type,
                    snapshot.origin_session_key, snapshot.status,
                    snapshot.prompt_preview, snapshot.project_path,
                    snapshot.started_at, snapshot.finished_at,
                    snapshot.result_preview, snapshot.error_message,
                    json.dumps({"cli_session_id": snapshot.cli_session_id}),
                ),
            )
            self._db.commit()
        except Exception as exc:
            logger.warning("BackgroundTaskStore: persist_task failed: {}", exc)

    def _update_task_status(
        self, task_id: str, status: str, snapshot: TaskSnapshot | None = None,
    ) -> None:
        if not self._db:
            return
        try:
            if snapshot:
                self._db.execute(
                    """UPDATE bg_tasks SET status=?, finished_at=?,
                       result_preview=?, error_message=? WHERE task_id=?""",
                    (status, snapshot.finished_at, snapshot.result_preview,
                     snapshot.error_message, task_id),
                )
            else:
                self._db.execute(
                    "UPDATE bg_tasks SET status=? WHERE task_id=?",
                    (status, task_id),
                )
            self._db.commit()
        except Exception as exc:
            logger.warning("BackgroundTaskStore: update_task_status failed: {}", exc)

    def _persist_event(self, task_id: str, event: str, detail: str = "") -> None:
        if not self._db:
            return
        try:
            self._db.execute(
                "INSERT INTO bg_task_events (task_id, event, detail, timestamp) VALUES (?, ?, ?, ?)",
                (task_id, event, detail, time.time()),
            )
            self._db.commit()
        except Exception as exc:
            logger.warning("BackgroundTaskStore: persist_event failed: {}", exc)

    def query_history(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        session_key: str | None = None,
    ) -> dict[str, Any]:
        """从 DB 查询历史任务（已完成），分页返回。"""
        if not self._db:
            return {"tasks": [], "total": 0, "page": page, "page_size": page_size}
        try:
            where = "WHERE status IN ('succeeded','failed','cancelled')"
            params: list[Any] = []
            if session_key:
                where += " AND origin_session_key = ?"
                params.append(session_key)

            count_row = self._db.fetchone(
                f"SELECT COUNT(*) as cnt FROM bg_tasks {where}", tuple(params)
            )
            total = count_row["cnt"] if count_row else 0

            offset = (page - 1) * page_size
            params.extend([page_size, offset])
            rows = self._db.fetchall(
                f"""SELECT task_id, task_type, origin_session_key, status,
                           prompt_preview, project_path, started_at, finished_at,
                           result_preview, error_message, extra
                    FROM bg_tasks {where}
                    ORDER BY started_at DESC
                    LIMIT ? OFFSET ?""",
                tuple(params),
            )
            tasks = []
            for r in rows:
                import json as _json
                extra = {}
                try:
                    extra = _json.loads(r.get("extra", "{}") or "{}")
                except Exception:
                    pass
                elapsed = 0
                if r.get("started_at") and r.get("finished_at"):
                    elapsed = int((r["finished_at"] - r["started_at"]) * 1000)
                tasks.append({
                    "task_id": r["task_id"],
                    "task_type": r["task_type"],
                    "origin_session_key": r["origin_session_key"],
                    "status": r["status"],
                    "prompt_preview": r.get("prompt_preview", ""),
                    "started_at": r.get("started_at"),
                    "finished_at": r.get("finished_at"),
                    "elapsed_ms": elapsed,
                    "result_preview": r.get("result_preview", ""),
                    "error_message": r.get("error_message", ""),
                    "project_path": r.get("project_path", ""),
                    "cli_session_id": extra.get("cli_session_id", ""),
                    "phase": "",
                    "last_tool_name": "",
                    "todo_summary": None,
                    "timeline": [],
                })
            return {"tasks": tasks, "total": total, "page": page, "page_size": page_size}
        except Exception as exc:
            logger.warning("BackgroundTaskStore: query_history failed: {}", exc)
            return {"tasks": [], "total": 0, "page": page, "page_size": page_size}

    def _load_timeline_from_db(self, task_id: str) -> list[TimelineEvent]:
        if not self._db:
            return []
        try:
            rows = self._db.fetchall(
                "SELECT event, detail, timestamp FROM bg_task_events WHERE task_id=? ORDER BY timestamp",
                (task_id,),
            )
            return [
                TimelineEvent(timestamp=r["timestamp"], event=r["event"], detail=r.get("detail", ""))
                for r in rows
            ]
        except Exception:
            return []
