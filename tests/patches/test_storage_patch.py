"""Tests for storage_patch — SQLite storage replacement."""

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from nanobot.session.manager import SessionManager, Session


@pytest.fixture(autouse=True)
def _restore_session_manager():
    """Save and restore SessionManager methods to avoid polluting other tests."""
    orig_save = SessionManager.save
    orig_load = SessionManager._load
    orig_list = SessionManager.list_sessions
    yield
    SessionManager.save = orig_save
    SessionManager._load = orig_load
    SessionManager.list_sessions = orig_list


@pytest.fixture
def storage_db(tmp_path):
    """Apply storage_patch with a temp workspace and return (db, workspace)."""
    from unittest.mock import patch as mock_patch

    with mock_patch("nanobot.config.paths.get_workspace_path", return_value=tmp_path):
        (tmp_path / "data").mkdir(exist_ok=True)
        from ava.storage import Database

        db_path = tmp_path / "data" / "nanobot.db"
        db = Database(db_path)
        return db, tmp_path, db_path


@pytest.fixture
def patched_manager(tmp_path):
    """Return a SessionManager after storage_patch is applied."""
    from unittest.mock import patch as mock_patch

    with mock_patch("nanobot.config.paths.get_workspace_path", return_value=tmp_path):
        (tmp_path / "data").mkdir(exist_ok=True)

        from ava.patches.storage_patch import apply_storage_patch
        apply_storage_patch()

    mgr = SessionManager.__new__(SessionManager)
    mgr._cache = {}
    mgr._sessions_dir = tmp_path / "sessions"
    mgr._sessions_dir.mkdir(exist_ok=True)
    return mgr


def _make_session(key="test:123", messages=None):
    """Helper to create a Session instance."""
    return Session(
        key=key,
        messages=messages or [
            {"role": "user", "content": "hello", "timestamp": "2026-01-01T00:00:00"},
            {"role": "assistant", "content": "hi there", "timestamp": "2026-01-01T00:00:01"},
        ],
        created_at=datetime(2026, 1, 1),
        metadata={"token_stats": {}},
        last_consolidated=0,
    )


class TestStoragePatch:
    def test_patch_applies_without_error(self, tmp_path):
        """T5.0: apply_storage_patch runs without error."""
        from unittest.mock import patch as mock_patch

        with mock_patch("nanobot.config.paths.get_workspace_path", return_value=tmp_path):
            (tmp_path / "data").mkdir(exist_ok=True)
            from ava.patches.storage_patch import apply_storage_patch

            result = apply_storage_patch()
            assert "sqlite" in result.lower()

    def test_save_and_load(self, patched_manager):
        """T5.1+T5.2: save then load returns equivalent session."""
        session = _make_session()
        patched_manager.save(session)

        loaded = patched_manager._load("test:123")
        assert loaded is not None
        assert loaded.key == "test:123"
        assert len(loaded.messages) == 2
        assert loaded.messages[0]["role"] == "user"
        assert loaded.messages[0]["content"] == "hello"

    def test_load_nonexistent(self, patched_manager):
        """T5.5: loading nonexistent key returns None."""
        result = patched_manager._load("nonexistent:key")
        assert result is None

    def test_message_serialization_with_tool_calls(self, patched_manager):
        """T5.3: messages with tool_calls serialize/deserialize correctly."""
        session = _make_session(messages=[
            {
                "role": "assistant",
                "content": "calling tool",
                "tool_calls": [{"id": "tc1", "function": {"name": "test"}}],
                "timestamp": "2026-01-01T00:00:00",
            },
            {
                "role": "tool",
                "content": "result",
                "tool_call_id": "tc1",
                "name": "test",
                "timestamp": "2026-01-01T00:00:01",
            },
        ])
        patched_manager.save(session)
        loaded = patched_manager._load("test:123")

        assert loaded.messages[0]["tool_calls"][0]["id"] == "tc1"
        assert loaded.messages[1]["tool_call_id"] == "tc1"
        assert loaded.messages[1]["name"] == "test"

    def test_list_sessions(self, patched_manager):
        """T5.4: list_sessions returns saved sessions."""
        patched_manager.save(_make_session("sess:1"))
        patched_manager.save(_make_session("sess:2"))

        sessions = patched_manager.list_sessions()
        keys = [s["key"] for s in sessions]
        assert "sess:1" in keys
        assert "sess:2" in keys

    def test_upsert(self, patched_manager):
        """T5.6: saving same key twice keeps latest version."""
        s1 = _make_session(messages=[{"role": "user", "content": "v1", "timestamp": "t1"}])
        patched_manager.save(s1)

        s2 = _make_session(messages=[{"role": "user", "content": "v2", "timestamp": "t2"}])
        patched_manager.save(s2)

        loaded = patched_manager._load("test:123")
        assert loaded.messages[0]["content"] == "v2"

    def test_cache_updated(self, patched_manager):
        """T5.7: save updates _cache."""
        session = _make_session()
        patched_manager.save(session)
        assert "test:123" in patched_manager._cache

    def test_backfill_integrated(self, patched_manager):
        """T5.8: backfill runs after SQLite load (P0 fix)."""
        # Save a session — backfill should run on load
        # Even if messages are "clean", the backfill code path should execute without error
        session = _make_session()
        patched_manager.save(session)
        loaded = patched_manager._load("test:123")
        assert loaded is not None
        assert len(loaded.messages) >= 2

    def test_shared_db_with_loop_patch(self, tmp_path):
        """T5.9: storage_patch calls loop_patch.set_shared_db."""
        from unittest.mock import patch as mock_patch

        with mock_patch("nanobot.config.paths.get_workspace_path", return_value=tmp_path):
            (tmp_path / "data").mkdir(exist_ok=True)

            # Verify that after apply, loop_patch._shared_db is set
            from ava.patches.loop_patch import set_shared_db
            set_shared_db(None)  # reset

            from ava.patches.storage_patch import apply_storage_patch
            apply_storage_patch()

            from ava.patches import loop_patch
            assert loop_patch._shared_db is not None
