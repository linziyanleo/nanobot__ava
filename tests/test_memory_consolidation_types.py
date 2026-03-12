"""Test MemoryStore.consolidate() handles non-string tool call arguments.

Regression test for https://github.com/HKUDS/nanobot/issues/1042
When memory consolidation receives dict values instead of strings from the LLM
tool call response, it should serialize them to JSON instead of raising TypeError.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.memory import MemoryStore
from nanobot.providers.base import LLMResponse, ToolCallRequest


def _make_session(message_count: int = 30, memory_window: int = 50):
    """Create a mock session with messages."""
    session = MagicMock()
    session.messages = [
        {"role": "user", "content": f"msg{i}", "timestamp": "2026-01-01 00:00"}
        for i in range(message_count)
    ]
    session.last_consolidated = 0
    return session


def _make_tool_response(
    history_entry,
    memory_update,
    person_memory_update=None,
    self_memory_update=None,
):
    """Create an LLMResponse with a save_memory tool call."""
    args = {
        "history_entry": history_entry,
        "memory_update": memory_update,
    }
    if person_memory_update is not None:
        args["person_memory_update"] = person_memory_update
    if self_memory_update is not None:
        args["self_memory_update"] = self_memory_update

    return LLMResponse(
        content=None,
        tool_calls=[
            ToolCallRequest(
                id="call_1",
                name="save_memory",
                arguments=args,
            )
        ],
    )


class TestMemoryConsolidationTypeHandling:
    """Test that consolidation handles various argument types correctly."""

    @pytest.mark.asyncio
    async def test_string_arguments_work(self, tmp_path: Path) -> None:
        """Normal case: LLM returns string arguments."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=_make_tool_response(
                history_entry="[2026-01-01] User discussed testing.",
                memory_update="# Memory\nUser likes testing.",
            )
        )
        session = _make_session(message_count=60)

        result = await store.consolidate(session, provider, "test-model", memory_window=50)

        assert result is True
        assert store.history_file.exists()
        assert "[2026-01-01] User discussed testing." in store.history_file.read_text()
        assert "User likes testing." in store.memory_file.read_text()

    @pytest.mark.asyncio
    async def test_dict_arguments_serialized_to_json(self, tmp_path: Path) -> None:
        """Issue #1042: LLM returns dict instead of string — must not raise TypeError."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=_make_tool_response(
                history_entry={"timestamp": "2026-01-01", "summary": "User discussed testing."},
                memory_update={"facts": ["User likes testing"], "topics": ["testing"]},
            )
        )
        session = _make_session(message_count=60)

        result = await store.consolidate(session, provider, "test-model", memory_window=50)

        assert result is True
        assert store.history_file.exists()
        history_content = store.history_file.read_text()
        parsed = json.loads(history_content.strip())
        assert parsed["summary"] == "User discussed testing."

        memory_content = store.memory_file.read_text()
        parsed_mem = json.loads(memory_content)
        assert "User likes testing" in parsed_mem["facts"]

    @pytest.mark.asyncio
    async def test_string_arguments_as_raw_json(self, tmp_path: Path) -> None:
        """Some providers return arguments as a JSON string instead of parsed dict."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()

        # Simulate arguments being a JSON string (not yet parsed)
        response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="call_1",
                    name="save_memory",
                    arguments=json.dumps({
                        "history_entry": "[2026-01-01] User discussed testing.",
                        "memory_update": "# Memory\nUser likes testing.",
                    }),
                )
            ],
        )
        provider.chat = AsyncMock(return_value=response)
        session = _make_session(message_count=60)

        result = await store.consolidate(session, provider, "test-model", memory_window=50)

        assert result is True
        assert "User discussed testing." in store.history_file.read_text()

    @pytest.mark.asyncio
    async def test_no_tool_call_returns_false(self, tmp_path: Path) -> None:
        """When LLM doesn't use the save_memory tool, return False."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=LLMResponse(content="I summarized the conversation.", tool_calls=[])
        )
        session = _make_session(message_count=60)

        result = await store.consolidate(session, provider, "test-model", memory_window=50)

        assert result is False
        assert not store.history_file.exists()

    @pytest.mark.asyncio
    async def test_skips_when_few_messages(self, tmp_path: Path) -> None:
        """Consolidation should be a no-op when messages < keep_count."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()
        session = _make_session(message_count=10)

        result = await store.consolidate(session, provider, "test-model", memory_window=50)

        assert result is True
        provider.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_arguments_extracts_first_dict(self, tmp_path: Path) -> None:
        """Some providers return arguments as a list - extract first element if it's a dict."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()

        # Simulate arguments being a list containing a dict
        response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="call_1",
                    name="save_memory",
                    arguments=[{
                        "history_entry": "[2026-01-01] User discussed testing.",
                        "memory_update": "# Memory\nUser likes testing.",
                    }],
                )
            ],
        )
        provider.chat = AsyncMock(return_value=response)
        session = _make_session(message_count=60)

        result = await store.consolidate(session, provider, "test-model", memory_window=50)

        assert result is True
        assert "User discussed testing." in store.history_file.read_text()
        assert "User likes testing." in store.memory_file.read_text()

    @pytest.mark.asyncio
    async def test_list_arguments_empty_list_returns_false(self, tmp_path: Path) -> None:
        """Empty list arguments should return False."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()

        response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="call_1",
                    name="save_memory",
                    arguments=[],
                )
            ],
        )
        provider.chat = AsyncMock(return_value=response)
        session = _make_session(message_count=60)

        result = await store.consolidate(session, provider, "test-model", memory_window=50)

        assert result is False

    @pytest.mark.asyncio
    async def test_list_arguments_non_dict_content_returns_false(self, tmp_path: Path) -> None:
        """List with non-dict content should return False."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()

        response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="call_1",
                    name="save_memory",
                    arguments=["string", "content"],
                )
            ],
        )
        provider.chat = AsyncMock(return_value=response)
        session = _make_session(message_count=60)

        result = await store.consolidate(session, provider, "test-model", memory_window=50)

        assert result is False

    @pytest.mark.asyncio
    async def test_person_memory_update_sent_to_categorized_store(self, tmp_path: Path) -> None:
        """Person memory should use dedicated person field, not global memory_update."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=_make_tool_response(
                history_entry="[2026-01-01] User discussed preferences.",
                memory_update="# Global Memory\n- Shared policy",
                person_memory_update="# Leo Memory\n- 喜欢简洁回复",
            )
        )
        session = _make_session(message_count=60)
        session.key = "cli:direct"
        categorized = MagicMock()
        categorized.resolve_person.return_value = "leo"

        result = await store.consolidate(
            session,
            provider,
            "test-model",
            memory_window=50,
            categorized_store=categorized,
        )

        assert result is True
        categorized.on_consolidate.assert_called_once_with(
            "cli",
            "direct",
            history_entry="[2026-01-01] User discussed preferences.",
            person_memory_facts="# Leo Memory\n- 喜欢简洁回复",
        )

    @pytest.mark.asyncio
    async def test_my_memory_update_written(self, tmp_path: Path) -> None:
        """My self memory should be persisted when self_memory_update is provided."""
        store = MemoryStore(tmp_path)
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=_make_tool_response(
                history_entry="[2026-01-01] Updated My self memory.",
                memory_update="# Global Memory\n- Shared fact",
                self_memory_update="# My Self Memory\n- 擅长结构化总结",
            )
        )
        session = _make_session(message_count=60)
        session.key = "cli:direct"

        result = await store.consolidate(session, provider, "test-model", memory_window=50)

        assert result is True
        assert store.self_memory_file.exists()
        assert "擅长结构化总结" in store.self_memory_file.read_text(encoding="utf-8")

    def test_stability_rules_remove_history_style_and_dedupe(self) -> None:
        """Rule layer should drop history-style lines and dedupe bullets."""
        content = "\n".join([
            "# Long-term Memory",
            "- 喜欢简洁回复",
            "- 喜欢简洁回复",
            "[2026-02-27 11:51] 这是时间线条目，不应进入 MEMORY",
        ])

        cleaned = MemoryStore._apply_stability_rules(content, scope="person")

        assert cleaned.count("喜欢简洁回复") == 1
        assert "2026-02-27 11:51" not in cleaned
