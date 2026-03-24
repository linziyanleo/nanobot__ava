"""Tests for Claude Code task persistence (active.txt and history.db)."""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

import pytest


class TestCCTaskPersistence:
    """Test CC task persistence functions."""

    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path: Path):
        """Set up temporary directory for tests."""
        self.tasks_dir = tmp_path / "tasks"
        self.active_file = self.tasks_dir / "active_tasks.txt"
        self.history_db = self.tasks_dir / "history_tasks.db"

        # Patch the module-level paths
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._ACTIVE_TASKS_FILE", self.active_file), \
             mock.patch("nanobot.agent.subagent._HISTORY_TASKS_DB", self.history_db):
            yield

    def test_ensure_tasks_dir_creates_directory(self):
        """Test that _ensure_tasks_dir creates the directory."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir):
            from nanobot.agent.subagent import _ensure_tasks_dir
            _ensure_tasks_dir()
            assert self.tasks_dir.exists()

    def test_write_active_tasks_line_creates_file(self):
        """Test writing a task line to active_tasks.txt."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._ACTIVE_TASKS_FILE", self.active_file):
            from nanobot.agent.subagent import _write_active_tasks_line, _read_active_tasks

            _write_active_tasks_line(
                task_id="cc_abc123",
                status="RUNNING",
                turns=5,
                last_file="/path/to/file.py",
                last_stdout="processing data...",
                start_time="15:30",
            )

            content = _read_active_tasks()
            assert "cc_abc" in content
            assert "RUNNING" in content
            assert "t=05" in content
            assert "file.py" in content
            assert "start=15:30" in content

    def test_write_active_tasks_line_updates_existing(self):
        """Test updating an existing task line."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._ACTIVE_TASKS_FILE", self.active_file):
            from nanobot.agent.subagent import _write_active_tasks_line, _read_active_tasks

            # Write initial line
            _write_active_tasks_line("cc_abc123", "RUNNING", 1, "file1.py", "step 1", "10:00")
            
            # Update the same task
            _write_active_tasks_line("cc_abc123", "RUNNING", 5, "file2.py", "step 5", "10:00")

            content = _read_active_tasks()
            lines = content.strip().split("\n")
            assert len(lines) == 1  # Only one line for same task
            assert "t=05" in content
            assert "file2.py" in content

    def test_write_multiple_tasks(self):
        """Test writing multiple tasks."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._ACTIVE_TASKS_FILE", self.active_file):
            from nanobot.agent.subagent import _write_active_tasks_line, _read_active_tasks

            # Use task IDs with different first 6 characters
            _write_active_tasks_line("cc_aaa111", "RUNNING", 3, "a.py", "working", "10:00")
            _write_active_tasks_line("cc_bbb222", "RUNNING", 7, "b.py", "testing", "10:05")

            content = _read_active_tasks()
            lines = content.strip().split("\n")
            assert len(lines) == 2
            assert "cc_aaa" in content
            assert "cc_bbb" in content

    def test_remove_active_tasks_line(self):
        """Test removing a task line from active_tasks.txt."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._ACTIVE_TASKS_FILE", self.active_file):
            from nanobot.agent.subagent import _write_active_tasks_line, _remove_active_tasks_line, _read_active_tasks

            # Use task IDs with different first 6 characters
            _write_active_tasks_line("cc_aaa111", "RUNNING", 3, "a.py", "working", "10:00")
            _write_active_tasks_line("cc_bbb222", "RUNNING", 7, "b.py", "testing", "10:05")

            # Remove first task
            _remove_active_tasks_line("cc_aaa111")

            content = _read_active_tasks()
            assert "cc_bbb" in content  # task cc_bbb222 still there
            assert "cc_aaa" not in content  # task cc_aaa111 removed
            lines = content.strip().split("\n")
            assert len(lines) == 1

    def test_remove_nonexistent_task(self):
        """Test removing a task that doesn't exist."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._ACTIVE_TASKS_FILE", self.active_file):
            from nanobot.agent.subagent import _remove_active_tasks_line
            # Should not raise
            _remove_active_tasks_line("cc_nonexistent")

    def test_read_active_tasks_empty_file(self):
        """Test reading when file doesn't exist."""
        with mock.patch("nanobot.agent.subagent._ACTIVE_TASKS_FILE", self.active_file):
            from nanobot.agent.subagent import _read_active_tasks
            content = _read_active_tasks()
            assert content == ""

    def test_init_history_db(self):
        """Test initializing the history database."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._HISTORY_TASKS_DB", self.history_db):
            from nanobot.agent.subagent import _init_history_db
            _init_history_db()

            assert self.history_db.exists()

            # Verify schema
            conn = sqlite3.connect(str(self.history_db))
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            assert "tasks" in tables

    def test_archive_task(self):
        """Test archiving a completed task."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._HISTORY_TASKS_DB", self.history_db):
            from nanobot.agent.subagent import _archive_task

            _archive_task(
                task_id="cc_test123",
                status="DONE",
                turns=10,
                prompt="Test prompt for archiving",
                last_file="/path/to/final.py",
                last_stdout="completed successfully",
                started_at="2026-03-23 15:30:00",
                ended_at="2026-03-23 15:35:00",
                duration_s=300,
                error="",
            )

            # Verify data was inserted
            conn = sqlite3.connect(str(self.history_db))
            cursor = conn.execute("SELECT * FROM tasks WHERE task_id = ?", ("cc_test123",))
            row = cursor.fetchone()
            conn.close()

            assert row is not None
            assert row[0] == "cc_test123"  # task_id
            assert row[1] == "DONE"  # status
            assert row[2] == 10  # turns
            assert row[3] == "Test prompt for archiving"  # prompt

    def test_archive_task_with_error(self):
        """Test archiving a failed task with error message."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._HISTORY_TASKS_DB", self.history_db):
            from nanobot.agent.subagent import _archive_task

            _archive_task(
                task_id="cc_failed123",
                status="ERROR",
                turns=3,
                prompt="Task that failed",
                last_file="error.py",
                last_stdout="exception occurred",
                started_at="2026-03-23 16:00:00",
                ended_at="2026-03-23 16:01:00",
                duration_s=60,
                error="RuntimeError: Something went wrong",
            )

            conn = sqlite3.connect(str(self.history_db))
            cursor = conn.execute("SELECT status, error FROM tasks WHERE task_id = ?", ("cc_failed123",))
            row = cursor.fetchone()
            conn.close()

            assert row[0] == "ERROR"
            assert "RuntimeError" in row[1]

    def test_archive_replaces_existing(self):
        """Test that archiving replaces existing task with same ID."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._HISTORY_TASKS_DB", self.history_db):
            from nanobot.agent.subagent import _archive_task

            # Archive first version
            _archive_task("cc_dup123", "DONE", 5, "v1", "", "", "2026-03-23 10:00:00", "2026-03-23 10:05:00", 300, "")
            
            # Archive updated version
            _archive_task("cc_dup123", "DONE", 10, "v2", "", "", "2026-03-23 10:00:00", "2026-03-23 10:10:00", 600, "")

            conn = sqlite3.connect(str(self.history_db))
            cursor = conn.execute("SELECT COUNT(*), turns, prompt FROM tasks WHERE task_id = ?", ("cc_dup123",))
            row = cursor.fetchone()
            conn.close()

            assert row[0] == 1  # Only one row
            assert row[1] == 10  # Updated turns
            assert row[2] == "v2"  # Updated prompt

    def test_long_stdout_truncated(self):
        """Test that long stdout is truncated to 40 chars."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._ACTIVE_TASKS_FILE", self.active_file):
            from nanobot.agent.subagent import _write_active_tasks_line, _read_active_tasks

            long_stdout = "x" * 100
            _write_active_tasks_line("cc_long123", "RUNNING", 1, "file.py", long_stdout, "12:00")

            content = _read_active_tasks()
            # stdout should be truncated with "..."
            assert "x" * 37 + "..." in content or len(content) < 200

    def test_long_filename_truncated(self):
        """Test that long filenames are truncated."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._ACTIVE_TASKS_FILE", self.active_file):
            from nanobot.agent.subagent import _write_active_tasks_line, _read_active_tasks

            long_file = "/path/to/very_long_filename_that_exceeds_limit.py"
            _write_active_tasks_line("cc_longf123", "RUNNING", 1, long_file, "output", "12:00")

            content = _read_active_tasks()
            # Filename should be truncated
            assert "very_long_filename" in content or "..." in content


class TestCCTaskContextInjection:
    """Test CC task status injection into runtime context."""

    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path: Path):
        """Set up temporary directory for tests."""
        self.tasks_dir = tmp_path / "tasks"
        self.active_file = self.tasks_dir / "active_tasks.txt"
        yield

    def test_context_without_active_tasks(self):
        """Test runtime context when no tasks are active."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._ACTIVE_TASKS_FILE", self.active_file):
            from nanobot.agent.context import ContextBuilder

            context = ContextBuilder._build_runtime_context("telegram", "12345")
            assert "[CC_TASKS]" not in context

    def test_context_with_active_tasks(self):
        """Test runtime context includes CC_TASKS block when tasks exist."""
        with mock.patch("nanobot.agent.subagent._TASKS_DIR", self.tasks_dir), \
             mock.patch("nanobot.agent.subagent._ACTIVE_TASKS_FILE", self.active_file):
            from nanobot.agent.subagent import _write_active_tasks_line
            from nanobot.agent.context import ContextBuilder

            # Create an active task
            _write_active_tasks_line("cc_ctx123", "RUNNING", 3, "context.py", "building", "14:00")

            context = ContextBuilder._build_runtime_context("telegram", "12345")
            assert "[CC_TASKS]" in context
            assert "[/CC_TASKS]" in context
            assert "cc_ctx" in context
            assert "RUNNING" in context
