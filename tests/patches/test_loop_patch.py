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


class TestTokenStatsRecordId:
    """token_stats_service.record() 返回 record_id 和 update_record() 测试。"""

    def test_record_returns_id(self, tmp_path):
        from ava.storage import Database
        db = Database(tmp_path / "test.db")
        from ava.console.services.token_stats_service import TokenStatsCollector
        collector = TokenStatsCollector(data_dir=tmp_path, db=db)

        rid = collector.record(
            model="test-model", provider="test",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            session_key="test:1", finish_reason="stop",
        )
        assert rid is not None
        assert isinstance(rid, int)

    def test_update_record(self, tmp_path):
        from ava.storage import Database
        db = Database(tmp_path / "test.db")
        from ava.console.services.token_stats_service import TokenStatsCollector
        collector = TokenStatsCollector(data_dir=tmp_path, db=db)

        rid = collector.record(
            model="test-model", provider="test",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            session_key="test:1", finish_reason="pending", model_role="pending",
        )
        collector.update_record(rid, prompt_tokens=100, finish_reason="stop", model_role="chat")

        records = collector.get_records(limit=1)
        assert len(records) == 1
        assert records[0]["prompt_tokens"] == 100
        assert records[0]["finish_reason"] == "stop"
        assert records[0]["model_role"] == "chat"

    def test_update_record_rejects_unknown_fields(self, tmp_path):
        from ava.storage import Database
        db = Database(tmp_path / "test.db")
        from ava.console.services.token_stats_service import TokenStatsCollector
        collector = TokenStatsCollector(data_dir=tmp_path, db=db)

        rid = collector.record(
            model="m", provider="p",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
        collector.update_record(rid, unknown_field="bad", prompt_tokens=50)
        records = collector.get_records(limit=1)
        assert records[0]["prompt_tokens"] == 50

    def test_session_query_backfills_turn_seq_before_filtering(self, tmp_path):
        from ava.storage import Database
        db = Database(tmp_path / "test.db")
        from ava.console.services.token_stats_service import TokenStatsCollector
        collector = TokenStatsCollector(data_dir=tmp_path, db=db)

        conn = db._get_conn()
        conn.execute(
            """INSERT INTO sessions (key, created_at, updated_at, metadata, token_stats)
               VALUES (?, ?, ?, ?, ?)""",
            (
                "telegram:1",
                "2026-04-05T20:00:00",
                "2026-04-05T20:02:00",
                "{}",
                "{}",
            ),
        )
        session_row = conn.execute("SELECT id FROM sessions WHERE key = ?", ("telegram:1",)).fetchone()
        assert session_row is not None

        conn.execute(
            """INSERT INTO session_messages
               (session_id, seq, role, content, tool_calls, tool_call_id, name, reasoning_content, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_row["id"], 0, "user", "first", None, None, None, None, "2026-04-05T20:00:00"),
        )
        conn.execute(
            """INSERT INTO session_messages
               (session_id, seq, role, content, tool_calls, tool_call_id, name, reasoning_content, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_row["id"], 1, "assistant", "reply-1", None, None, None, None, "2026-04-05T20:00:10"),
        )
        conn.execute(
            """INSERT INTO session_messages
               (session_id, seq, role, content, tool_calls, tool_call_id, name, reasoning_content, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_row["id"], 2, "user", "second", None, None, None, None, "2026-04-05T20:01:00"),
        )
        conn.execute(
            """INSERT INTO token_usage
               (timestamp, model, provider, prompt_tokens, completion_tokens, total_tokens,
                session_key, turn_seq, iteration, user_message, output_content,
                system_prompt_preview, conversation_history, full_request_payload, finish_reason,
                model_role, cached_tokens, cache_creation_tokens, cost_usd, current_turn_tokens,
                tool_names)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "2026-04-05T20:00:05",
                "model-a",
                "provider-a",
                10,
                5,
                15,
                "telegram:1",
                None,
                0,
                "",
                "",
                "",
                "",
                "",
                "stop",
                "chat",
                0,
                0,
                0.0,
                0,
                "",
            ),
        )
        conn.execute(
            """INSERT INTO token_usage
               (timestamp, model, provider, prompt_tokens, completion_tokens, total_tokens,
                session_key, turn_seq, iteration, user_message, output_content,
                system_prompt_preview, conversation_history, full_request_payload, finish_reason,
                model_role, cached_tokens, cache_creation_tokens, cost_usd, current_turn_tokens,
                tool_names)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "2026-04-05T20:01:05",
                "model-b",
                "provider-b",
                20,
                7,
                27,
                "telegram:1",
                None,
                0,
                "",
                "",
                "",
                "",
                "",
                "stop",
                "chat",
                0,
                0,
                0.0,
                0,
                "",
            ),
        )
        conn.commit()

        per_turn = collector.get_by_session("telegram:1")
        assert [row["turn_seq"] for row in per_turn] == [0, 1]

        filtered = collector.get_records(limit=10, session_key="telegram:1", turn_seq=1)
        assert len(filtered) == 1
        assert filtered[0]["model"] == "model-b"
