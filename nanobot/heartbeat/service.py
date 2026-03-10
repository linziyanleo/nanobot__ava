"""Heartbeat service - periodic agent wake-up to check for tasks."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from loguru import logger

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider

_HEARTBEAT_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "heartbeat",
            "description": "Report heartbeat decision after reviewing tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["skip", "run"],
                        "description": "skip = nothing to do, run = has active tasks",
                    },
                    "tasks": {
                        "type": "string",
                        "description": "Natural-language summary of active tasks (required for run)",
                    },
                },
                "required": ["action"],
            },
        },
    }
]


class HeartbeatService:
    """
    Periodic heartbeat service that wakes the agent to check for tasks.

    Phase 1 (decision): reads HEARTBEAT.md and asks the LLM — via a virtual
    tool call — whether there are active tasks.  This avoids free-text parsing
    and the unreliable HEARTBEAT_OK token.

    Phase 2 (execution): only triggered when Phase 1 returns ``run``.  The
    ``on_execute`` callback runs the task through the full agent loop and
    returns the result to deliver.
    """

    def __init__(
        self,
        workspace: Path,
        provider: LLMProvider,
        model: str,
        mini_model: str | None = None,
        on_execute: Callable[[str], Coroutine[Any, Any, str]] | None = None,
        on_notify: Callable[[str], Coroutine[Any, Any, None]] | None = None,
        interval_s: int = 30 * 60,
        enabled: bool = True,
        phase1_model: str | None = None,
        phase2_model: str | None = None,
    ):
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.mini_model = mini_model or model
        self.phase1_model = phase1_model or self.mini_model
        self.phase2_model = phase2_model or self.model
        self.on_execute = on_execute
        self.on_notify = on_notify
        self.interval_s = interval_s
        self.enabled = enabled
        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def heartbeat_file(self) -> Path:
        return self.workspace / "HEARTBEAT.md"

    @property
    def heartbeat_state_file(self) -> Path:
        return self.workspace / "heartbeat_state.json"

    def _read_heartbeat_file(self) -> str | None:
        if self.heartbeat_file.exists():
            try:
                return self.heartbeat_file.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    def _read_heartbeat_state(self) -> dict | None:
        """Read structured task completion state from heartbeat_state.json."""
        if self.heartbeat_state_file.exists():
            try:
                return json.loads(self.heartbeat_state_file.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def _all_tasks_done_today(self, state: dict | None) -> bool:
        """Check whether all tasks in state are completed for today's cycle.

        Conservative: returns False when state is missing or incomplete.
        """
        if not state or "tasks" not in state:
            return False
        tasks = state["tasks"]
        if not tasks:
            return False
        today = date.today().isoformat()
        for task_state in tasks.values():
            cycle = task_state.get("cycle", "")
            if cycle != today:
                return False
        return True

    async def _decide(self, content: str) -> tuple[str, str]:
        """Phase 1: ask LLM to decide skip/run via virtual tool call.

        Injects heartbeat_state.json into the prompt for structured context.
        Short-circuits with 'skip' if all tasks are done for today.
        Returns (action, tasks) where action is 'skip' or 'run'.
        """
        state = self._read_heartbeat_state()

        if self._all_tasks_done_today(state):
            logger.info("Heartbeat: all tasks done today, skipping LLM call")
            return "skip", ""

        state_context = ""
        if state:
            state_context = (
                "\n\n## Task Completion State (from heartbeat_state.json)\n"
                f"```json\n{json.dumps(state, indent=2, ensure_ascii=False)}\n```\n"
                "Use the completion state above to determine which tasks have already "
                "been completed for the current cycle and should NOT be re-executed."
            )

        response = await self.provider.chat(
            messages=[
                {"role": "system", "content": "You are a heartbeat agent. Call the heartbeat tool to report your decision."},
                {"role": "user", "content": (
                    "Review the following HEARTBEAT.md and task completion state, "
                    "then decide whether there are active tasks that still need to run.\n\n"
                    f"{content}{state_context}"
                )},
            ],
            tools=_HEARTBEAT_TOOL,
            model=self.phase1_model,
        )

        if not response.has_tool_calls:
            return "skip", ""

        args = response.tool_calls[0].arguments
        return args.get("action", "skip"), args.get("tasks", "")

    async def start(self) -> None:
        """Start the heartbeat service."""
        if not self.enabled:
            logger.info("Heartbeat disabled")
            return
        if self._running:
            logger.warning("Heartbeat already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Heartbeat started (every {}s)", self.interval_s)

    def stop(self) -> None:
        """Stop the heartbeat service."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run_loop(self) -> None:
        """Main heartbeat loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval_s)
                if self._running:
                    await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat error: {}", e)

    async def _tick(self) -> None:
        """Execute a single heartbeat tick."""
        content = self._read_heartbeat_file()
        if not content:
            logger.debug("Heartbeat: HEARTBEAT.md missing or empty")
            return

        logger.info("Heartbeat: checking for tasks...")

        try:
            action, tasks = await self._decide(content)

            if action != "run":
                logger.info("Heartbeat: OK (nothing to report)")
                return

            logger.info("Heartbeat: tasks found, executing...")
            if self.on_execute:
                response = await self.on_execute(tasks)
                if response and self.on_notify:
                    logger.info("Heartbeat: completed, delivering response")
                    await self.on_notify(response)
        except Exception:
            logger.exception("Heartbeat execution failed")

    async def trigger_now(self) -> str | None:
        """Manually trigger a heartbeat."""
        content = self._read_heartbeat_file()
        if not content:
            return None
        action, tasks = await self._decide(content)
        if action != "run" or not self.on_execute:
            return None
        return await self.on_execute(tasks)
