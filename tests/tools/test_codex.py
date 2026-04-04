"""Tests for CodexTool — OpenAI Codex CLI integration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ava.tools.codex import CodexTool, _CODEX_SUBCMD


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def codex_tool(workspace: Path) -> CodexTool:
    return CodexTool(
        workspace=workspace,
        token_stats=None,
        default_project=str(workspace),
        model="gpt-5.4",
        timeout=60,
    )


@pytest.fixture
def codex_tool_with_store(workspace: Path) -> CodexTool:
    store = MagicMock()
    store.submit_coding_task = MagicMock(return_value="task_abc123")
    store.cancel = AsyncMock(return_value="Cancelled task task_abc123")
    return CodexTool(
        workspace=workspace,
        token_stats=MagicMock(),
        default_project=str(workspace),
        model="gpt-5.4",
        timeout=60,
        task_store=store,
    )


# ── Properties ──────────────────────────────────────────────────────

class TestProperties:
    def test_name(self, codex_tool: CodexTool):
        assert codex_tool.name == "codex"

    def test_description_contains_codex(self, codex_tool: CodexTool):
        assert "Codex" in codex_tool.description

    def test_parameters_schema(self, codex_tool: CodexTool):
        params = codex_tool.parameters
        assert params["type"] == "object"
        assert "prompt" in params["properties"]
        assert "prompt" in params["required"]
        assert "mode" in params["properties"]
        mode_enum = params["properties"]["mode"]["enum"]
        assert "fast" in mode_enum
        assert "standard" in mode_enum
        assert "readonly" in mode_enum
        assert "sync" not in mode_enum


# ── Context ─────────────────────────────────────────────────────────

class TestContext:
    def test_default_context(self, codex_tool: CodexTool):
        assert codex_tool._channel == "cli"
        assert codex_tool._chat_id == "direct"
        assert codex_tool._session_key == "cli:direct"

    def test_set_context(self, codex_tool: CodexTool):
        codex_tool.set_context("telegram", "12345")
        assert codex_tool._channel == "telegram"
        assert codex_tool._chat_id == "12345"
        assert codex_tool._session_key == "telegram:12345"

    def test_set_context_with_session_key(self, codex_tool: CodexTool):
        codex_tool.set_context("console", "user1", session_key="console:session42")
        assert codex_tool._session_key == "console:session42"


# ── Command Building ────────────────────────────────────────────────

class TestBuildCommand:
    def test_standard_mode(self, codex_tool: CodexTool):
        cmd = codex_tool._build_command("fix bug", "/tmp/proj", "standard")
        assert cmd[0] == "codex"
        assert cmd[1] == _CODEX_SUBCMD
        assert cmd[2] == "fix bug"
        assert "--json" in cmd
        assert "-C" in cmd
        idx = cmd.index("-C")
        assert cmd[idx + 1] == "/tmp/proj"
        assert "-m" in cmd
        idx_m = cmd.index("-m")
        assert cmd[idx_m + 1] == "gpt-5.4"
        assert "--full-auto" in cmd

    def test_readonly_mode(self, codex_tool: CodexTool):
        cmd = codex_tool._build_command("analyze", "/tmp/proj", "readonly")
        assert "-s" in cmd
        idx_s = cmd.index("-s")
        assert cmd[idx_s + 1] == "read-only"
        assert "--full-auto" not in cmd

    def test_fast_mode(self, codex_tool: CodexTool):
        cmd = codex_tool._build_command("quick fix", "/tmp/proj", "fast")
        assert "--full-auto" in cmd

    def test_no_model(self, workspace: Path):
        tool = CodexTool(workspace=workspace, model="")
        cmd = tool._build_command("task", "/tmp/proj", "standard")
        assert "-m" not in cmd


# ── JSONL Parsing ───────────────────────────────────────────────────

class TestParseJsonl:
    def test_basic_success(self, codex_tool: CodexTool):
        jsonl = (
            '{"type":"thread.started","thread_id":"tid-001"}\n'
            '{"type":"turn.started"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"Done."}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":50,"output_tokens":30}}\n'
        )
        result = codex_tool._parse_jsonl(jsonl)
        assert result["thread_id"] == "tid-001"
        assert result["result"] == "Done."
        assert result["is_error"] is False
        assert result["num_turns"] == 1
        assert result["usage"]["input_tokens"] == 100
        assert result["usage"]["cached_input_tokens"] == 50
        assert result["usage"]["output_tokens"] == 30

    def test_multiple_turns(self, codex_tool: CodexTool):
        jsonl = (
            '{"type":"thread.started","thread_id":"tid-002"}\n'
            '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":0,"output_tokens":50}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":200,"cached_input_tokens":100,"output_tokens":80}}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"All done."}}\n'
        )
        result = codex_tool._parse_jsonl(jsonl)
        assert result["num_turns"] == 2
        assert result["usage"]["input_tokens"] == 300
        assert result["usage"]["cached_input_tokens"] == 100
        assert result["usage"]["output_tokens"] == 130

    def test_turn_failed(self, codex_tool: CodexTool):
        jsonl = (
            '{"type":"thread.started","thread_id":"tid-003"}\n'
            '{"type":"turn.failed","error":{"message":"rate limit exceeded"}}\n'
        )
        result = codex_tool._parse_jsonl(jsonl)
        assert result["is_error"] is True
        assert result["error_message"] == "rate limit exceeded"

    def test_error_event(self, codex_tool: CodexTool):
        jsonl = '{"type":"error","message":"connection failed"}\n'
        result = codex_tool._parse_jsonl(jsonl)
        assert result["is_error"] is True
        assert "connection failed" in result["error_message"]

    def test_empty_stdout(self, codex_tool: CodexTool):
        assert codex_tool._parse_jsonl("")["_parse_error"] is True
        assert codex_tool._parse_jsonl("   ")["_parse_error"] is True
        assert codex_tool._parse_jsonl(None)["_parse_error"] is True

    def test_no_agent_message_no_error(self, codex_tool: CodexTool):
        jsonl = '{"type":"thread.started","thread_id":"tid-004"}\n'
        result = codex_tool._parse_jsonl(jsonl)
        assert result.get("_parse_error") is True

    def test_malformed_lines_skipped(self, codex_tool: CodexTool):
        jsonl = (
            'not json\n'
            '{"type":"thread.started","thread_id":"tid-005"}\n'
            'another bad line\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"Result"}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":10,"cached_input_tokens":0,"output_tokens":5}}\n'
        )
        result = codex_tool._parse_jsonl(jsonl)
        assert result["thread_id"] == "tid-005"
        assert result["result"] == "Result"
        assert result["is_error"] is False

    def test_last_agent_message_wins(self, codex_tool: CodexTool):
        jsonl = (
            '{"type":"item.completed","item":{"type":"agent_message","text":"first"}}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"second"}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":10,"cached_input_tokens":0,"output_tokens":5}}\n'
        )
        result = codex_tool._parse_jsonl(jsonl)
        assert result["result"] == "second"


# ── Output Formatting ───────────────────────────────────────────────

class TestFormatOutput:
    def test_success_format(self, codex_tool: CodexTool):
        parsed = {
            "thread_id": "tid-010",
            "result": "Task completed successfully.",
            "is_error": False,
            "num_turns": 3,
            "duration_ms": 5000,
            "error_message": "",
        }
        output = codex_tool._format_output(parsed, "standard")
        assert "[Codex SUCCESS]" in output
        assert "Turns: 3" in output
        assert "Duration: 5000ms" in output
        assert "Thread: tid-010" in output
        assert "Task completed successfully." in output

    def test_error_format(self, codex_tool: CodexTool):
        parsed = {
            "thread_id": "tid-011",
            "result": "",
            "is_error": True,
            "error_message": "Rate limit exceeded",
            "num_turns": 1,
            "duration_ms": 1000,
        }
        output = codex_tool._format_output(parsed, "standard")
        assert "[Codex ERROR]" in output
        assert "Rate limit exceeded" in output

    def test_long_output_truncated(self, codex_tool: CodexTool):
        long_text = "x" * 50000
        parsed = {
            "thread_id": "",
            "result": long_text,
            "is_error": False,
            "num_turns": 1,
            "duration_ms": 1000,
            "error_message": "",
        }
        output = codex_tool._format_output(parsed, "standard")
        assert "chars omitted" in output
        assert len(output) < 50000


# ── Execute Integration ─────────────────────────────────────────────

class TestExecute:
    @pytest.mark.asyncio
    async def test_no_codex_binary(self, codex_tool: CodexTool):
        with patch("shutil.which", return_value=None):
            result = await codex_tool.execute(prompt="test")
            assert "Error" in result
            assert "codex not found" in result

    @pytest.mark.asyncio
    async def test_nonexistent_project(self, codex_tool: CodexTool):
        with patch("shutil.which", return_value="/usr/bin/codex"):
            result = await codex_tool.execute(
                prompt="test", project_path="/nonexistent/path"
            )
            assert "Error" in result
            assert "does not exist" in result

    @pytest.mark.asyncio
    async def test_submit_to_task_store(self, codex_tool_with_store: CodexTool):
        with patch("shutil.which", return_value="/usr/bin/codex"):
            result = await codex_tool_with_store.execute(prompt="fix bug")
            assert "task_abc123" in result
            store = codex_tool_with_store._task_store
            store.submit_coding_task.assert_called_once()
            call_kwargs = store.submit_coding_task.call_args
            assert call_kwargs.kwargs["prompt"] == "fix bug"
            assert call_kwargs.kwargs["origin_session_key"] == "cli:direct"

    @pytest.mark.asyncio
    async def test_fast_mode_timeout(self, codex_tool_with_store: CodexTool):
        with patch("shutil.which", return_value="/usr/bin/codex"):
            await codex_tool_with_store.execute(prompt="quick fix", mode="fast")
            call_kwargs = codex_tool_with_store._task_store.submit_coding_task.call_args
            assert call_kwargs.kwargs["timeout"] == 120

    @pytest.mark.asyncio
    async def test_standard_mode_timeout(self, codex_tool_with_store: CodexTool):
        with patch("shutil.which", return_value="/usr/bin/codex"):
            await codex_tool_with_store.execute(prompt="big task", mode="standard")
            call_kwargs = codex_tool_with_store._task_store.submit_coding_task.call_args
            assert call_kwargs.kwargs["timeout"] == 60  # tool's _timeout


# ── Cancel ──────────────────────────────────────────────────────────

class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_delegates_to_store(self, codex_tool_with_store: CodexTool):
        result = await codex_tool_with_store.cancel("task_abc123")
        assert "Cancelled" in result

    @pytest.mark.asyncio
    async def test_cancel_without_store(self, codex_tool: CodexTool):
        result = await codex_tool.cancel("task_abc123")
        assert "Error" in result


# ── Record Stats ────────────────────────────────────────────────────

class TestRecordStats:
    def test_records_to_token_stats(self, codex_tool_with_store: CodexTool):
        parsed = {
            "thread_id": "tid-020",
            "result": "Done",
            "is_error": False,
            "num_turns": 2,
            "duration_ms": 3000,
            "usage": {
                "input_tokens": 500,
                "cached_input_tokens": 200,
                "output_tokens": 100,
            },
        }
        codex_tool_with_store._record_stats(parsed, "fix bug")
        ts = codex_tool_with_store._token_stats
        ts.record.assert_called_once()
        call_kwargs = ts.record.call_args.kwargs
        assert call_kwargs["model"] == "gpt-5.4"
        assert call_kwargs["provider"] == "codex-cli"
        assert call_kwargs["model_role"] == "codex"
        assert call_kwargs["usage"]["prompt_tokens"] == 700  # 500 + 200
        assert call_kwargs["usage"]["completion_tokens"] == 100
        assert call_kwargs["finish_reason"] == "end_turn"

    def test_records_error_finish_reason(self, codex_tool_with_store: CodexTool):
        parsed = {
            "thread_id": "tid-021",
            "result": "",
            "is_error": True,
            "num_turns": 1,
            "duration_ms": 1000,
            "usage": {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0},
        }
        codex_tool_with_store._record_stats(parsed, "fail task")
        call_kwargs = codex_tool_with_store._token_stats.record.call_args.kwargs
        assert call_kwargs["finish_reason"] == "error"

    def test_no_stats_when_collector_none(self, codex_tool: CodexTool):
        parsed = {
            "usage": {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0},
        }
        codex_tool._record_stats(parsed, "test")  # should not raise


# ── Project Resolution ──────────────────────────────────────────────

class TestResolveProject:
    def test_explicit_path(self, codex_tool: CodexTool):
        assert codex_tool._resolve_project("/some/path") == "/some/path"

    def test_default_project(self, codex_tool: CodexTool, workspace: Path):
        assert codex_tool._resolve_project(None) == str(workspace)


# ── Config Injection ────────────────────────────────────────────────

class TestConfigInjection:
    def test_default_config(self, codex_tool: CodexTool):
        assert codex_tool._codex_config.api_key == ""
        assert codex_tool._codex_config.api_base == ""

    def test_custom_config(self, workspace: Path):
        cfg = SimpleNamespace(api_key="sk-test", api_base="https://custom.api")
        tool = CodexTool(workspace=workspace, codex_config=cfg)
        assert tool._codex_config.api_key == "sk-test"
        assert tool._codex_config.api_base == "https://custom.api"


# ── Tools Patch Integration ─────────────────────────────────────────

class TestToolsPatchIntegration:
    def test_codex_import_in_tools_patch(self):
        """CodexTool is imported in tools_patch."""
        import inspect
        from ava.patches.tools_patch import apply_tools_patch

        source = inspect.getsource(apply_tools_patch)
        assert "CodexTool" in source

    def test_codex_conditional_registration(self):
        """CodexTool registration is conditional on CLI or api_key."""
        import inspect
        from ava.patches.tools_patch import apply_tools_patch

        source = inspect.getsource(apply_tools_patch)
        assert 'which("codex")' in source
        assert "codex_api_key" in source or "openai_codex" in source

    def test_codex_in_loop_patch_backfill(self):
        """loop_patch backfills _task_store for codex tool."""
        import inspect
        from ava.patches.loop_patch import apply_loop_patch

        source = inspect.getsource(apply_loop_patch)
        assert '"codex"' in source or "'codex'" in source
