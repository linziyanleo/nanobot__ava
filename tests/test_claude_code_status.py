from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from nanobot.agent.commands import CommandRegistry, register_builtin_commands
from nanobot.agent.subagent import SubagentManager
from nanobot.bus.queue import MessageBus


def _make_manager(workspace: Path) -> SubagentManager:
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    return SubagentManager(provider=provider, workspace=workspace, bus=MessageBus())


def test_get_claude_code_status_filters_by_session(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path)
    mgr._create_claude_code_state(
        task_id="cc_a",
        session_key="cli:direct",
        prompt="task a",
        project_path=str(tmp_path),
        mode="standard",
    )
    mgr._create_claude_code_state(
        task_id="cc_b",
        session_key="telegram:1",
        prompt="task b",
        project_path=str(tmp_path),
        mode="fast",
    )
    mgr._set_claude_code_state("cc_a", status="running", phase="editing")
    mgr._set_claude_code_state("cc_b", status="done", phase="done")

    status = mgr.get_claude_code_status(session_key="cli:direct")
    assert status["total"] == 1
    assert status["running"] == 1
    assert status["tasks"][0]["task_id"] == "cc_a"
    assert status["tasks"][0]["phase"] == "editing"


def test_stream_event_updates_todo_and_usage_estimate(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path)
    mgr._create_claude_code_state(
        task_id="cc_todo",
        session_key="cli:direct",
        prompt="todo test",
        project_path=str(tmp_path),
        mode="standard",
    )

    mgr._apply_claude_stream_event(
        "cc_todo",
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_start",
                "content_block": {"type": "tool_use", "name": "TodoWrite"},
            },
        },
    )
    mgr._apply_claude_stream_event(
        "cc_todo",
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "delta": {
                    "type": "input_json_delta",
                    "partial_json": (
                        '{"todos":[{"content":"Implement status API","status":"in_progress"}],'
                        '"merge":true}'
                    ),
                },
            },
        },
    )
    mgr._apply_claude_stream_event(
        "cc_todo",
        {
            "type": "result",
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 120,
                "cache_read_input_tokens": 40,
                "cache_creation_input_tokens": 10,
            },
            "session_id": "sid-1",
            "num_turns": 3,
            "duration_ms": 4200,
            "total_cost_usd": 0.0123,
        },
    )

    status = mgr.get_claude_code_status(task_id="cc_todo", verbose=True)
    assert status["total"] == 1
    task = status["tasks"][0]
    assert task["last_tool_name"] == "TodoWrite"
    assert task["todo_summary"]["in_progress"] == 1
    assert task["context_used_est"] == 1170
    assert task["context_remaining_est"] == 198830
    assert task["session_id"] == "sid-1"


def test_build_claude_code_command_uses_stream_json_and_todowrite(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path)
    cmd = mgr._build_claude_code_command(
        prompt="hello",
        project=str(tmp_path),
        mode="standard",
        session_id=None,
    )

    assert "--output-format" in cmd
    idx = cmd.index("--output-format")
    assert cmd[idx + 1] == "stream-json"

    allowed_idx = cmd.index("--allowedTools")
    assert "TodoWrite" in cmd[allowed_idx + 1]


def test_cc_status_command_is_registered() -> None:
    registry = CommandRegistry()
    register_builtin_commands(registry, MagicMock())
    assert registry.match("/cc_status") is not None
