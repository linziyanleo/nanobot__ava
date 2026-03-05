"""Tests for MemoryTool: recall, remember, search_history, map_identity, list_persons."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nanobot.agent.categorized_memory import CategorizedMemoryStore
from nanobot.agent.tools.memory_tool import MemoryTool


def _make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "memory" / "persons").mkdir(parents=True)
    (workspace / "sessions").mkdir(parents=True)
    return workspace


def _make_tool(workspace: Path, channel: str = "cli", chat_id: str = "direct") -> MemoryTool:
    store = CategorizedMemoryStore(workspace)
    tool = MemoryTool(store)
    tool.set_context(channel, chat_id)
    return tool


def _write_session(workspace: Path, channel: str, chat_id: str, messages: list[dict]) -> None:
    path = workspace / "sessions" / f"{channel}_{chat_id}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        meta = {"_type": "metadata", "key": f"{channel}:{chat_id}", "created_at": "2026-02-25T10:00:00"}
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")
        for msg in messages:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")


def _write_identity_map(workspace: Path, persons: dict) -> None:
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML required")
    path = workspace / "memory" / "identity_map.yaml"
    path.write_text(yaml.dump({"persons": persons}, allow_unicode=True), encoding="utf-8")


# ── Basic actions ──


@pytest.mark.asyncio
async def test_recall_no_identity(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    tool = _make_tool(workspace)
    result = await tool.execute(action="recall")
    assert "No person identity" in result


@pytest.mark.asyncio
async def test_remember_and_recall(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    _write_identity_map(workspace, {
        "alice": {"display_name": "Alice", "ids": [{"channel": "cli", "id": ["direct"]}]}
    })
    tool = _make_tool(workspace)

    result = await tool.execute(action="remember", content="likes Python")
    assert "memory updated" in result.lower() or "updated" in result

    result = await tool.execute(action="recall")
    assert "likes Python" in result


@pytest.mark.asyncio
async def test_remember_source_scope(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    _write_identity_map(workspace, {
        "alice": {"display_name": "Alice", "ids": [{"channel": "cli", "id": ["direct"]}]}
    })
    tool = _make_tool(workspace)

    await tool.execute(action="remember", content="cli-specific note", scope="source")
    result = await tool.execute(action="recall", scope="source")
    assert "cli-specific note" in result


@pytest.mark.asyncio
async def test_map_identity_and_list(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    tool = _make_tool(workspace, channel="telegram", chat_id="12345")

    result = await tool.execute(action="map_identity", person="bob", display_name="Bob")
    assert "Mapped" in result

    result = await tool.execute(action="list_persons")
    assert "bob" in result.lower() or "Bob" in result


@pytest.mark.asyncio
async def test_unknown_action(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    tool = _make_tool(workspace)
    result = await tool.execute(action="nonexistent")
    assert "Unknown action" in result


# ── search_history: HISTORY.md path ──


@pytest.mark.asyncio
async def test_search_history_from_history_md(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    history = workspace / "memory" / "HISTORY.md"
    history.write_text("2026-02-25 discussed Python performance\n2026-02-24 talked about Rust\n")

    tool = _make_tool(workspace)
    result = await tool.execute(action="search_history", content="Python")
    assert "Python" in result
    assert "Rust" not in result


# ── search_history: sessions fallback ──


@pytest.mark.asyncio
async def test_search_history_fallback_to_sessions(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    _write_session(workspace, "cli", "direct", [
        {"role": "user", "content": "tell me a joke", "timestamp": "2026-02-25T19:00:00"},
        {"role": "assistant", "content": "Why did the chicken cross the road?", "timestamp": "2026-02-25T19:00:01"},
    ])

    tool = _make_tool(workspace)
    result = await tool.execute(action="search_history", content="joke")
    assert "joke" in result
    assert "2026-02-25T19:00:00" in result


@pytest.mark.asyncio
async def test_search_history_no_match(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    _write_session(workspace, "cli", "direct", [
        {"role": "user", "content": "hello", "timestamp": "2026-02-25T10:00:00"},
    ])
    tool = _make_tool(workspace)
    result = await tool.execute(action="search_history", content="nonexistent_keyword_xyz")
    assert "No matches" in result


# ── search_history: since/until time filtering ──


@pytest.mark.asyncio
async def test_search_history_since_until(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    _write_session(workspace, "cli", "direct", [
        {"role": "user", "content": "morning msg", "timestamp": "2026-02-25T08:00:00"},
        {"role": "user", "content": "afternoon msg", "timestamp": "2026-02-25T14:00:00"},
        {"role": "user", "content": "next day msg", "timestamp": "2026-02-26T09:00:00"},
    ])

    tool = _make_tool(workspace)

    result = await tool.execute(
        action="search_history", content="msg",
        since="2026-02-25", until="2026-02-26",
    )
    assert "morning msg" in result
    assert "afternoon msg" in result
    assert "next day msg" not in result


@pytest.mark.asyncio
async def test_search_history_precise_time(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    _write_session(workspace, "cli", "direct", [
        {"role": "user", "content": "early msg", "timestamp": "2026-02-25T08:00:00"},
        {"role": "user", "content": "target msg", "timestamp": "2026-02-25T10:30:00"},
        {"role": "user", "content": "late msg", "timestamp": "2026-02-25T15:00:00"},
    ])

    tool = _make_tool(workspace)

    result = await tool.execute(
        action="search_history", content="msg",
        since="2026-02-25T10:00:00", until="2026-02-25T11:00:00",
    )
    assert "target msg" in result
    assert "early msg" not in result
    assert "late msg" not in result


@pytest.mark.asyncio
async def test_search_history_time_only_no_content(tmp_path: Path) -> None:
    """content is optional when time range is provided."""
    workspace = _make_workspace(tmp_path)
    _write_session(workspace, "cli", "direct", [
        {"role": "user", "content": "hello world", "timestamp": "2026-02-25T10:00:00"},
        {"role": "assistant", "content": "hi there", "timestamp": "2026-02-25T10:00:01"},
    ])

    tool = _make_tool(workspace)
    result = await tool.execute(
        action="search_history",
        since="2026-02-25T10:00:00", until="2026-02-25T10:01:00",
    )
    assert "hello world" in result
    assert "hi there" in result


@pytest.mark.asyncio
async def test_search_history_requires_content_or_time(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    tool = _make_tool(workspace)
    result = await tool.execute(action="search_history")
    assert "Error" in result


# ── search_history: channel filtering ──


@pytest.mark.asyncio
async def test_search_history_channel_filter(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    _write_session(workspace, "telegram", "123", [
        {"role": "user", "content": "telegram msg", "timestamp": "2026-02-25T10:00:00"},
    ])
    _write_session(workspace, "cli", "direct", [
        {"role": "user", "content": "cli msg", "timestamp": "2026-02-25T10:00:00"},
    ])

    tool = _make_tool(workspace)

    result = await tool.execute(
        action="search_history", content="msg", channel="telegram",
    )
    assert "telegram msg" in result
    assert "cli msg" not in result


@pytest.mark.asyncio
async def test_search_history_channel_all(tmp_path: Path) -> None:
    """No channel filter → search all sessions."""
    workspace = _make_workspace(tmp_path)
    _write_session(workspace, "telegram", "123", [
        {"role": "user", "content": "tg hello", "timestamp": "2026-02-25T10:00:00"},
    ])
    _write_session(workspace, "cli", "direct", [
        {"role": "user", "content": "cli hello", "timestamp": "2026-02-25T10:00:00"},
    ])

    tool = _make_tool(workspace)

    result = await tool.execute(
        action="search_history", content="hello",
        since="2026-02-25", until="2026-02-26",
    )
    assert "tg hello" in result
    assert "cli hello" in result


# ── search_history: person-scoped sessions ──


@pytest.mark.asyncio
async def test_search_sessions_for_person(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    _write_identity_map(workspace, {
        "alice": {
            "display_name": "Alice",
            "ids": [
                {"channel": "telegram", "id": ["111"]},
                {"channel": "cli", "id": ["direct"]},
            ],
        }
    })
    _write_session(workspace, "telegram", "111", [
        {"role": "user", "content": "alice on telegram", "timestamp": "2026-02-25T10:00:00"},
    ])
    _write_session(workspace, "cli", "direct", [
        {"role": "user", "content": "alice on cli", "timestamp": "2026-02-25T10:00:00"},
    ])
    _write_session(workspace, "telegram", "999", [
        {"role": "user", "content": "other user msg", "timestamp": "2026-02-25T10:00:00"},
    ])

    tool = _make_tool(workspace)
    result = await tool.execute(
        action="search_history", content="alice", person="alice",
        since="2026-02-25", until="2026-02-26",
    )
    assert "alice on telegram" in result
    assert "alice on cli" in result
    assert "other user" not in result


# ── _normalize_datetime ──


def test_normalize_datetime_date_only() -> None:
    assert MemoryTool._normalize_datetime("2026-02-25") == "2026-02-25T00:00:00"


def test_normalize_datetime_full() -> None:
    assert MemoryTool._normalize_datetime("2026-02-25T10:30:00") == "2026-02-25T10:30:00"


# ── Edge cases ──


@pytest.mark.asyncio
async def test_search_sessions_truncation(tmp_path: Path) -> None:
    """Results are capped at MAX_RESULTS."""
    workspace = _make_workspace(tmp_path)
    messages = [
        {"role": "user", "content": f"msg {i}", "timestamp": f"2026-02-25T10:{i:02d}:00"}
        for i in range(30)
    ]
    _write_session(workspace, "cli", "direct", messages)

    tool = _make_tool(workspace)
    result = await tool.execute(
        action="search_history", content="msg",
        since="2026-02-25", until="2026-02-26",
    )
    assert "showing first 20" in result


@pytest.mark.asyncio
async def test_search_sessions_long_content_truncated(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    long_content = "x" * 1000
    _write_session(workspace, "cli", "direct", [
        {"role": "user", "content": long_content, "timestamp": "2026-02-25T10:00:00"},
    ])

    tool = _make_tool(workspace)
    result = await tool.execute(
        action="search_history", content="xxx",
        since="2026-02-25", until="2026-02-26",
    )
    assert "..." in result
    assert len(result) < len(long_content)
