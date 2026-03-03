"""Cron service for scheduling agent tasks."""

import asyncio
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine

from loguru import logger

from nanobot.cron.types import CronJob, CronJobState, CronPayload, CronSchedule, CronStore


def _now_ms() -> int:
    return int(time.time() * 1000)


def _compute_next_run(schedule: CronSchedule, now_ms: int) -> int | None:
    """Compute next run time in ms."""
    if schedule.kind == "at":
        return schedule.at_ms if schedule.at_ms and schedule.at_ms > now_ms else None
    
    if schedule.kind == "every":
        if not schedule.every_ms or schedule.every_ms <= 0:
            return None
        # Next interval from now
        return now_ms + schedule.every_ms
    
    if schedule.kind == "cron" and schedule.expr:
        try:
            from croniter import croniter
            from zoneinfo import ZoneInfo
            # Use caller-provided reference time for deterministic scheduling
            base_time = now_ms / 1000
            tz = ZoneInfo(schedule.tz) if schedule.tz else datetime.now().astimezone().tzinfo
            base_dt = datetime.fromtimestamp(base_time, tz=tz)
            cron = croniter(schedule.expr, base_dt)
            next_dt = cron.get_next(datetime)
            return int(next_dt.timestamp() * 1000)
        except Exception:
            return None
    
    return None


def _validate_schedule_for_add(schedule: CronSchedule) -> None:
    """Validate schedule fields that would otherwise create non-runnable jobs."""
    if schedule.tz and schedule.kind != "cron":
        raise ValueError("tz can only be used with cron schedules")

    if schedule.kind == "cron" and schedule.tz:
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(schedule.tz)
        except Exception:
            raise ValueError(f"unknown timezone '{schedule.tz}'") from None


class CronService:
    """Service for managing and executing scheduled jobs."""
    
    def __init__(
        self,
        store_path: Path,
        on_job: Callable[[CronJob], Coroutine[Any, Any, str | None]] | None = None
    ):
        self.store_path = store_path
        self.on_job = on_job  # Callback to execute job, returns response text
        self._store: CronStore | None = None
        self._timer_task: asyncio.Task | None = None
        self._running = False
    
    def _load_store(self) -> CronStore:
        """Load jobs from disk."""
        if self._store:
            return self._store
        
        if self.store_path.exists():
            try:
                data = json.loads(self.store_path.read_text(encoding="utf-8"))
                jobs = []
                for j in data.get("jobs", []):
                    jobs.append(CronJob(
                        id=j["id"],
                        name=j["name"],
                        enabled=j.get("enabled", True),
                        schedule=CronSchedule(
                            kind=j["schedule"]["kind"],
                            at_ms=j["schedule"].get("atMs"),
                            every_ms=j["schedule"].get("everyMs"),
                            expr=j["schedule"].get("expr"),
                            tz=j["schedule"].get("tz"),
                        ),
                        payload=CronPayload(
                            kind=j["payload"].get("kind", "agent_turn"),
                            message=j["payload"].get("message", ""),
                            deliver=j["payload"].get("deliver", False),
                            channel=j["payload"].get("channel"),
                            to=j["payload"].get("to"),
                        ),
                        state=CronJobState(
                            next_run_at_ms=j.get("state", {}).get("nextRunAtMs"),
                            last_run_at_ms=j.get("state", {}).get("lastRunAtMs"),
                            last_status=j.get("state", {}).get("lastStatus"),
                            last_error=j.get("state", {}).get("lastError"),
                            task_completed_at_ms=j.get("state", {}).get("taskCompletedAtMs"),
                            task_cycle_id=j.get("state", {}).get("taskCycleId"),
                        ),
                        created_at_ms=j.get("createdAtMs", 0),
                        updated_at_ms=j.get("updatedAtMs", 0),
                        delete_after_run=j.get("deleteAfterRun", False),
                        source=j.get("source", "cli"),
                    ))
                self._store = CronStore(jobs=jobs)
            except Exception as e:
                logger.warning("Failed to load cron store: {}", e)
                self._store = CronStore()
        else:
            self._store = CronStore()
        
        return self._store
    
    def _save_store(self) -> None:
        """Save jobs to disk."""
        if not self._store:
            return
        
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "version": self._store.version,
            "jobs": [
                {
                    "id": j.id,
                    "name": j.name,
                    "enabled": j.enabled,
                    "schedule": {
                        "kind": j.schedule.kind,
                        "atMs": j.schedule.at_ms,
                        "everyMs": j.schedule.every_ms,
                        "expr": j.schedule.expr,
                        "tz": j.schedule.tz,
                    },
                    "payload": {
                        "kind": j.payload.kind,
                        "message": j.payload.message,
                        "deliver": j.payload.deliver,
                        "channel": j.payload.channel,
                        "to": j.payload.to,
                    },
                    "state": {
                        "nextRunAtMs": j.state.next_run_at_ms,
                        "lastRunAtMs": j.state.last_run_at_ms,
                        "lastStatus": j.state.last_status,
                        "lastError": j.state.last_error,
                        "taskCompletedAtMs": j.state.task_completed_at_ms,
                        "taskCycleId": j.state.task_cycle_id,
                    },
                    "createdAtMs": j.created_at_ms,
                    "updatedAtMs": j.updated_at_ms,
                    "deleteAfterRun": j.delete_after_run,
                    "source": j.source,
                }
                for j in self._store.jobs
            ]
        }
        
        self.store_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    async def start(self) -> None:
        """Start the cron service."""
        self._running = True
        self._load_store()
        self._recompute_next_runs()
        self._save_store()
        self._arm_timer()
        logger.info("Cron service started with {} jobs", len(self._store.jobs if self._store else []))
    
    def stop(self) -> None:
        """Stop the cron service."""
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
    
    def _recompute_next_runs(self) -> None:
        """Recompute next run times for all enabled jobs."""
        if not self._store:
            return
        now = _now_ms()
        for job in self._store.jobs:
            if job.enabled:
                job.state.next_run_at_ms = _compute_next_run(job.schedule, now)
    
    def _get_next_wake_ms(self) -> int | None:
        """Get the earliest next run time across all jobs."""
        if not self._store:
            return None
        times = [j.state.next_run_at_ms for j in self._store.jobs 
                 if j.enabled and j.state.next_run_at_ms]
        return min(times) if times else None
    
    def _arm_timer(self) -> None:
        """Schedule the next timer tick."""
        if self._timer_task:
            self._timer_task.cancel()
        
        next_wake = self._get_next_wake_ms()
        if not next_wake or not self._running:
            return
        
        delay_ms = max(0, next_wake - _now_ms())
        delay_s = delay_ms / 1000
        
        async def tick():
            await asyncio.sleep(delay_s)
            if self._running:
                await self._on_timer()
        
        self._timer_task = asyncio.create_task(tick())
    
    async def _on_timer(self) -> None:
        """Handle timer tick - run due jobs."""
        self._load_store()
        if not self._store:
            return
        
        now = _now_ms()
        due_jobs = [
            j for j in self._store.jobs
            if j.enabled and j.state.next_run_at_ms and now >= j.state.next_run_at_ms
        ]
        
        for job in due_jobs:
            await self._execute_job(job)
        
        self._save_store()
        self._arm_timer()
    
    def _compute_cycle_id(self, schedule: CronSchedule) -> str:
        """Compute current cycle identifier based on schedule type."""
        tz = None
        if schedule.tz:
            from zoneinfo import ZoneInfo
            try:
                tz = ZoneInfo(schedule.tz)
            except Exception:
                pass
        now_dt = datetime.now(tz) if tz else datetime.now().astimezone()

        if schedule.kind == "at":
            return "once"
        if schedule.kind == "cron" and schedule.expr:
            parts = schedule.expr.strip().split()
            if len(parts) >= 5:
                minute_field, hour_field = parts[0], parts[1]
                if hour_field != "*" and minute_field != "*":
                    return now_dt.strftime("%Y-%m-%d")
                if hour_field == "*" or (hour_field != "*" and minute_field == "*"):
                    return now_dt.strftime("%Y-%m-%d-%H")
            return now_dt.strftime("%Y-%m-%d")
        if schedule.kind == "every" and schedule.every_ms:
            return now_dt.strftime("%Y-%m-%d")
        return now_dt.strftime("%Y-%m-%d")

    async def _execute_job(self, job: CronJob) -> None:
        """Execute a single job."""
        current_cycle = self._compute_cycle_id(job.schedule)
        if (job.state.task_completed_at_ms
                and job.state.task_cycle_id == current_cycle):
            job.state.last_status = "skipped"
            job.state.last_run_at_ms = _now_ms()
            job.updated_at_ms = _now_ms()
            if job.schedule.kind != "at":
                job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
            logger.info("Cron: job '{}' skipped (cycle {} already done)", job.name, current_cycle)
            return

        start_ms = _now_ms()
        logger.info("Cron: executing job '{}' ({})", job.name, job.id)
        
        try:
            response = None
            if self.on_job:
                response = await self.on_job(job)
            
            job.state.last_status = "ok"
            job.state.last_error = None
            logger.info("Cron: job '{}' completed", job.name)
            
        except Exception as e:
            job.state.last_status = "error"
            job.state.last_error = str(e)
            logger.error("Cron: job '{}' failed: {}", job.name, e)
        
        job.state.last_run_at_ms = start_ms
        job.updated_at_ms = _now_ms()
        
        # Handle one-shot jobs
        if job.schedule.kind == "at":
            if job.delete_after_run:
                self._store.jobs = [j for j in self._store.jobs if j.id != job.id]
            else:
                job.enabled = False
                job.state.next_run_at_ms = None
        else:
            # Compute next run
            job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
    
    # ========== Public API ==========
    
    def list_jobs(self, include_disabled: bool = False) -> list[CronJob]:
        """List all jobs."""
        store = self._load_store()
        jobs = store.jobs if include_disabled else [j for j in store.jobs if j.enabled]
        return sorted(jobs, key=lambda j: j.state.next_run_at_ms or float('inf'))
    
    def add_job(
        self,
        name: str,
        schedule: CronSchedule,
        message: str,
        deliver: bool = False,
        channel: str | None = None,
        to: str | None = None,
        delete_after_run: bool = False,
    ) -> CronJob:
        """Add a new job."""
        store = self._load_store()
        _validate_schedule_for_add(schedule)
        now = _now_ms()
        
        job = CronJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            enabled=True,
            schedule=schedule,
            payload=CronPayload(
                kind="agent_turn",
                message=message,
                deliver=deliver,
                channel=channel,
                to=to,
            ),
            state=CronJobState(next_run_at_ms=_compute_next_run(schedule, now)),
            created_at_ms=now,
            updated_at_ms=now,
            delete_after_run=delete_after_run,
        )
        
        store.jobs.append(job)
        self._save_store()
        self._arm_timer()
        
        logger.info("Cron: added job '{}' ({})", name, job.id)
        return job
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID."""
        store = self._load_store()
        before = len(store.jobs)
        store.jobs = [j for j in store.jobs if j.id != job_id]
        removed = len(store.jobs) < before
        
        if removed:
            self._save_store()
            self._arm_timer()
            logger.info("Cron: removed job {}", job_id)
        
        return removed
    
    def enable_job(self, job_id: str, enabled: bool = True) -> CronJob | None:
        """Enable or disable a job."""
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                job.enabled = enabled
                job.updated_at_ms = _now_ms()
                if enabled:
                    job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
                else:
                    job.state.next_run_at_ms = None
                self._save_store()
                self._arm_timer()
                return job
        return None
    
    def mark_job_done(self, job_id: str) -> CronJob | None:
        """Mark a job's task as completed for the current cycle."""
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                now = _now_ms()
                cycle_id = self._compute_cycle_id(job.schedule)
                job.state.task_completed_at_ms = now
                job.state.task_cycle_id = cycle_id
                job.updated_at_ms = now
                self._save_store()
                logger.info("Cron: job '{}' marked done for cycle {}", job.name, cycle_id)
                return job
        return None

    def get_job_status(self, job_id: str | None = None) -> dict | list[dict] | None:
        """Get detailed job status including completion state.

        If job_id is given, returns a single dict.
        If job_id is None, returns a list of dicts for all enabled jobs.
        """
        store = self._load_store()
        if job_id:
            for job in store.jobs:
                if job.id == job_id:
                    return self._job_status_dict(job)
            return None
        return [self._job_status_dict(j) for j in store.jobs if j.enabled]

    def _job_status_dict(self, job: CronJob) -> dict:
        current_cycle = self._compute_cycle_id(job.schedule)
        is_done = (
            job.state.task_completed_at_ms is not None
            and job.state.task_cycle_id == current_cycle
        )
        return {
            "id": job.id,
            "name": job.name,
            "enabled": job.enabled,
            "schedule_kind": job.schedule.kind,
            "last_run_at_ms": job.state.last_run_at_ms,
            "last_status": job.state.last_status,
            "next_run_at_ms": job.state.next_run_at_ms,
            "task_completed_at_ms": job.state.task_completed_at_ms,
            "task_cycle_id": job.state.task_cycle_id,
            "current_cycle_id": current_cycle,
            "is_current_cycle_done": is_done,
        }

    async def run_job(self, job_id: str, force: bool = False) -> bool:
        """Manually run a job."""
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                if not force and not job.enabled:
                    return False
                await self._execute_job(job)
                self._save_store()
                self._arm_timer()
                return True
        return False
    
    def load_schedule(self, schedule_path: Path) -> int:
        """Load tasks from a declarative schedule.json file.

        Syncs schedule-sourced jobs with the store: adds new, updates changed,
        removes jobs no longer present in the file.  CLI-sourced jobs are never
        touched.  Returns the number of active schedule jobs after sync.
        """
        if not schedule_path.exists():
            return 0

        try:
            data = json.loads(schedule_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to read schedule file {}: {}", schedule_path, e)
            return 0

        tasks = data.get("tasks", [])
        if not tasks:
            return 0

        global_tz = data.get("timezone")
        defaults = data.get("defaults", {})
        default_deliver = defaults.get("deliver", False)
        default_channel = defaults.get("channel")
        default_to = defaults.get("to")

        store = self._load_store()
        existing = {j.id: j for j in store.jobs if j.source == "schedule"}
        seen_ids: set[str] = set()
        now = _now_ms()

        for task in tasks:
            task_id = task.get("id")
            if not task_id:
                continue
            job_id = f"sched:{task_id}"
            seen_ids.add(job_id)

            tz = task.get("timezone") or global_tz
            schedule = CronSchedule(kind="cron", expr=task.get("schedule"), tz=tz)
            enabled = task.get("enabled", True)
            message = task.get("message", "")
            deliver = task.get("deliver", default_deliver)
            channel = task.get("channel", default_channel)
            to = task.get("to", default_to)

            if job_id in existing:
                job = existing[job_id]
                changed = (
                    job.schedule.expr != schedule.expr
                    or job.schedule.tz != schedule.tz
                    or job.payload.message != message
                    or job.enabled != enabled
                    or job.payload.deliver != deliver
                    or job.payload.channel != channel
                    or job.payload.to != to
                    or job.name != task.get("name", "")
                )
                if changed:
                    job.name = task.get("name", "")
                    job.schedule = schedule
                    job.payload.message = message
                    job.payload.deliver = deliver
                    job.payload.channel = channel
                    job.payload.to = to
                    job.enabled = enabled
                    job.updated_at_ms = now
                    if enabled:
                        job.state.next_run_at_ms = _compute_next_run(schedule, now)
                    else:
                        job.state.next_run_at_ms = None
                    logger.info("Schedule: updated job '{}' ({})", job.name, job_id)
            else:
                job = CronJob(
                    id=job_id,
                    name=task.get("name", task_id),
                    enabled=enabled,
                    schedule=schedule,
                    payload=CronPayload(
                        kind="agent_turn",
                        message=message,
                        deliver=deliver,
                        channel=channel,
                        to=to,
                    ),
                    state=CronJobState(
                        next_run_at_ms=_compute_next_run(schedule, now) if enabled else None,
                    ),
                    created_at_ms=now,
                    updated_at_ms=now,
                    source="schedule",
                )
                store.jobs.append(job)
                logger.info("Schedule: added job '{}' ({})", job.name, job_id)

        stale = [jid for jid in existing if jid not in seen_ids]
        if stale:
            store.jobs = [j for j in store.jobs if j.id not in stale]
            for jid in stale:
                logger.info("Schedule: removed stale job {}", jid)

        self._save_store()
        return len([j for j in store.jobs if j.source == "schedule"])

    def status(self) -> dict:
        """Get service status."""
        store = self._load_store()
        return {
            "enabled": self._running,
            "jobs": len(store.jobs),
            "next_wake_at_ms": self._get_next_wake_ms(),
        }
