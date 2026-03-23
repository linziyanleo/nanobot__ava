"""Unified slash command registry for cross-platform command handling."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Awaitable, Callable

from loguru import logger

from nanobot.agent.memory import MemoryStore
from nanobot.session.manager import Session

if TYPE_CHECKING:
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.events import InboundMessage


@dataclass
class SlashCommand:
    """A registered slash command."""

    name: str
    description: str
    handler: Callable[["InboundMessage", "AgentLoop"], Awaitable[str]]
    pre_dispatch: bool = False


class CommandRegistry:
    """Registry of slash commands available across all channels."""

    def __init__(self) -> None:
        self._commands: dict[str, SlashCommand] = {}

    def register(
        self,
        name: str,
        description: str,
        handler: Callable[["InboundMessage", "AgentLoop"], Awaitable[str]],
        pre_dispatch: bool = False,
    ) -> None:
        self._commands[name.lower().lstrip("/")] = SlashCommand(
            name=name.lower().lstrip("/"),
            description=description,
            handler=handler,
            pre_dispatch=pre_dispatch,
        )

    def match(self, text: str) -> SlashCommand | None:
        """Match message text to a registered command. Returns None if not a command."""
        stripped = text.strip().lower()
        if not stripped.startswith("/"):
            return None
        cmd_name = stripped[1:].split()[0] if stripped[1:] else ""
        return self._commands.get(cmd_name)

    def get_help_text(self, agent: "AgentLoop | None" = None) -> str:
        lines = ["🐈 Nanobot commands:"]
        for cmd in sorted(self._commands.values(), key=lambda c: c.name):
            lines.append(f"/{cmd.name} — {cmd.description}")
        if agent:
            tool_names = sorted(agent.tools.tool_names)
            if tool_names:
                lines.append(f"\n🔧 Available tools ({len(tool_names)}):")
                lines.append(", ".join(tool_names))
        return "\n".join(lines)

    def get_bot_commands(self) -> list[tuple[str, str]]:
        """Return (name, description) pairs for platform-native command registration."""
        return [
            (cmd.name, cmd.description)
            for cmd in sorted(self._commands.values(), key=lambda c: c.name)
        ]


_boot_time = time.monotonic()


def register_builtin_commands(registry: CommandRegistry, agent: AgentLoop) -> None:
    """Register the built-in slash commands."""

    async def _archive_snapshot_with_retry(
        _agent: AgentLoop,
        *,
        session_key: str,
        snapshot: list[dict[str, object]],
        retries: int = 3,
    ) -> None:
        """Best-effort background archival with raw fallback to avoid data loss."""
        if not snapshot:
            return

        temp = Session(key=session_key)
        temp.messages = list(snapshot)
        for attempt in range(retries):
            try:
                if await _agent._consolidate_memory(temp, archive_all=True):
                    return
            except Exception:
                logger.exception(
                    "/new background archival attempt {} failed for {}",
                    attempt + 1,
                    session_key,
                )

        try:
            lines: list[str] = []
            for m in snapshot:
                content = m.get("content")
                if not content:
                    continue
                tools = (
                    f" [tools: {', '.join(m['tools_used'])}]"
                    if m.get("tools_used")
                    else ""
                )
                lines.append(
                    f"[{str(m.get('timestamp', '?'))[:16]}] "
                    f"{str(m.get('role', '?')).upper()}{tools}: {content}"
                )

            if lines:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                MemoryStore(_agent.workspace).append_history(
                    f"[{ts}] [RAW] {len(snapshot)} messages\n" + "\n".join(lines)
                )
            logger.warning(
                "/new archival degraded to raw history dump for {} (messages={})",
                session_key,
                len(snapshot),
            )
        except Exception:
            logger.exception("/new raw fallback archive failed for {}", session_key)

    async def _cmd_help(msg: InboundMessage, _agent: AgentLoop) -> str:
        return registry.get_help_text(agent=_agent)

    async def _cmd_start(msg: InboundMessage, _agent: AgentLoop) -> str:
        return (
            "👋 Hi! I'm nanobot.\n\n"
            "Send me a message and I'll respond!\n"
            "Type /help to see available commands."
        )

    async def _cmd_new(msg: InboundMessage, _agent: AgentLoop) -> str:
        key = msg.session_key
        session = _agent.sessions.get_or_create(key)

        lock = _agent._consolidation_locks.setdefault(session.key, asyncio.Lock())
        _agent._consolidating.add(session.key)
        try:
            async with lock:
                snapshot = session.messages[session.last_consolidated:]
                session.clear()
                _agent.sessions.save(session)
                _agent.sessions.invalidate(session.key)
                _agent._consolidation_locks.pop(session.key, None)
        finally:
            _agent._consolidating.discard(session.key)

        if snapshot:
            task = asyncio.create_task(
                _archive_snapshot_with_retry(
                    _agent,
                    session_key=session.key,
                    snapshot=list(snapshot),
                )
            )
            _agent._pending_archives.append(task)

            def _drop_pending(done_task: asyncio.Task) -> None:
                try:
                    _agent._pending_archives.remove(done_task)
                except ValueError:
                    pass

            task.add_done_callback(_drop_pending)

        return "New session started."

    async def _cmd_stop(msg: InboundMessage, _agent: AgentLoop) -> str:
        tasks = _agent._active_tasks.pop(msg.session_key, [])
        cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        sub_cancelled = await _agent.subagents.cancel_by_session(msg.session_key)
        total = cancelled + sub_cancelled
        return f"⏹ Stopped {total} task(s)." if total else "No active task to stop."

    async def _cmd_status(msg: InboundMessage, _agent: AgentLoop) -> str:
        uptime_s = time.monotonic() - _boot_time
        hours, remainder = divmod(int(uptime_s), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"

        session = _agent.sessions.get_or_create(msg.session_key)
        msg_count = len(session.messages)

        # Session-level token stats (from session JSONL metadata)
        s_stats = session.token_stats
        s_total = s_stats.get("total_tokens", 0)
        s_prompt = s_stats.get("total_prompt_tokens", 0)
        s_completion = s_stats.get("total_completion_tokens", 0)
        s_calls = s_stats.get("llm_calls", 0)

        # Global token stats (from TokenStatsCollector, same as console-ui)
        global_line = ""
        if _agent._token_stats:
            g = _agent._token_stats.get_totals()
            g_total = g.get("total_tokens", 0)
            g_calls = g.get("total_calls", 0)
            g_prompt = g.get("prompt_tokens", 0)
            g_completion = g.get("completion_tokens", 0)
            global_line = (
                f"\n🌐 Global tokens: {g_total:,} ({g_calls} calls)\n"
                f"   ├ Prompt: {g_prompt:,}\n"
                f"   └ Completion: {g_completion:,}"
            )

        # Simulate the exact same context building as _process_message
        history = session.get_history(max_messages=_agent.memory_window)
        if _agent._compression_enabled:
            history = _agent.history_compressor.compress(history, "(status check)")

        simulated_messages = _agent.context.build_messages(
            history=history,
            current_message="(status check)",
            channel=msg.channel, chat_id=msg.chat_id,
        )

        def _estimate_chars(messages: list) -> int:
            total = 0
            for m in messages:
                content = m.get("content", "")
                if isinstance(content, str):
                    total += len(content)
                elif isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict):
                            total += len(c.get("text", ""))
                for tc in m.get("tool_calls", []):
                    total += len(json.dumps(tc, ensure_ascii=False))
            return total

        sys_prompt = simulated_messages[0].get("content", "") if simulated_messages else ""
        sys_chars = len(sys_prompt) if isinstance(sys_prompt, str) else 0
        sys_est = sys_chars // 4

        history_chars = _estimate_chars(simulated_messages[1:])
        history_est = history_chars // 4

        tool_defs = _agent.tools.get_definitions()
        tool_chars = sum(len(json.dumps(t, ensure_ascii=False)) for t in tool_defs)
        tool_est = tool_chars // 4

        total_context_est = sys_est + history_est + tool_est
        history_msg_count = len(simulated_messages) - 1

        cron_info = ""
        if _agent.cron_service:
            jobs = _agent.cron_service.list_jobs(include_disabled=True)
            enabled = sum(1 for j in jobs if j.enabled)
            cron_info = f"\n📋 Cron: {enabled} active / {len(jobs)} total"

        cc_snapshot = _agent.subagents.get_claude_code_status(session_key=msg.session_key, verbose=False)
        cc_info = "\n🤖 Claude Code: 0 running / 0 tracked"
        if cc_snapshot["total"] > 0:
            latest = cc_snapshot["tasks"][0]
            todo = latest.get("todo_summary", {})
            todo_text = ""
            if todo.get("total", 0):
                todo_text = (
                    f" | TODO {todo.get('in_progress', 0)} in-progress/"
                    f"{todo.get('pending', 0)} pending/{todo.get('completed', 0)} done"
                )
            ctx_left = latest.get("context_remaining_est")
            ctx_text = f" | Ctx~{ctx_left:,}" if isinstance(ctx_left, int) else ""
            cc_info = (
                f"\n🤖 Claude Code: {cc_snapshot['running']} running / {cc_snapshot['total']} tracked\n"
                f"   └ Latest: {latest['task_id']} {latest['status']} "
                f"({latest['phase']}, {latest['elapsed_ms']}ms){todo_text}{ctx_text}"
            )

        compression_label = "on" if _agent._compression_enabled else "off"

        return (
            f"🤖 Nanobot Status\n"
            f"⏱ Uptime: {uptime_str}\n"
            f"💬 Session: {msg_count} messages (window: {_agent.memory_window})\n"
            f"💰 Session tokens: {s_total:,} ({s_calls} calls)\n"
            f"   ├ Prompt: {s_prompt:,}\n"
            f"   └ Completion: {s_completion:,}"
            f"{global_line}\n"
            f"📐 Next-call context (est., compression: {compression_label}):\n"
            f"   ├ System prompt: ~{sys_est:,} tk ({sys_chars:,} chars)\n"
            f"   ├ History: ~{history_est:,} tk ({history_msg_count} msgs)\n"
            f"   ├ Tool defs: ~{tool_est:,} tk ({len(tool_defs)} tools)\n"
            f"   └ Total: ~{total_context_est:,} tk"
            f"{cron_info}"
            f"{cc_info}"
        )

    async def _cmd_cc_status(msg: InboundMessage, _agent: AgentLoop) -> str:
        parts = msg.content.strip().split()
        task_id: str | None = None
        verbose = False
        for token in parts[1:]:
            low = token.lower()
            if low in {"-v", "--verbose", "verbose"}:
                verbose = True
            elif task_id is None:
                task_id = token

        snapshot = _agent.subagents.get_claude_code_status(
            task_id=task_id,
            session_key=None if task_id else msg.session_key,
            verbose=verbose,
        )
        if task_id and snapshot["total"] == 0:
            return f"Claude Code task '{task_id}' not found."
        if snapshot["total"] == 0:
            return "🤖 Claude Code tasks: none"

        lines = [
            f"🤖 Claude Code Status: {snapshot['running']} running / {snapshot['total']} tracked",
        ]
        visible = snapshot["tasks"] if (verbose or task_id) else snapshot["tasks"][:5]
        for item in visible:
            todo = item.get("todo_summary", {})
            todo_text = ""
            if todo.get("total", 0):
                todo_text = (
                    f" | todo {todo.get('in_progress', 0)} in-progress/"
                    f"{todo.get('pending', 0)} pending/{todo.get('completed', 0)} done"
                )
            ctx_left = item.get("context_remaining_est")
            ctx_text = f" | ctx~{ctx_left:,}" if isinstance(ctx_left, int) else ""
            lines.append(
                f"- {item['task_id']} {item['status']} phase={item['phase']} "
                f"elapsed={item['elapsed_ms']}ms{todo_text}{ctx_text}"
            )
            if item.get("last_tool_name"):
                lines.append(f"  last tool: {item['last_tool_name']}")
            if item.get("error_message"):
                lines.append(f"  error: {str(item['error_message'])[:200]}")
            if verbose and item.get("prompt_preview"):
                lines.append(f"  prompt: {item['prompt_preview']}")
            if verbose and item.get("todo_items"):
                for todo_item in item["todo_items"][:8]:
                    lines.append(
                        f"  - [{todo_item.get('status', 'pending')}] "
                        f"{todo_item.get('content', '')}"
                    )

        if not (verbose or task_id) and snapshot["total"] > len(visible):
            lines.append(f"... {snapshot['total'] - len(visible)} more tasks (use /cc_status --verbose)")

        return "\n".join(lines)

    registry.register("help", "Show available commands", _cmd_help)
    registry.register("start", "Start the bot", _cmd_start)
    registry.register("new", "Start a new conversation", _cmd_new)
    registry.register("stop", "Stop the current task", _cmd_stop, pre_dispatch=True)
    registry.register("status", "Show bot status", _cmd_status)
    registry.register("cc_status", "Show Claude Code task status", _cmd_cc_status)
