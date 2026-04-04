"""Tests for BackgroundTaskStore lifecycle, persistence, and digest."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ava.agent.bg_tasks import BackgroundTaskStore, TaskSnapshot, TimelineEvent


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
