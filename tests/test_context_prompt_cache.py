"""Tests for cache-friendly prompt construction."""

from __future__ import annotations

from datetime import datetime as real_datetime
from pathlib import Path
import datetime as datetime_module

from nanobot.agent.context import ContextBuilder
from nanobot.agent.history_compressor import HistoryCompressor


class _FakeDatetime(real_datetime):
    current = real_datetime(2026, 2, 24, 13, 59)

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return cls.current


def _make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    return workspace


def test_system_prompt_stays_stable_when_clock_changes(tmp_path, monkeypatch) -> None:
    """System prompt should not change just because wall clock minute changes."""
    monkeypatch.setattr(datetime_module, "datetime", _FakeDatetime)

    workspace = _make_workspace(tmp_path)
    builder = ContextBuilder(workspace)

    _FakeDatetime.current = real_datetime(2026, 2, 24, 13, 59)
    prompt1 = builder.build_system_prompt()

    _FakeDatetime.current = real_datetime(2026, 2, 24, 14, 0)
    prompt2 = builder.build_system_prompt()

    assert prompt1 == prompt2


def test_runtime_context_is_separate_untrusted_user_message(tmp_path) -> None:
    """Runtime metadata should be merged with the user message."""
    workspace = _make_workspace(tmp_path)
    builder = ContextBuilder(workspace)

    messages = builder.build_messages(
        history=[],
        current_message="Return exactly: OK",
        channel="cli",
        chat_id="direct",
    )

    assert messages[0]["role"] == "system"
    assert "## Current Session" not in messages[0]["content"]

    # Runtime context is now merged with user message into a single message
    assert messages[-1]["role"] == "user"
    user_content = messages[-1]["content"]
    assert isinstance(user_content, str)
    assert ContextBuilder._RUNTIME_CONTEXT_TAG in user_content
    assert "Current Time:" in user_content
    assert "Channel: cli" in user_content
    assert "Chat ID: direct" in user_content
    assert "Return exactly: OK" in user_content


def test_history_compressor_shortens_auto_backfill_placeholders() -> None:
    compressor = HistoryCompressor(max_chars=5000, recent_turns=6, protected_recent_messages=0)
    history = [
        {"role": "user", "content": "上一轮问题"},
        {
            "role": "assistant",
            "content": "[auto-backfill] This historical turn had no final assistant reply.",
            "metadata": {"auto_backfill": True},
        },
        {"role": "user", "content": "当前问题"},
        {"role": "assistant", "content": "当前回复"},
    ]

    compressed = compressor.compress(history, current_message="当前问题")
    contents = [m.get("content") for m in compressed if m.get("role") == "assistant"]

    assert "[bf]" in contents
    assert all(not (isinstance(c, str) and c.startswith("[auto-backfill]")) for c in contents)


def test_history_compressor_keeps_recent_and_relevant_old_turns() -> None:
    compressor = HistoryCompressor(
        max_chars=5000,
        recent_turns=2,
        min_recent_turns=2,
        max_old_turns=1,
        protected_recent_messages=0,
    )
    history: list[dict] = []

    for i in range(4):
        history.append({"role": "user", "content": f"聊游戏{i}"})
        history.append({"role": "assistant", "content": f"游戏回复{i}"})

    history.append({"role": "user", "content": "体重记录目标80kg"})
    history.append({"role": "assistant", "content": "已记录体重目标"})

    history.append({"role": "user", "content": "今天天气怎么样"})
    history.append({"role": "assistant", "content": "晴天"})
    history.append({"role": "user", "content": "午饭吃什么"})
    history.append({"role": "assistant", "content": "清淡一点"})

    compressed = compressor.compress(history, current_message="今天体重是多少")
    users = [m.get("content") for m in compressed if m.get("role") == "user"]

    assert "体重记录目标80kg" in users
    assert "今天天气怎么样" in users
    assert "午饭吃什么" in users
    assert "聊游戏0" not in users
