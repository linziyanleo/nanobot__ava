"""Claude Code CLI integration tool."""

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager

_MAX_OUTPUT_CHARS = 16000


class ClaudeCodeTool(Tool):
    """Run Claude Code CLI to modify code, add features, fix bugs, or analyze a codebase.
    
    Supports both synchronous (blocking) and asynchronous (background) execution modes.
    """

    def __init__(
        self,
        workspace: Path,
        token_stats: Any | None = None,
        default_project: str = "",
        model: str = "claude-sonnet-4-20250514",
        max_turns: int = 15,
        allowed_tools: str = "Read,Edit,Bash,Glob,Grep",
        timeout: int = 600,
        subagent_manager: "SubagentManager | None" = None,
    ) -> None:
        self._workspace = workspace
        self._token_stats = token_stats
        self._default_project = default_project or str(workspace)
        self._model = model
        self._max_turns = max_turns
        self._allowed_tools = allowed_tools
        self._timeout = timeout
        self._subagent_manager = subagent_manager
        # Context for async result routing
        self._channel = "cli"
        self._chat_id = "direct"
        self._session_key = "cli:direct"

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the origin context for async task result routing."""
        self._channel = channel
        self._chat_id = chat_id
        self._session_key = f"{channel}:{chat_id}"

    @property
    def name(self) -> str:
        return "claude_code"

    @property
    def description(self) -> str:
        return (
            "Run Claude Code CLI to execute code tasks: modify code, add features, "
            "fix bugs, refactor, or analyze a codebase. Default is async execution "
            "(task runs in background, notifies when complete). "
            "Use mode='fast' for simple tasks (async, max 5 turns), "
            "'standard' for complex tasks (async, max 15 turns), "
            "'readonly' for analysis (async), "
            "'sync' for synchronous blocking execution (backward compatible)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The task prompt for Claude Code. Be specific: include file paths, expected behavior, and constraints.",
                },
                "project_path": {
                    "type": "string",
                    "description": "Project directory (absolute path). Omit to use default project.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["fast", "standard", "readonly", "sync"],
                    "description": (
                        "fast: async, max 5 turns, 120s timeout; "
                        "standard: async, max 15 turns (default); "
                        "readonly: async, analysis only; "
                        "sync: synchronous blocking execution"
                    ),
                },
                "session_id": {
                    "type": "string",
                    "description": "Resume a previous Claude Code session by its session ID",
                },
            },
            "required": ["prompt"],
        }

    async def execute(
        self,
        prompt: str,
        project_path: str | None = None,
        mode: str = "standard",
        session_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        project = self._resolve_project(project_path)
        if not Path(project).is_dir():
            return f"Error: Project directory does not exist: {project}"

        # Sync mode: original blocking behavior
        if mode == "sync":
            return await self._execute_sync(prompt, project, session_id)

        # Async mode: delegate to SubagentManager
        if not self._subagent_manager:
            logger.warning("claude_code: SubagentManager not available, falling back to sync")
            return await self._execute_sync(prompt, project, session_id)

        return await self._subagent_manager.spawn_claude_code(
            prompt=prompt,
            project_path=project,
            mode=mode,
            session_id=session_id,
            origin_channel=self._channel,
            origin_chat_id=self._chat_id,
            session_key=self._session_key,
            timeout=120 if mode == "fast" else self._timeout,
        )

    async def _execute_sync(
        self,
        prompt: str,
        project: str,
        session_id: str | None = None,
    ) -> str:
        """Execute Claude Code synchronously (blocking)."""
        claude_bin = shutil.which("claude")
        if not claude_bin:
            return "Error: claude not found in PATH. Install Claude Code CLI globally: npm install -g @anthropic-ai/claude-code"

        cmd = self._build_command(prompt, project, "standard", session_id)
        timeout = self._timeout

        logger.info("claude_code (sync): project={}", project)
        stdout, stderr = await self._run_subprocess(cmd, project, timeout)

        if stderr and not stdout:
            return f"Error: Claude Code failed.\n{stderr[:2000]}"

        parsed = self._parse_result(stdout)
        if parsed.get("_parse_error"):
            raw = stdout[:_MAX_OUTPUT_CHARS] if stdout else "(no output)"
            return f"Claude Code returned non-JSON output:\n{raw}"

        self._record_stats(parsed, prompt)
        return self._format_output(parsed, "sync")

    async def cancel(self, task_id: str) -> str:
        """Cancel a running Claude Code task."""
        if not self._subagent_manager:
            return "Error: SubagentManager not available."
        return await self._subagent_manager.cancel_claude_code(task_id)

    def _resolve_project(self, project_path: str | None) -> str:
        if project_path:
            return project_path
        return self._default_project

    def _build_command(
        self,
        prompt: str,
        project: str,
        mode: str,
        session_id: str | None,
    ) -> list[str]:
        max_turns = 5 if mode == "fast" else self._max_turns
        allowed = "View,Read,Glob,Grep" if mode == "readonly" else self._allowed_tools

        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", "json",
            "--model", self._model,
            "--max-turns", str(max_turns),
            "--allowedTools", allowed,
        ]

        if session_id:
            cmd.extend(["--resume", session_id])

        return cmd

    async def _run_subprocess(
        self,
        cmd: list[str],
        cwd: str,
        timeout: int,
    ) -> tuple[str, str]:
        env = os.environ.copy()
        # Inject Claude Code auth from nanobot config
        if self.cc_config.api_key:
            env["ANTHROPIC_API_KEY"] = self.cc_config.api_key
            logger.debug("claude_code: injected ANTHROPIC_API_KEY from config")
        if self.cc_config.base_url:
            env["ANTHROPIC_BASE_URL"] = self.cc_config.base_url
            logger.debug("claude_code: injected ANTHROPIC_BASE_URL from config")
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                return "", f"Claude Code timed out after {timeout}s"
        except Exception as e:
            return "", f"Failed to start Claude Code: {e}"

        stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        return stdout, stderr

    def _parse_result(self, stdout: str) -> dict[str, Any]:
        """Parse the JSON output from Claude Code CLI."""
        stdout = stdout.strip()
        if not stdout:
            return {"_parse_error": True}

        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue

        return {"_parse_error": True}

    def _record_stats(self, parsed: dict[str, Any], prompt: str = "") -> None:
        if not self._token_stats:
            return

        usage = parsed.get("usage", {})
        cost = parsed.get("total_cost_usd", 0.0)
        duration_ms = parsed.get("duration_ms", 0)
        num_turns = parsed.get("num_turns", 0)
        session_id = parsed.get("session_id", "")
        result_text = parsed.get("result", "")
        is_error = parsed.get("is_error", False)
        stop_reason = parsed.get("stop_reason", "")

        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_creation = usage.get("cache_creation_input_tokens", 0)
        total_input = input_tokens + cache_read + cache_creation

        model_usage = parsed.get("modelUsage", {})
        model_name = self._model
        if model_usage:
            model_name = next(iter(model_usage), self._model)

        finish = "error" if is_error else stop_reason or "end_turn"

        user_msg = (
            f"[claude_code] session={session_id} turns={num_turns} "
            f"duration={duration_ms}ms\n\n--- Prompt ---\n{prompt}"
        )

        self._token_stats.record(
            model=model_name,
            provider="claude-code-cli",
            usage={
                "prompt_tokens": total_input,
                "completion_tokens": output_tokens,
                "total_tokens": total_input + output_tokens,
                "cache_creation_input_tokens": cache_creation,
                "prompt_tokens_details": {"cached_tokens": cache_read},
            },
            user_message=user_msg,
            output_content=result_text[:4000] if result_text else "",
            finish_reason=finish,
            model_role="claude_code",
            cost_usd=cost,
        )

        logger.info(
            "claude_code stats: model={} input={} output={} cache_read={} cache_create={} cost=${:.6f} turns={} duration={}ms",
            model_name, input_tokens, output_tokens, cache_read, cache_creation,
            cost, num_turns, duration_ms,
        )

    def _format_output(self, parsed: dict[str, Any], mode: str) -> str:
        is_error = parsed.get("is_error", False)
        result_text = parsed.get("result", "")
        subtype = parsed.get("subtype", "")
        num_turns = parsed.get("num_turns", 0)
        duration_ms = parsed.get("duration_ms", 0)
        cost = parsed.get("total_cost_usd", 0.0)
        session_id = parsed.get("session_id", "")

        status = "ERROR" if is_error else subtype.upper() or "SUCCESS"

        parts = [
            f"[Claude Code {status}]",
            f"Turns: {num_turns} | Duration: {duration_ms}ms | Cost: ${cost:.4f}",
        ]

        if session_id:
            parts.append(f"Session: {session_id}")

        parts.append("")

        if result_text:
            if len(result_text) > _MAX_OUTPUT_CHARS:
                result_text = result_text[:_MAX_OUTPUT_CHARS] + "\n... (truncated)"
            parts.append(result_text)
        else:
            parts.append("(no result text)")

        return "\n".join(parts)
