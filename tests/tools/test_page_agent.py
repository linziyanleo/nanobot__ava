"""Tests for PageAgentTool — unit tests without real browser/runner."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import ava.tools.page_agent as page_agent_module
from ava.tools.page_agent import PageAgentTool


@pytest.fixture
def tool():
    """PageAgentTool with default config (no runner started)."""
    cfg = MagicMock()
    cfg.enabled = True
    cfg.api_key_env = "PAGE_AGENT_API_KEY"
    cfg.headless = True
    cfg.browser_type = "chromium"
    cfg.viewport_width = 1280
    cfg.viewport_height = 720
    cfg.api_base = ""
    cfg.model = ""
    cfg.max_steps = 40
    cfg.step_delay = 0.4
    cfg.language = "zh-CN"
    cfg.timeout = 120
    cfg.screenshot_dir = ""
    return PageAgentTool(config=cfg, media_service=None)


class TestToolInterface:
    def test_name(self, tool):
        assert tool.name == "page_agent"

    def test_description_not_empty(self, tool):
        assert len(tool.description) > 0

    def test_parameters_schema(self, tool):
        params = tool.parameters
        assert params["type"] == "object"
        props = params["properties"]
        assert "action" in props
        assert "url" in props
        assert "instruction" in props
        assert "session_id" in props
        assert "response_format" in props
        assert props["action"]["enum"] == [
            "execute", "screenshot", "get_page_info", "close_session", "restart_runner"
        ]
        assert props["response_format"]["enum"] == ["text", "json"]

    def test_required_fields(self, tool):
        assert tool.parameters["required"] == ["action"]


class TestDisabled:
    @pytest.mark.asyncio
    async def test_disabled_returns_error(self):
        cfg = MagicMock()
        cfg.enabled = False
        t = PageAgentTool(config=cfg)
        result = await t.execute(action="execute", instruction="go to example.com")
        assert "disabled" in result.lower()


class TestExecuteValidation:
    @pytest.mark.asyncio
    async def test_execute_missing_instruction(self, tool):
        with patch.object(tool, "_rpc", new_callable=AsyncMock):
            result = await tool.execute(action="execute")
            assert "instruction is required" in result.lower()

    @pytest.mark.asyncio
    async def test_screenshot_missing_session(self, tool):
        result = await tool.execute(action="screenshot")
        assert "session_id is required" in result.lower()

    @pytest.mark.asyncio
    async def test_get_page_info_missing_session(self, tool):
        result = await tool.execute(action="get_page_info")
        assert "session_id is required" in result.lower()

    @pytest.mark.asyncio
    async def test_close_session_missing_session(self, tool):
        result = await tool.execute(action="close_session")
        assert "session_id is required" in result.lower()

    @pytest.mark.asyncio
    async def test_unknown_action(self, tool):
        result = await tool.execute(action="fly_to_moon")
        assert "unknown action" in result.lower()

    @pytest.mark.asyncio
    async def test_invalid_response_format(self, tool):
        result = await tool.execute(action="execute", instruction="open page", response_format="yaml")
        assert "response_format" in result


class TestRpcExecute:
    @pytest.mark.asyncio
    async def test_execute_success(self, tool):
        mock_result = {
            "success": True,
            "result": {
                "session_id": "s_abc",
                "page_url": "https://example.com",
                "page_title": "Example",
                "data": "Page loaded",
            },
        }
        with patch.object(tool, "_rpc", new_callable=AsyncMock, return_value=mock_result):
            result = await tool.execute(
                action="execute",
                url="https://example.com",
                instruction="open this page",
            )
            assert "s_abc" in result
            assert "Example" in result
            assert "Page loaded" in result

    @pytest.mark.asyncio
    async def test_execute_success_json(self, tool):
        mock_result = {
            "success": True,
            "result": {
                "session_id": "s_abc",
                "page_url": "https://example.com",
                "page_title": "Example",
                "data": "Page loaded",
                "success": True,
                "steps": 3,
                "duration": 1200,
                "page_state": {"headings": ["Example"]},
            },
        }
        with patch.object(tool, "_rpc", new_callable=AsyncMock, return_value=mock_result):
            result = await tool.execute(
                action="execute",
                url="https://example.com",
                instruction="open this page",
                response_format="json",
            )
        payload = json.loads(result)
        assert payload["status"] == "SUCCESS"
        assert payload["session_id"] == "s_abc"
        assert payload["steps"] == 3
        assert payload["duration_ms"] == 1200
        assert payload["page"]["url"] == "https://example.com"
        assert payload["result"]["success"] is True
        assert payload["page_state"]["headings"] == ["Example"]
        assert payload["error"] is None

    @pytest.mark.asyncio
    async def test_execute_rpc_error(self, tool):
        mock_result = {
            "success": False,
            "error": {"code": "EXEC_FAIL", "message": "Browser crashed"},
        }
        with patch.object(tool, "_rpc", new_callable=AsyncMock, return_value=mock_result):
            result = await tool.execute(
                action="execute",
                instruction="click button",
                session_id="s_test",
            )
            assert "error" in result.lower()
            assert "Browser crashed" in result

    @pytest.mark.asyncio
    async def test_execute_rpc_error_json(self, tool):
        mock_result = {
            "success": False,
            "error": {
                "code": "TIMEOUT",
                "message": "RPC timeout after 120s",
                "session_id": "s_test",
                "duration": 120000,
                "page_url": "https://example.com/slow",
                "page_title": "Slow Page",
            },
        }
        with patch.object(tool, "_rpc", new_callable=AsyncMock, return_value=mock_result):
            result = await tool.execute(
                action="execute",
                instruction="click button",
                session_id="s_test",
                response_format="json",
            )
        payload = json.loads(result)
        assert payload["status"] == "TIMEOUT"
        assert payload["session_id"] == "s_test"
        assert payload["page"]["url"] == "https://example.com/slow"
        assert payload["result"]["success"] is False
        assert payload["error"]["code"] == "TIMEOUT"
        assert "timeout" in payload["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_screenshot_success_json(self, tool, tmp_path):
        mock_result = {
            "success": True,
            "result": {
                "path": str(tmp_path / "shot.png"),
                "size": 2048,
            },
        }
        with patch.object(tool, "_rpc", new_callable=AsyncMock, return_value=mock_result), \
             patch.object(tool, "_get_screenshot_dir", return_value=tmp_path):
            result = await tool.execute(
                action="screenshot",
                session_id="s_test",
                response_format="json",
            )
        payload = json.loads(result)
        assert payload["status"] == "SUCCESS"
        assert payload["session_id"] == "s_test"
        assert payload["result"]["success"] is True
        assert payload["result"]["path"].endswith(".png")
        assert payload["result"]["size_bytes"] == 2048
        assert payload["error"] is None

    @pytest.mark.asyncio
    async def test_get_page_info_success_json(self, tool):
        mock_result = {
            "success": True,
            "result": {
                "page_url": "https://example.com",
                "page_title": "Example",
                "viewport": "1280x720",
            },
        }
        with patch.object(tool, "_rpc", new_callable=AsyncMock, return_value=mock_result):
            result = await tool.execute(
                action="get_page_info",
                session_id="s_test",
                response_format="json",
            )
        payload = json.loads(result)
        assert payload["status"] == "SUCCESS"
        assert payload["session_id"] == "s_test"
        assert payload["page"]["title"] == "Example"
        assert payload["page"]["viewport"] == "1280x720"
        assert payload["result"]["success"] is True


class TestSubscription:
    @pytest.mark.asyncio
    async def test_list_sessions_without_runner_returns_empty(self, tool):
        assert await tool.list_sessions() == []

    @pytest.mark.asyncio
    async def test_list_sessions_filters_non_strings(self, tool):
        tool._process = MagicMock(returncode=None)
        tool._event_buffer = {"s1": [{"type": "activity"}], "stale": [{"type": "activity"}]}
        tool._last_frame = {"s2": {"type": "frame"}, "stale": {"type": "frame"}}
        tool._subscribers = {"s1": [MagicMock()], "stale": [MagicMock()]}
        mock_result = {
            "success": True,
            "result": {"sessions": ["s1", 123, "s2", None]},
        }
        with patch.object(tool, "_rpc", new_callable=AsyncMock, return_value=mock_result):
            assert await tool.list_sessions() == ["s1", "s2"]
        assert "stale" not in tool._event_buffer
        assert "stale" not in tool._last_frame
        assert "stale" not in tool._subscribers

    def test_subscribe_and_unsubscribe(self, tool):
        cb = MagicMock()
        tool.subscribe("sess1", cb)
        assert "sess1" in tool._subscribers
        assert cb in tool._subscribers["sess1"]

        tool.unsubscribe("sess1", cb)
        assert "sess1" not in tool._subscribers

    def test_get_active_sessions(self, tool):
        cb = MagicMock()
        tool.subscribe("s1", cb)
        tool.subscribe("s2", cb)
        sessions = tool.get_active_sessions()
        assert set(sessions) == {"s1", "s2"}

    def test_unsubscribe_nonexistent(self, tool):
        cb = MagicMock()
        # Should not raise
        tool.unsubscribe("nonexistent", cb)

    def test_clear_session_state_removes_cached_state_and_subscribers(self, tool):
        cb = MagicMock()
        tool.subscribe("sess1", cb)
        tool._event_buffer["sess1"] = [{"type": "activity"}]
        tool._last_frame["sess1"] = {"type": "frame"}

        tool._clear_session_state("sess1")

        assert "sess1" not in tool._subscribers
        assert "sess1" not in tool._event_buffer
        assert "sess1" not in tool._last_frame

    @pytest.mark.asyncio
    async def test_shutdown_runner_clears_cached_state(self, tool):
        process = MagicMock()
        process.returncode = None
        process.wait = AsyncMock(return_value=0)
        tool._process = process
        tool._reader_task = MagicMock()
        tool._idle_task = MagicMock()
        tool._event_buffer["sess1"] = [{"type": "activity"}]
        tool._last_frame["sess1"] = {"type": "frame"}
        tool._subscribers["sess1"] = [MagicMock()]

        with patch.object(tool, "_write_stdin", new_callable=AsyncMock):
            await tool._shutdown_runner()

        assert tool._process is None
        assert tool._event_buffer == {}
        assert tool._last_frame == {}
        assert tool._subscribers == {}


class TestLifecycleHardening:
    def test_registers_process_cleanup_only_once(self):
        cfg = MagicMock()
        cfg.enabled = True

        original_registered = page_agent_module._PROCESS_CLEANUP_REGISTERED
        original_live_tools = page_agent_module._LIVE_PAGE_AGENT_TOOLS
        try:
            page_agent_module._PROCESS_CLEANUP_REGISTERED = False
            page_agent_module._LIVE_PAGE_AGENT_TOOLS = None
            with patch.object(page_agent_module.atexit, "register") as mock_register:
                first = PageAgentTool(config=cfg)
                second = PageAgentTool(config=cfg)

            assert mock_register.call_count == 1
            registered_callback = mock_register.call_args.args[0]
            assert getattr(registered_callback, "__self__", None) is PageAgentTool
            assert registered_callback.__name__ == "_cleanup_live_tools"
            assert len(list(PageAgentTool._get_live_tools())) == 2
            assert first is not second
        finally:
            page_agent_module._PROCESS_CLEANUP_REGISTERED = original_registered
            page_agent_module._LIVE_PAGE_AGENT_TOOLS = original_live_tools


class TestSetContext:
    def test_set_context(self, tool):
        tool.set_context("telegram", "chat_123")
        assert tool._channel == "telegram"
        assert tool._chat_id == "chat_123"


class TestPageInfoHelpers:
    @pytest.mark.asyncio
    async def test_get_page_info_passthrough(self, tool):
        mock_result = {
            "success": True,
            "result": {"page_url": "https://example.com"},
        }
        with patch.object(tool, "_rpc", new_callable=AsyncMock, return_value=mock_result):
            assert await tool.get_page_info("s_test") == mock_result
