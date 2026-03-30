"""Tests for HistoryCompressor, especially tool_call group boundary safety."""

from ava.agent.history_compressor import HistoryCompressor


def _assert_no_orphans(history: list[dict]) -> None:
    """Assert every tool result in history has a matching assistant tool_call."""
    declared = {
        tc["id"]
        for m in history if m.get("role") == "assistant"
        for tc in (m.get("tool_calls") or [])
    }
    orphans = [
        m.get("tool_call_id") for m in history
        if m.get("role") == "tool" and m.get("tool_call_id")
        and str(m["tool_call_id"]) not in declared
    ]
    assert orphans == [], f"orphan tool_call_ids: {orphans}"


def _make_tool_turn(user_text: str, tool_id: str) -> list[dict]:
    """Create a complete tool turn: user, assistant(tool_calls), tool, assistant(final)."""
    return [
        {"role": "user", "content": user_text},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": tool_id, "type": "function", "function": {"name": "search", "arguments": "{}"}},
            ],
        },
        {"role": "tool", "tool_call_id": tool_id, "name": "search", "content": "result"},
        {"role": "assistant", "content": f"Answer to {user_text}"},
    ]


def test_protected_recent_does_not_orphan_tool_result():
    """protected_recent_messages boundary must not split a tool_call group."""
    history = (
        _make_tool_turn("q1", "call_1")
        + _make_tool_turn("q2", "call_2")
        + _make_tool_turn("q3", "call_3")
    )
    # 12 msgs total, protected_recent_messages=6 → naive split at index 6 (tool of turn 2)
    c = HistoryCompressor(max_chars=100000, protected_recent_messages=6)
    result = c.compress(history, "test query")
    _assert_no_orphans(result)


def test_protected_boundary_on_tool_message():
    """If boundary lands on a tool message, it must be pulled back."""
    history = _make_tool_turn("q1", "call_1") + _make_tool_turn("q2", "call_2")
    # 8 msgs, protected_recent_messages=6 → split at index 2 which is tool(call_1)
    c = HistoryCompressor(max_chars=100000, protected_recent_messages=6)
    result = c.compress(history, "test")
    _assert_no_orphans(result)


def test_protected_boundary_on_assistant_with_tool_calls():
    """If boundary lands on assistant with tool_calls, it must be pulled back."""
    history = _make_tool_turn("q1", "call_1") + _make_tool_turn("q2", "call_2")
    # 8 msgs, protected_recent_messages=7 → split at index 1 (assistant with tool_calls)
    c = HistoryCompressor(max_chars=100000, protected_recent_messages=7)
    result = c.compress(history, "test")
    _assert_no_orphans(result)


def test_compress_small_history_no_split():
    """History smaller than protected_recent_messages is returned as-is."""
    history = _make_tool_turn("q1", "call_1")
    c = HistoryCompressor(max_chars=100000, protected_recent_messages=20)
    result = c.compress(history, "test")
    _assert_no_orphans(result)
    assert len(result) == 4
