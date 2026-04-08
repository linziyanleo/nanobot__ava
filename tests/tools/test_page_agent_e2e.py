"""Layer 2: page_agent E2E 冒烟测试。

真实启动 Node runner + Playwright 浏览器 + console-ui dev server + mock LLM server，
验证完整的 navigate → execute → screenshot 链路。
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

# Playwright 浏览器缺失时跳过整个模块
_PW_CHROMIUM = Path.home() / "Library" / "Caches" / "ms-playwright"
if not _PW_CHROMIUM.exists() or not list(_PW_CHROMIUM.glob("chromium*")):
    pytest.skip("Playwright chromium not installed (run: npx playwright install chromium)", allow_module_level=True)

pytestmark = pytest.mark.e2e


class TestNavigateAndScreenshot:
    """navigate 到 console-ui → 截图验证。"""

    async def test_navigate_and_screenshot(
        self, runner_process, mock_llm, console_ui_server,
    ):
        # init：配置 mock LLM
        resp = await runner_process.rpc("init", {
            "headless": True,
            "browserType": "chromium",
            "viewportWidth": 1280,
            "viewportHeight": 720,
            "apiBase": mock_llm,
            "apiKey": "mock-key",
            "model": "mock-model",
            "maxSteps": 3,
            "stepDelay": 0,
            "language": "zh-CN",
        })
        assert resp["success"] is True

        # execute：导航到 console-ui（mock LLM 立即返回 done）
        resp = await runner_process.rpc("execute", {
            "url": console_ui_server,
            "instruction": "观察当前页面",
        }, timeout=60)
        assert resp["success"] is True, f"execute failed: {resp.get('error')}"
        result = resp["result"]
        session_id = result["session_id"]
        assert session_id
        assert result["page_url"].startswith("http")

        # screenshot：对当前页面截图
        resp = await runner_process.rpc("screenshot", {
            "session_id": session_id,
        })
        assert resp["success"] is True
        screenshot_data = resp["result"].get("data", "")
        assert len(screenshot_data) > 100  # base64 数据应非空
        # 验证是有效的 base64
        raw = base64.b64decode(screenshot_data)
        assert len(raw) > 1000  # PNG 图片至少几 KB


class TestExecuteWithMockLLM:
    """mock LLM 返回固定 done action，验证 execute 完整流程。"""

    async def test_execute_returns_structured_result(
        self, runner_process, mock_llm, console_ui_server,
    ):
        await runner_process.rpc("init", {
            "headless": True,
            "browserType": "chromium",
            "apiBase": mock_llm,
            "apiKey": "mock-key",
            "model": "mock-model",
            "maxSteps": 3,
            "stepDelay": 0,
        })

        resp = await runner_process.rpc("execute", {
            "url": console_ui_server,
            "instruction": "确认页面加载完成",
        }, timeout=60)
        assert resp["success"] is True

        result = resp["result"]
        # 结构化字段验证
        assert "session_id" in result
        assert "page_url" in result
        assert "page_title" in result
        assert "duration" in result
        assert isinstance(result["duration"], int)
        assert result["duration"] >= 0
        assert "llm_usage" in result


class TestSessionLifecycle:
    """验证完整的 session 生命周期：navigate → get_page_info → screenshot → close。"""

    async def test_full_lifecycle(
        self, runner_process, mock_llm, console_ui_server,
    ):
        await runner_process.rpc("init", {
            "headless": True,
            "browserType": "chromium",
            "apiBase": mock_llm,
            "apiKey": "mock-key",
            "model": "mock-model",
            "maxSteps": 3,
            "stepDelay": 0,
        })

        # 1. execute 创建 session
        resp = await runner_process.rpc("execute", {
            "url": console_ui_server,
            "instruction": "查看页面",
        }, timeout=60)
        assert resp["success"] is True
        session_id = resp["result"]["session_id"]

        # 2. list_sessions 应包含该 session
        resp = await runner_process.rpc("list_sessions")
        assert session_id in resp["result"]["sessions"]

        # 3. get_page_info
        resp = await runner_process.rpc("get_page_info", {
            "session_id": session_id,
        })
        assert resp["success"] is True
        info = resp["result"]
        assert "page_url" in info
        assert "page_title" in info
        assert "viewport" in info
        assert "x" in info["viewport"]  # 格式: "1280x720"

        # 4. screenshot
        resp = await runner_process.rpc("screenshot", {
            "session_id": session_id,
        })
        assert resp["success"] is True
        assert resp["result"].get("data")

        # 5. close_session
        resp = await runner_process.rpc("close_session", {
            "session_id": session_id,
        })
        assert resp["success"] is True

        # 6. list_sessions 不再包含该 session
        resp = await runner_process.rpc("list_sessions")
        assert session_id not in resp["result"]["sessions"]
