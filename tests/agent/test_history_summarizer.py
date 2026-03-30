"""Tests for HistorySummarizer, especially tool_call group boundary safety."""

from ava.agent.history_summarizer import HistorySummarizer


def _assert_no_orphans(history: list[dict]) -> None:
    """Assert every tool result in history has a matching assistant tool_call."""
    declared = {
        tc["id"]
        for m in history if m.get("role") == "assistant"
        for tc in (m.get("tool_calls") or [])
    }
    orphans = [
        m.get("tool_call_id") for m in history
        if m.get("role") == "tool" and m.get("tool_call_id") not in declared
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


def test_protect_recent_does_not_orphan_tool_result():
    """protect_recent boundary must not split a tool_call group."""
    # Build history: 3 complete tool turns (4 msgs each = 12 msgs total)
    history = (
        _make_tool_turn("q1", "call_1")
        + _make_tool_turn("q2", "call_2")
        + _make_tool_turn("q3", "call_3")
    )
    # protect_recent=6 would naively split at index 6 (middle of turn 2's tool group)
    s = HistorySummarizer(enabled=True, protect_recent=6)
    result = s.summarize(history)
    _assert_no_orphans(result)


def test_protect_recent_boundary_on_tool_message():
    """If boundary lands exactly on a tool message, it should be pulled back."""
    history = (
        _make_tool_turn("q1", "call_1")
        + _make_tool_turn("q2", "call_2")
    )
    # 8 msgs total, protect_recent=5 → split at index 3 which is assistant(final) of turn 1
    # But protect_recent=6 → split at index 2 which is tool(call_1) → must pull back
    s = HistorySummarizer(enabled=True, protect_recent=6)
    result = s.summarize(history)
    _assert_no_orphans(result)


def test_protect_recent_boundary_on_assistant_with_tool_calls():
    """If boundary lands on assistant with tool_calls, it should be pulled back."""
    history = (
        _make_tool_turn("q1", "call_1")
        + _make_tool_turn("q2", "call_2")
    )
    # 8 msgs, protect_recent=7 → split at index 1 which is assistant(tool_calls) → pull back to 0
    s = HistorySummarizer(enabled=True, protect_recent=7)
    result = s.summarize(history)
    _assert_no_orphans(result)


def test_summarize_without_protect_recent():
    """With protect_recent=0, all messages are summarized (no orphan risk)."""
    history = _make_tool_turn("q1", "call_1") + _make_tool_turn("q2", "call_2")
    s = HistorySummarizer(enabled=True, protect_recent=0)
    result = s.summarize(history)
    _assert_no_orphans(result)
    # All turns should be compressed to [user, assistant] pairs
    assert all(m.get("role") in ("user", "assistant") for m in result)
    assert not any(m.get("tool_calls") for m in result)
