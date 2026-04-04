"""Tests for PageAgentTool — unit tests without real browser/runner."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        assert props["action"]["enum"] == [
            "execute", "screenshot", "get_page_info", "close_session", "restart_runner"
        ]

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


class TestSubscription:
    @pytest.mark.asyncio
    async def test_list_sessions_without_runner_returns_empty(self, tool):
        assert await tool.list_sessions() == []

    @pytest.mark.asyncio
    async def test_list_sessions_filters_non_strings(self, tool):
        tool._process = MagicMock(returncode=None)
        mock_result = {
            "success": True,
            "result": {"sessions": ["s1", 123, "s2", None]},
        }
        with patch.object(tool, "_rpc", new_callable=AsyncMock, return_value=mock_result):
            assert await tool.list_sessions() == ["s1", "s2"]

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
