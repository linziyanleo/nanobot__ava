"""Tests for context_patch — history processing + memory injection."""

from unittest.mock import MagicMock, patch

import pytest

from nanobot.agent.context import ContextBuilder


@pytest.fixture(autouse=True)
def _restore_build_messages():
    """Save and restore ContextBuilder.build_messages."""
    original = ContextBuilder.build_messages
    yield
    ContextBuilder.build_messages = original


class TestContextPatch:
    def test_patch_applies_without_error(self):
        """apply_context_patch runs without error."""
        from ava.patches.context_patch import apply_context_patch

        result = apply_context_patch()
        assert "contextbuilder" in result.lower() or "patched" in result.lower()

    def test_build_messages_replaced(self):
        """build_messages has _ava_patched marker after patch."""
        from ava.patches.context_patch import apply_context_patch

        apply_context_patch()
        assert getattr(ContextBuilder.build_messages, "_ava_patched", False) is True

    def test_idempotent(self):
        """Calling patch twice doesn't double-wrap."""
        from ava.patches.context_patch import apply_context_patch

        r1 = apply_context_patch()
        r2 = apply_context_patch()
        assert "skipped" in r2.lower()

    def test_summarizer_called_when_available(self):
        """Summarizer is invoked when _agent_loop has one."""
        from ava.patches.context_patch import apply_context_patch
        apply_context_patch()

        # Create a mock ContextBuilder with _agent_loop
        ctx = ContextBuilder.__new__(ContextBuilder)
        ctx.workspace = MagicMock()
        ctx.memory = MagicMock()
        ctx.memory.get_memory_context.return_value = ""
        ctx.skills = MagicMock()
        ctx.skills.get_always_skills.return_value = []
        ctx.skills.build_skills_summary.return_value = ""

        mock_loop = MagicMock()
        mock_summarizer = MagicMock()
        mock_summarizer.summarize.return_value = [{"role": "user", "content": "hi"}]
        mock_loop.history_summarizer = mock_summarizer
        mock_loop.history_compressor = None
        mock_loop.categorized_memory = None
        ctx._agent_loop = mock_loop

        history = [
            {"role": "user", "content": "old msg"},
            {"role": "assistant", "content": "old reply"},
        ]

        ctx.build_messages(history, "new msg", channel="tg", chat_id="123")
        mock_summarizer.summarize.assert_called_once_with(history)

    def test_compressor_called_when_available(self):
        """Compressor is invoked after summarizer."""
        from ava.patches.context_patch import apply_context_patch
        apply_context_patch()

        ctx = ContextBuilder.__new__(ContextBuilder)
        ctx.workspace = MagicMock()
        ctx.memory = MagicMock()
        ctx.memory.get_memory_context.return_value = ""
        ctx.skills = MagicMock()
        ctx.skills.get_always_skills.return_value = []
        ctx.skills.build_skills_summary.return_value = ""

        mock_loop = MagicMock()
        mock_loop.history_summarizer = None
        mock_compressor = MagicMock()
        mock_compressor.compress.return_value = [{"role": "user", "content": "hi"}]
        mock_loop.history_compressor = mock_compressor
        mock_loop.categorized_memory = None
        ctx._agent_loop = mock_loop

        history = [{"role": "user", "content": "old"}]
        ctx.build_messages(history, "new msg", channel="tg", chat_id="123")
        mock_compressor.compress.assert_called_once()

    def test_memory_injected_into_system_prompt(self):
        """Categorized memory context is appended to system prompt."""
        from ava.patches.context_patch import apply_context_patch
        apply_context_patch()

        ctx = ContextBuilder.__new__(ContextBuilder)
        ctx.workspace = MagicMock()
        ctx.memory = MagicMock()
        ctx.memory.get_memory_context.return_value = ""
        ctx.skills = MagicMock()
        ctx.skills.get_always_skills.return_value = []
        ctx.skills.build_skills_summary.return_value = ""

        mock_loop = MagicMock()
        mock_loop.history_summarizer = None
        mock_loop.history_compressor = None
        mock_cat_mem = MagicMock()
        mock_cat_mem.get_combined_context.return_value = "用户偏好：喜欢猫咪"
        mock_loop.categorized_memory = mock_cat_mem
        ctx._agent_loop = mock_loop

        messages = ctx.build_messages([], "hi", channel="tg", chat_id="123")

        assert messages[0]["role"] == "system"
        assert "Personal Memory" in messages[0]["content"]
        assert "猫咪" in messages[0]["content"]

    def test_no_loop_ref_passthrough(self):
        """Without _agent_loop, build_messages works normally."""
        from ava.patches.context_patch import apply_context_patch
        apply_context_patch()

        ctx = ContextBuilder.__new__(ContextBuilder)
        ctx.workspace = MagicMock()
        ctx.memory = MagicMock()
        ctx.memory.get_memory_context.return_value = ""
        ctx.skills = MagicMock()
        ctx.skills.get_always_skills.return_value = []
        ctx.skills.build_skills_summary.return_value = ""
        # No _agent_loop set

        messages = ctx.build_messages([], "hello")
        assert messages[0]["role"] == "system"
        assert len(messages) >= 2  # system + user
