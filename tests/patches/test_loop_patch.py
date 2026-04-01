"""Tests for loop_patch — AgentLoop attribute injection + token stats."""

from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

from nanobot.agent.loop import AgentLoop


@pytest.fixture(autouse=True)
def _restore_agent_loop():
    """Save and restore AgentLoop methods to avoid polluting other tests."""
    orig_init = AgentLoop.__init__
    orig_set_tool_context = AgentLoop._set_tool_context
    orig_run_agent_loop = AgentLoop._run_agent_loop
    orig_save_turn = AgentLoop._save_turn
    orig_process = AgentLoop._process_message
    yield
    AgentLoop.__init__ = orig_init
    AgentLoop._set_tool_context = orig_set_tool_context
    AgentLoop._run_agent_loop = orig_run_agent_loop
    AgentLoop._save_turn = orig_save_turn
    AgentLoop._process_message = orig_process


class TestLoopPatch:
    def test_set_shared_db(self):
        """T3.7: set_shared_db stores the db reference."""
        from ava.patches.loop_patch import set_shared_db, _get_or_create_db

        mock_db = MagicMock()
        set_shared_db(mock_db)
        result = _get_or_create_db("/tmp/test")
        assert result is mock_db

        # Cleanup
        set_shared_db(None)

    def test_get_or_create_db_fallback(self, tmp_path):
        """T3.7b: _get_or_create_db creates new db when shared is None."""
        from ava.patches.loop_patch import set_shared_db, _get_or_create_db

        set_shared_db(None)
        result = _get_or_create_db(tmp_path)
        assert result is not None

        # Cleanup
        set_shared_db(None)

    def test_patch_applies_without_error(self):
        """T3.1-3.3: apply_loop_patch runs without error."""
        from ava.patches.a_schema_patch import apply_schema_patch
        apply_schema_patch()
        from ava.patches.loop_patch import apply_loop_patch

        result = apply_loop_patch()
        assert "AgentLoop patched" in result

    def test_process_message_patched(self):
        """T3.5: _process_message is wrapped after patch."""
        original = AgentLoop._process_message

        from ava.patches.a_schema_patch import apply_schema_patch
        apply_schema_patch()
        from ava.patches.loop_patch import apply_loop_patch
        apply_loop_patch()

        assert AgentLoop._process_message is not original

    def test_patch_result_mentions_new_modules(self):
        """New attributes mentioned in patch result string."""
        from ava.patches.a_schema_patch import apply_schema_patch
        apply_schema_patch()
        from ava.patches.loop_patch import apply_loop_patch

        result = apply_loop_patch()
        assert "categorized_memory" in result
        assert "summarizer" in result
        assert "compressor" in result

    def test_idempotent(self):
        """T3.6: 连续应用两次不应重复包装。"""
        from ava.patches.a_schema_patch import apply_schema_patch
        apply_schema_patch()
        from ava.patches.loop_patch import apply_loop_patch

        apply_loop_patch()
        result = apply_loop_patch()
        assert "skipped" in result.lower()
