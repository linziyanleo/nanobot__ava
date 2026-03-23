import asyncio
from types import SimpleNamespace

import pytest

from nanobot.agent.tools.claude_code import ClaudeCodeTool


class _DummyProcess:
    async def communicate(self):
        return b'{"result":"ok"}', b""


@pytest.mark.asyncio
async def test_run_subprocess_works_without_injected_cc_config(tmp_path, monkeypatch) -> None:
    async def fake_create_subprocess_exec(*args, **kwargs):  # noqa: ANN001
        return _DummyProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    tool = ClaudeCodeTool(workspace=tmp_path)
    stdout, stderr = await tool._run_subprocess(["claude"], str(tmp_path), timeout=1)

    assert stderr == ""
    assert '"result":"ok"' in stdout


@pytest.mark.asyncio
async def test_run_subprocess_injects_cc_env_from_config(tmp_path, monkeypatch) -> None:
    captured_env: dict[str, str] = {}

    async def fake_create_subprocess_exec(*args, **kwargs):  # noqa: ANN001
        nonlocal captured_env
        captured_env = kwargs.get("env", {})
        return _DummyProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    cfg = SimpleNamespace(api_key="test-key", base_url="https://example.test")
    tool = ClaudeCodeTool(workspace=tmp_path, cc_config=cfg)
    await tool._run_subprocess(["claude"], str(tmp_path), timeout=1)

    assert captured_env.get("ANTHROPIC_API_KEY") == "test-key"
    assert captured_env.get("ANTHROPIC_BASE_URL") == "https://example.test"
