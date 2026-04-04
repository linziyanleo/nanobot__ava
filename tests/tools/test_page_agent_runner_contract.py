"""Contract tests for page-agent runner and injected demo bundle shape."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "console-ui" / "e2e" / "page-agent-runner.mjs"
BUNDLE = ROOT / "console-ui" / "node_modules" / "page-agent" / "dist" / "iife" / "page-agent.demo.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_demo_bundle_exports_page_agent_constructor_shape():
    source = _read(BUNDLE)

    assert "window.PageAgent=PageAgent" in source
    assert "window.pageAgent=new PageAgent" in source
    assert "window.PageAgentCore" not in source
    assert "window.PageController" not in source


def test_runner_uses_bundle_constructor_instead_of_missing_namespace_exports():
    source = _read(RUNNER)

    assert "const PageAgent = window.PageAgent;" in source
    assert "new PageAgent({" in source
    assert "PageAgentCore" not in source
    assert "PageController" not in source


def test_runner_tracks_bridge_registration_on_session_side():
    source = _read(RUNNER)

    assert "activityBridgeExposed" in source
    assert "if (!session.activityBridgeExposed)" in source
    assert 'page.exposeFunction("__paOnActivity"' in source
    assert 'page.exposeFunction("__paOnStatus"' in source

