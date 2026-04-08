"""page_agent 集成/E2E 测试的共享 fixture。"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, AsyncIterator

import pytest
import pytest_asyncio
from aiohttp import web

from tests.tools.mock_llm_server import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_SCRIPT = REPO_ROOT / "console-ui" / "e2e" / "page-agent-runner.mjs"
CONSOLE_UI_DIR = REPO_ROOT / "console-ui"


# ---------------------------------------------------------------------------
# node_bin: 查找 node 可执行文件
# ---------------------------------------------------------------------------

def _find_node_bin() -> str | None:
    """复用 page_agent 的 _find_node 逻辑。"""
    from ava.tools.page_agent import _find_node
    return _find_node()


@pytest.fixture(scope="session")
def node_bin() -> str:
    """返回 node 可执行文件路径，找不到则 skip。"""
    found = _find_node_bin()
    if not found:
        pytest.skip("node not found")
    return found


# ---------------------------------------------------------------------------
# runner_process: 启动/关闭 Node runner 子进程
# ---------------------------------------------------------------------------

class RunnerProcess:
    """封装 page-agent-runner.mjs 子进程的 stdin/stdout 通信。"""

    def __init__(self, proc: asyncio.subprocess.Process):
        self._proc = proc
        self._counter = 0
        self._lock = asyncio.Lock()

    @property
    def process(self) -> asyncio.subprocess.Process:
        return self._proc

    async def rpc(self, method: str, params: dict | None = None, timeout: float = 30) -> dict:
        """发送 JSON-RPC 请求并等待带相同 id 的响应。"""
        async with self._lock:
            self._counter += 1
            req_id = f"test-{self._counter}"
            msg = {"id": req_id, "method": method, "params": params or {}}
            line = json.dumps(msg, ensure_ascii=False) + "\n"
            self._proc.stdin.write(line.encode("utf-8"))
            await self._proc.stdin.drain()

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                raw = await asyncio.wait_for(
                    self._proc.stdout.readline(),
                    timeout=deadline - time.monotonic(),
                )
                if not raw:
                    raise RuntimeError("runner process stdout closed")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                # 跳过推送事件（无 id 字段）
                if data.get("id") == req_id:
                    return data
            raise TimeoutError(f"RPC {method} timed out after {timeout}s")

    async def shutdown(self) -> int:
        """发送 shutdown 并等待进程退出。"""
        try:
            resp = await self.rpc("shutdown", timeout=10)
            assert resp.get("success") is True
        except Exception:
            pass
        try:
            return await asyncio.wait_for(self._proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            self._proc.kill()
            return await self._proc.wait()


@pytest_asyncio.fixture
async def runner_process(node_bin: str) -> AsyncIterator[RunnerProcess]:
    """启动 runner 子进程，测试结束后 shutdown。"""
    env = os.environ.copy()
    node_dir = str(Path(node_bin).parent)
    if node_dir not in env.get("PATH", "").split(os.pathsep):
        env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")

    proc = await asyncio.create_subprocess_exec(
        node_bin, str(RUNNER_SCRIPT),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    runner = RunnerProcess(proc)
    yield runner
    await runner.shutdown()


# ---------------------------------------------------------------------------
# mock_llm: Mock LLM Server
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def mock_llm() -> AsyncIterator[str]:
    """启动 mock LLM server，返回 base_url（如 http://127.0.0.1:<port>）。"""
    app = create_app()
    app_runner = web.AppRunner(app)
    await app_runner.setup()
    site = web.TCPSite(app_runner, "127.0.0.1", 0)
    await site.start()

    # 获取实际绑定的端口
    sock = site._server.sockets[0]
    port = sock.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"

    yield base_url

    await app_runner.cleanup()


# ---------------------------------------------------------------------------
# console_ui_server: Vite dev server
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def console_ui_server(node_bin: str) -> str:
    """启动 console-ui vite dev server，返回 URL。session scope 避免重复启动。"""
    node_modules = CONSOLE_UI_DIR / "node_modules"
    if not node_modules.exists():
        pytest.skip("console-ui/node_modules not installed")

    npx_bin = str(Path(node_bin).parent / "npx")
    env = os.environ.copy()
    node_dir = str(Path(node_bin).parent)
    if node_dir not in env.get("PATH", "").split(os.pathsep):
        env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")

    port = 15173
    proc = subprocess.Popen(
        [npx_bin, "vite", "--port", str(port), "--strictPort"],
        cwd=str(CONSOLE_UI_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )

    # 等待 vite 就绪（最多 30 秒）
    url = f"http://localhost:{port}"
    deadline = time.monotonic() + 30
    ready = False
    while time.monotonic() < deadline:
        try:
            import urllib.request
            resp = urllib.request.urlopen(url, timeout=1)
            if resp.status == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.5)

    if not ready:
        proc.kill()
        pytest.skip("console-ui vite dev server failed to start")

    yield url

    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
