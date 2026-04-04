"""GatewayControlTool 测试。"""

from unittest.mock import MagicMock

import pytest

from ava.tools.gateway_control import GatewayControlTool


@pytest.fixture
def mock_lifecycle():
    lm = MagicMock()
    lm.get_status.return_value = {
        "running": True,
        "pid": 12345,
        "uptime_seconds": 100.0,
        "gateway_port": 18790,
        "console_port": 6688,
        "supervised": True,
        "supervisor": "docker",
        "restart_pending": False,
        "boot_generation": 3,
        "last_exit_reason": None,
    }
    lm.request_restart.return_value = {
        "status": "accepted",
        "message": "Restart request accepted. Process will exit gracefully.",
        "boot_generation": 3,
    }
    return lm


@pytest.fixture
def tool(mock_lifecycle):
    t = GatewayControlTool(lifecycle=mock_lifecycle)
    t.set_context("console", "admin", session_key="console:session_1")
    return t


class TestProperties:
    def test_name(self):
        t = GatewayControlTool()
        assert t.name == "gateway_control"

    def test_description(self):
        t = GatewayControlTool()
        assert "status" in t.description
        assert "restart" in t.description

    def test_parameters_schema(self):
        t = GatewayControlTool()
        params = t.parameters
        assert params["type"] == "object"
        assert "action" in params["properties"]
        assert params["properties"]["action"]["enum"] == ["status", "restart"]


class TestStatusAction:
    async def test_status_returns_info(self, tool, mock_lifecycle):
        result = await tool.execute(action="status")
        assert "Gateway Status" in result
        assert "gen 3" in result
        assert "12345" in result
        mock_lifecycle.get_status.assert_called_once()

    async def test_status_without_lifecycle(self):
        t = GatewayControlTool(lifecycle=None)
        result = await t.execute(action="status")
        assert "not initialized" in result


class TestRestartAction:
    async def test_restart_from_console(self, tool, mock_lifecycle):
        result = await tool.execute(action="restart", reason="test")
        assert "accepted" in result.lower() or "gracefully" in result.lower()
        mock_lifecycle.request_restart.assert_called_once()
        call_kwargs = mock_lifecycle.request_restart.call_args[1]
        assert call_kwargs["requested_by"] == "console:admin"
        assert call_kwargs["reason"] == "test"

    async def test_restart_from_cli(self, mock_lifecycle):
        t = GatewayControlTool(lifecycle=mock_lifecycle)
        t.set_context("cli", "direct", session_key="cli:direct")
        result = await t.execute(action="restart")
        mock_lifecycle.request_restart.assert_called_once()

    async def test_restart_rejected_from_telegram(self, mock_lifecycle):
        t = GatewayControlTool(lifecycle=mock_lifecycle)
        t.set_context("telegram", "12345")
        result = await t.execute(action="restart")
        assert "cli/console" in result
        mock_lifecycle.request_restart.assert_not_called()

    async def test_restart_without_lifecycle(self):
        t = GatewayControlTool(lifecycle=None)
        t.set_context("console", "admin")
        result = await t.execute(action="restart")
        assert "not initialized" in result

    async def test_restart_passes_force(self, tool, mock_lifecycle):
        await tool.execute(action="restart", force=True, reason="urgent")
        call_kwargs = mock_lifecycle.request_restart.call_args[1]
        assert call_kwargs["force"] is True


class TestSetContext:
    def test_set_context_with_session_key(self):
        t = GatewayControlTool()
        t.set_context("console", "user1", session_key="console:session_abc")
        assert t._channel == "console"
        assert t._chat_id == "user1"
        assert t._session_key == "console:session_abc"

    def test_set_context_fallback(self):
        t = GatewayControlTool()
        t.set_context("telegram", "12345")
        assert t._session_key == "telegram:12345"


class TestUnknownAction:
    async def test_unknown_action(self, tool):
        result = await tool.execute(action="unknown")
        assert "Unknown action" in result
