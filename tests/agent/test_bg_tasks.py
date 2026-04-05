"""Tests for BackgroundTaskStore lifecycle, persistence, and digest."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ava.agent.bg_tasks import BackgroundTaskStore, TaskSnapshot, TimelineEvent, _MAX_CONTINUATION_BUDGET


class TestTaskSnapshot:
    def test_to_dict(self):
        snap = TaskSnapshot(
            task_id="abc123",
            task_type="coding",
            origin_session_key="console:sess1",
            status="running",
            prompt_preview="Fix the bug",
            started_at=1000.0,
        )
        d = snap.to_dict()
        assert d["task_id"] == "abc123"
        assert d["task_type"] == "coding"
        assert d["origin_session_key"] == "console:sess1"
        assert isinstance(d["timeline"], list)


class TestSubmitAndLifecycle:
    @pytest.mark.asyncio
    async def test_submit_success(self):
        store = BackgroundTaskStore()

        async def mock_executor(**kw):
            return {"result": "done", "session_id": "s1"}

        task_id = store.submit_coding_task(
            executor=mock_executor,
            origin_session_key="console:sess1",
            prompt="Fix the bug",
            project_path="/tmp/project",
            timeout=30,
        )
        assert task_id in store._active

        await asyncio.sleep(0.1)

        assert task_id in store._finished
        assert task_id not in store._active
        snap = store._finished[task_id]
        assert snap.status == "succeeded"
        assert snap.result_preview == "done"

    @pytest.mark.asyncio
    async def test_submit_failure(self):
        store = BackgroundTaskStore()

        async def failing_executor(**kw):
            raise RuntimeError("oops")

        task_id = store.submit_coding_task(
            executor=failing_executor,
            origin_session_key="cli:direct",
            prompt="Bad task",
            project_path="/tmp",
            timeout=10,
        )
        await asyncio.sleep(0.1)

        snap = store._finished[task_id]
        assert snap.status == "failed"
        assert "oops" in snap.error_message

    @pytest.mark.asyncio
    async def test_submit_timeout(self):
        store = BackgroundTaskStore()

        async def slow_executor(**kw):
            await asyncio.sleep(100)
            return {"result": "never"}

        task_id = store.submit_coding_task(
            executor=slow_executor,
            origin_session_key="cli:direct",
            prompt="Slow task",
            project_path="/tmp",
            timeout=1,
        )
        await asyncio.sleep(1.5)

        snap = store._finished[task_id]
        assert snap.status == "failed"
        assert "Timed out" in snap.error_message


class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_running_task(self):
        store = BackgroundTaskStore()

        async def slow(**kw):
            await asyncio.sleep(100)
            return {"result": "never"}

        task_id = store.submit_coding_task(
            executor=slow,
            origin_session_key="console:s1",
            prompt="Cancel me",
            project_path="/tmp",
            timeout=600,
        )
        await asyncio.sleep(0.05)
        result = await store.cancel(task_id)
        assert "cancelled" in result.lower()
        await asyncio.sleep(0.1)
        snap = store._finished[task_id]
        assert snap.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_by_session(self):
        store = BackgroundTaskStore()

        async def slow(**kw):
            await asyncio.sleep(100)
            return {"result": "never"}

        t1 = store.submit_coding_task(
            executor=slow, origin_session_key="console:s1",
            prompt="Task 1", project_path="/tmp", timeout=600,
        )
        t2 = store.submit_coding_task(
            executor=slow, origin_session_key="console:s1",
            prompt="Task 2", project_path="/tmp", timeout=600,
        )
        t3 = store.submit_coding_task(
            executor=slow, origin_session_key="console:s2",
            prompt="Task 3", project_path="/tmp", timeout=600,
        )

        await asyncio.sleep(0.05)
        count = await store.cancel_by_session("console:s1")
        assert count == 2

        await asyncio.sleep(0.1)
        assert store._finished[t1].status == "cancelled"
        assert store._finished[t2].status == "cancelled"
        assert t3 in store._active or store._finished.get(t3, TaskSnapshot(
            task_id="", task_type="", origin_session_key="", status="running", prompt_preview="",
        )).status != "cancelled"

        await store.cancel(t3)
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self):
        store = BackgroundTaskStore()
        result = await store.cancel("nonexistent")
        assert "not found" in result.lower()


class TestGetStatus:
    @pytest.mark.asyncio
    async def test_status_by_session(self):
        store = BackgroundTaskStore()

        async def quick(**kw):
            return {"result": "ok"}

        store.submit_coding_task(
            executor=quick, origin_session_key="console:s1",
            prompt="T1", project_path="/tmp", timeout=10,
        )
        await asyncio.sleep(0.1)

        status = store.get_status(session_key="console:s1")
        assert status["total"] >= 1

        status_other = store.get_status(session_key="console:s2")
        assert status_other["total"] == 0


class TestDigest:
    @pytest.mark.asyncio
    async def test_empty_digest(self):
        store = BackgroundTaskStore()
        assert store.get_active_digest() == ""
        assert store.get_active_digest("console:s1") == ""

    @pytest.mark.asyncio
    async def test_active_task_digest(self):
        store = BackgroundTaskStore()

        async def slow(**kw):
            await asyncio.sleep(100)
            return {"result": "never"}

        store.submit_coding_task(
            executor=slow, origin_session_key="console:s1",
            prompt="Fix the auth module",
            project_path="/tmp", timeout=600,
        )
        await asyncio.sleep(0.05)

        digest = store.get_active_digest("console:s1")
        assert "Active Background Tasks" in digest
        assert "coding:" in digest
        assert "Fix the auth module" in digest

        digest_other = store.get_active_digest("console:s2")
        assert digest_other == ""

        await store.cancel_by_session("console:s1")
        await asyncio.sleep(0.1)


class TestTimeline:
    @pytest.mark.asyncio
    async def test_timeline_events(self):
        store = BackgroundTaskStore()

        async def quick(**kw):
            return {"result": "ok"}

        task_id = store.submit_coding_task(
            executor=quick, origin_session_key="cli:direct",
            prompt="T1", project_path="/tmp", timeout=10,
        )
        await asyncio.sleep(0.1)

        timeline = store.get_timeline(task_id)
        events = [e.event for e in timeline]
        assert "submitted" in events
        assert "started" in events
        assert "succeeded" in events


class TestOnComplete:
    @pytest.mark.asyncio
    async def test_result_persisted_to_session(self):
        mock_session = MagicMock()
        mock_session.messages = []
        mock_sessions = MagicMock()
        mock_sessions.get_or_create.return_value = mock_session
        mock_sessions.save = MagicMock()

        mock_loop = MagicMock()
        mock_loop.sessions = mock_sessions
        mock_loop.bus = None

        store = BackgroundTaskStore()
        store.set_agent_loop(mock_loop)

        async def quick(**kw):
            return {"result": "Build succeeded"}

        task_id = store.submit_coding_task(
            executor=quick, origin_session_key="console:s1",
            prompt="Build", project_path="/tmp", timeout=10,
        )
        await asyncio.sleep(0.2)

        assert len(mock_session.messages) == 1
        assert "SUCCESS" in mock_session.messages[0]["content"]
        assert "Build succeeded" in mock_session.messages[0]["content"]
        mock_sessions.save.assert_called()

    @pytest.mark.asyncio
    async def test_outbound_published(self):
        mock_session = MagicMock()
        mock_session.messages = []
        mock_sessions = MagicMock()
        mock_sessions.get_or_create.return_value = mock_session
        mock_sessions.save = MagicMock()

        mock_bus = MagicMock()
        mock_bus.publish_outbound = MagicMock()

        mock_loop = MagicMock()
        mock_loop.sessions = mock_sessions
        mock_loop.bus = mock_bus

        store = BackgroundTaskStore()
        store.set_agent_loop(mock_loop)

        async def quick(**kw):
            return {"result": "Done"}

        with patch("ava.agent.bg_tasks.OutboundMessage", create=True) as MockOB:
            from nanobot.bus.events import OutboundMessage
            task_id = store.submit_coding_task(
                executor=quick, origin_session_key="console:s1",
                prompt="Task", project_path="/tmp", timeout=10,
            )
            await asyncio.sleep(0.2)

        mock_bus.publish_outbound.assert_called_once()


class TestRecordEvent:
    def test_record_event_on_active_task(self):
        store = BackgroundTaskStore()
        snap = TaskSnapshot(
            task_id="t1", task_type="cron",
            origin_session_key="cron:j1",
            status="running", prompt_preview="Daily report",
        )
        store._active["t1"] = snap
        store.record_event("t1", "checkpoint", "halfway")
        assert len(snap.timeline) == 1
        assert snap.timeline[0].event == "checkpoint"


class TestAutoContineField:
    def test_snapshot_default_false(self):
        snap = TaskSnapshot(
            task_id="x", task_type="coding",
            origin_session_key="cli:d", status="queued",
            prompt_preview="test",
        )
        assert snap.auto_continue is False

    def test_snapshot_explicit_true(self):
        snap = TaskSnapshot(
            task_id="x", task_type="coding",
            origin_session_key="cli:d", status="queued",
            prompt_preview="test", auto_continue=True,
        )
        assert snap.auto_continue is True

    @pytest.mark.asyncio
    async def test_submit_passes_auto_continue(self):
        store = BackgroundTaskStore()

        async def noop(**kw):
            return {"result": "ok"}

        tid = store.submit_coding_task(
            executor=noop, origin_session_key="cli:d",
            prompt="T", project_path="/tmp", timeout=10,
            auto_continue=True,
        )
        snap = store._active.get(tid) or store._finished.get(tid)
        assert snap is not None
        assert snap.auto_continue is True

        await asyncio.sleep(0.1)


class TestContinuationBudget:
    def test_initial_budget(self):
        store = BackgroundTaskStore()
        assert store._continuation_budgets.get("k") is None

    def test_reset_clears_budget(self):
        store = BackgroundTaskStore()
        store._continuation_budgets["session:1"] = 2
        store.reset_continuation_budget("session:1")
        assert "session:1" not in store._continuation_budgets

    def test_reset_nonexistent_is_noop(self):
        store = BackgroundTaskStore()
        store.reset_continuation_budget("no-such-key")


class TestBuildContinuationMessage:
    def test_success_message(self):
        store = BackgroundTaskStore()
        snap = TaskSnapshot(
            task_id="abc", task_type="coding",
            origin_session_key="telegram:123",
            status="succeeded", prompt_preview="Fix bug",
            elapsed_ms=5000, result_preview="All tests pass",
        )
        msg = store._build_continuation_message(snap)
        assert "SUCCESS" in msg
        assert "abc" in msg
        assert "All tests pass" in msg
        assert "后续步骤" in msg

    def test_failed_message(self):
        store = BackgroundTaskStore()
        snap = TaskSnapshot(
            task_id="def", task_type="coding",
            origin_session_key="cli:d",
            status="failed", prompt_preview="Bad task",
            elapsed_ms=1000, error_message="Compile error",
        )
        msg = store._build_continuation_message(snap)
        assert "ERROR" in msg
        assert "Compile error" in msg

    def test_with_rebuild_info(self):
        store = BackgroundTaskStore()
        snap = TaskSnapshot(
            task_id="ghi", task_type="coding",
            origin_session_key="console:s1",
            status="succeeded", prompt_preview="Refactor",
            elapsed_ms=3000, result_preview="Done",
        )
        msg = store._build_continuation_message(snap, "[Auto Rebuild] Frontend rebuilt: hash=abcdef, 2000ms")
        assert "[Auto Rebuild]" in msg
        assert "Frontend rebuilt" in msg


class TestTriggerContinuation:
    @pytest.mark.asyncio
    async def test_skips_when_no_agent_loop(self):
        store = BackgroundTaskStore()
        snap = TaskSnapshot(
            task_id="t1", task_type="coding",
            origin_session_key="telegram:123",
            status="succeeded", prompt_preview="Fix",
            auto_continue=True,
        )
        await store._trigger_continuation(snap)

    @pytest.mark.asyncio
    async def test_skips_non_terminal_status(self):
        store = BackgroundTaskStore()
        mock_loop = MagicMock()
        mock_loop.process_direct = AsyncMock()
        store.set_agent_loop(mock_loop)

        snap = TaskSnapshot(
            task_id="t1", task_type="coding",
            origin_session_key="telegram:123",
            status="running", prompt_preview="Fix",
        )
        await store._trigger_continuation(snap)
        mock_loop.process_direct.assert_not_called()

    @pytest.mark.asyncio
    async def test_budget_exhaustion(self):
        store = BackgroundTaskStore()
        mock_loop = MagicMock()
        mock_loop.process_direct = AsyncMock(return_value=None)
        store.set_agent_loop(mock_loop)

        store._continuation_budgets["telegram:123"] = 0

        snap = TaskSnapshot(
            task_id="t1", task_type="coding",
            origin_session_key="telegram:123",
            status="succeeded", prompt_preview="Fix",
        )
        await store._trigger_continuation(snap)
        mock_loop.process_direct.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_continuation(self):
        store = BackgroundTaskStore()
        mock_loop = MagicMock()
        mock_loop.process_direct = AsyncMock(return_value=None)
        mock_loop.bus = None
        store.set_agent_loop(mock_loop)

        snap = TaskSnapshot(
            task_id="t1", task_type="coding",
            origin_session_key="telegram:123",
            status="succeeded", prompt_preview="Fix bug",
            elapsed_ms=2000, result_preview="Done",
        )
        await store._trigger_continuation(snap)

        mock_loop.process_direct.assert_called_once()
        call_kwargs = mock_loop.process_direct.call_args
        assert call_kwargs.kwargs["session_key"] == "telegram:123"
        assert call_kwargs.kwargs["channel"] == "telegram"
        assert call_kwargs.kwargs["chat_id"] == "123"

        assert store._continuation_budgets["telegram:123"] == _MAX_CONTINUATION_BUDGET - 1

    @pytest.mark.asyncio
    async def test_budget_decrements_per_call(self):
        store = BackgroundTaskStore()
        mock_loop = MagicMock()
        mock_loop.process_direct = AsyncMock(return_value=None)
        mock_loop.bus = None
        store.set_agent_loop(mock_loop)

        snap = TaskSnapshot(
            task_id="t1", task_type="coding",
            origin_session_key="cli:direct",
            status="succeeded", prompt_preview="T",
            elapsed_ms=100, result_preview="ok",
        )
        for i in range(_MAX_CONTINUATION_BUDGET):
            snap.task_id = f"t{i}"
            await store._trigger_continuation(snap)
        assert mock_loop.process_direct.call_count == _MAX_CONTINUATION_BUDGET

        snap.task_id = "t_extra"
        await store._trigger_continuation(snap)
        assert mock_loop.process_direct.call_count == _MAX_CONTINUATION_BUDGET

    @pytest.mark.asyncio
    async def test_publishes_outbound_on_response(self):
        store = BackgroundTaskStore()

        mock_response = MagicMock()
        mock_response.content = "I will continue working"

        mock_loop = MagicMock()
        mock_loop.process_direct = AsyncMock(return_value=mock_response)
        mock_bus = MagicMock()
        mock_bus.publish_outbound = MagicMock(return_value=None)
        mock_loop.bus = mock_bus
        store.set_agent_loop(mock_loop)

        snap = TaskSnapshot(
            task_id="t1", task_type="coding",
            origin_session_key="telegram:456",
            status="succeeded", prompt_preview="Fix",
            elapsed_ms=1000, result_preview="Done",
        )
        await store._trigger_continuation(snap)

        mock_bus.publish_outbound.assert_called_once_with(mock_response)


class TestRunPostTaskHooks:
    @pytest.mark.asyncio
    async def test_skips_non_coding_task(self):
        store = BackgroundTaskStore()
        snap = TaskSnapshot(
            task_id="t1", task_type="cron",
            origin_session_key="cron:j1",
            status="succeeded", prompt_preview="Daily",
        )
        result = await store._run_post_task_hooks(snap)
        assert result == ""

    @pytest.mark.asyncio
    async def test_skips_failed_task(self):
        store = BackgroundTaskStore()
        snap = TaskSnapshot(
            task_id="t1", task_type="coding",
            origin_session_key="cli:d",
            status="failed", prompt_preview="Bad",
        )
        result = await store._run_post_task_hooks(snap)
        assert result == ""

    @pytest.mark.asyncio
    async def test_calls_maybe_rebuild_on_success(self):
        store = BackgroundTaskStore()
        snap = TaskSnapshot(
            task_id="t1", task_type="coding",
            origin_session_key="cli:d",
            status="succeeded", prompt_preview="Fix",
            project_path="/tmp/fake",
        )
        with patch.object(store, "_maybe_rebuild_frontend", new_callable=AsyncMock, return_value="[Auto Rebuild] ok"):
            result = await store._run_post_task_hooks(snap)
        assert "[Auto Rebuild]" in result


class TestMaybeRebuildFrontend:
    @pytest.mark.asyncio
    async def test_no_project_path(self):
        store = BackgroundTaskStore()
        snap = TaskSnapshot(
            task_id="t1", task_type="coding",
            origin_session_key="cli:d",
            status="succeeded", prompt_preview="Fix",
            project_path="",
        )
        result = await store._maybe_rebuild_frontend(snap)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_console_ui_dir(self, tmp_path):
        store = BackgroundTaskStore()
        snap = TaskSnapshot(
            task_id="t1", task_type="coding",
            origin_session_key="cli:d",
            status="succeeded", prompt_preview="Fix",
            project_path=str(tmp_path),
        )
        result = await store._maybe_rebuild_frontend(snap)
        assert result is None

    @pytest.mark.asyncio
    async def test_build_not_needed(self, tmp_path):
        (tmp_path / "console-ui").mkdir()
        store = BackgroundTaskStore()
        snap = TaskSnapshot(
            task_id="t1", task_type="coding",
            origin_session_key="cli:d",
            status="succeeded", prompt_preview="Fix",
            project_path=str(tmp_path),
        )
        with patch("ava.console.ui_build.needs_console_ui_build", return_value=False) as mock_check, \
             patch("ava.console.ui_build.rebuild_console_ui") as mock_rebuild:
            result = await store._maybe_rebuild_frontend(snap)
        assert result is None
        mock_rebuild.assert_not_called()


class TestOnCompleteWithContinuation:
    @pytest.mark.asyncio
    async def test_no_continuation_when_auto_continue_false(self):
        mock_session = MagicMock()
        mock_session.messages = []
        mock_sessions = MagicMock()
        mock_sessions.get_or_create.return_value = mock_session
        mock_sessions.save = MagicMock()

        mock_loop = MagicMock()
        mock_loop.sessions = mock_sessions
        mock_loop.bus = None
        mock_loop.process_direct = AsyncMock()

        store = BackgroundTaskStore()
        store.set_agent_loop(mock_loop)

        async def quick(**kw):
            return {"result": "Done"}

        task_id = store.submit_coding_task(
            executor=quick, origin_session_key="telegram:123",
            prompt="Task", project_path="/tmp", timeout=10,
            auto_continue=False,
        )
        await asyncio.sleep(0.3)

        mock_loop.process_direct.assert_not_called()

    @pytest.mark.asyncio
    async def test_continuation_when_auto_continue_true(self):
        mock_session = MagicMock()
        mock_session.messages = []
        mock_sessions = MagicMock()
        mock_sessions.get_or_create.return_value = mock_session
        mock_sessions.save = MagicMock()

        mock_loop = MagicMock()
        mock_loop.sessions = mock_sessions
        mock_loop.bus = None
        mock_loop.process_direct = AsyncMock(return_value=None)

        store = BackgroundTaskStore()
        store.set_agent_loop(mock_loop)

        async def quick(**kw):
            return {"result": "Done"}

        task_id = store.submit_coding_task(
            executor=quick, origin_session_key="telegram:123",
            prompt="Task", project_path="/tmp", timeout=10,
            auto_continue=True,
        )
        await asyncio.sleep(0.3)

        mock_loop.process_direct.assert_called_once()
        call_kwargs = mock_loop.process_direct.call_args
        assert call_kwargs.kwargs["session_key"] == "telegram:123"
