"""Layer 1: page_agent 集成测试。

真实启动 Node runner 进程，通过 stdin/stdout JSON-RPC 通信。
不涉及 Playwright 浏览器操作（仅测试进程管理和 RPC 协议）。
"""

from __future__ import annotations

import pytest

from ava.tools.page_agent import _find_node

pytestmark = pytest.mark.integration


# ------------------------------------------------------------------
# _find_node 探测
# ------------------------------------------------------------------

class TestFindNode:
    def test_find_node_returns_path(self):
        """_find_node() 应能找到 node 可执行文件。"""
        result = _find_node()
        if result is None:
            pytest.skip("node not installed")
        assert "node" in result

    def test_find_node_is_executable(self):
        import os
        result = _find_node()
        if result is None:
            pytest.skip("node not installed")
        assert os.access(result, os.X_OK)


# ------------------------------------------------------------------
# Runner 进程启动 + init RPC
# ------------------------------------------------------------------

class TestRunnerLifecycle:
    async def test_runner_starts_and_inits(self, runner_process):
        """启动 runner → 发送 init → 返回 success。"""
        resp = await runner_process.rpc("init", {
            "headless": True,
            "browserType": "chromium",
            "viewportWidth": 1280,
            "viewportHeight": 720,
        })
        assert resp["success"] is True
        assert resp["result"]["message"] == "config updated"

    async def test_list_sessions_empty(self, runner_process):
        """初始状态应无会话。"""
        resp = await runner_process.rpc("list_sessions")
        assert resp["success"] is True
        assert resp["result"]["sessions"] == []

    async def test_shutdown_exits_cleanly(self, runner_process):
        """shutdown 后进程应正常退出。"""
        resp = await runner_process.rpc("shutdown", timeout=10)
        assert resp["success"] is True
        code = await runner_process.process.wait()
        assert code == 0


# ------------------------------------------------------------------
# 错误路径
# ------------------------------------------------------------------

class TestRpcErrors:
    async def test_no_session_error(self, runner_process):
        """对不存在的 session 操作应返回 NO_SESSION。"""
        await runner_process.rpc("init", {"headless": True, "browserType": "chromium"})
        resp = await runner_process.rpc("get_page_info", {"session_id": "nonexistent"})
        assert resp["success"] is False
        assert resp["error"]["code"] == "NO_SESSION"

    async def test_screenshot_no_session(self, runner_process):
        """对不存在的 session 截图应返回 NO_SESSION。"""
        await runner_process.rpc("init", {"headless": True, "browserType": "chromium"})
        resp = await runner_process.rpc("screenshot", {"session_id": "nonexistent"})
        assert resp["success"] is False
        assert resp["error"]["code"] == "NO_SESSION"

    async def test_execute_missing_instruction(self, runner_process):
        """execute 缺少 instruction 应返回 MISSING_PARAM。"""
        await runner_process.rpc("init", {"headless": True, "browserType": "chromium"})
        resp = await runner_process.rpc("execute", {"url": "about:blank"})
        assert resp["success"] is False
        assert resp["error"]["code"] == "MISSING_PARAM"
