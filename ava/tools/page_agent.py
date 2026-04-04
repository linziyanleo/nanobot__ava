"""通用 PageAgent 页面操作工具。

通过常驻 Node runner 进程（page-agent-runner.mjs）管理 Playwright 浏览器，
在页面内注入 page-agent 实现自然语言操控网页。

通信协议：stdin/stdout JSON-RPC（每行一个 JSON）。
推送事件（frame/activity/status）无 id 字段，RPC 响应有 id 字段。
"""

from __future__ import annotations

import asyncio
import atexit
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from nanobot.agent.tools.base import Tool

_RUNNER_SCRIPT = Path(__file__).resolve().parents[2] / "console-ui" / "e2e" / "page-agent-runner.mjs"

_IDLE_TIMEOUT = 300  # 空闲 5 分钟自动回收 runner


class PageAgentTool(Tool):
    """Control web pages using natural language via page-agent + Playwright."""

    def __init__(
        self,
        config: Any | None = None,
        media_service: Any | None = None,
    ) -> None:
        self._config = config
        self._media_service = media_service
        # Runner 进程
        self._process: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task | None = None
        self._last_activity: float = time.monotonic()
        self._idle_task: asyncio.Task | None = None
        self._req_counter = 0
        # RPC 请求等待表
        self._pending: dict[str, asyncio.Future] = {}
        # 推送事件订阅者 { session_id: [callback, ...] }
        self._subscribers: dict[str, list[Callable]] = {}
        # 事件缓存：最近 N 条 activity 事件 + 最后一帧，供 WS 连接后回放
        self._event_buffer: dict[str, list[dict]] = {}  # session_id -> recent events
        self._last_frame: dict[str, dict] = {}  # session_id -> last frame event
        self._EVENT_BUFFER_SIZE = 50
        self._lock = asyncio.Lock()
        # Context
        self._channel = "cli"
        self._chat_id = "direct"
        # atexit 清理
        atexit.register(self._sync_cleanup)

    def set_context(self, channel: str, chat_id: str) -> None:
        self._channel = channel
        self._chat_id = chat_id

    # ------------------------------------------------------------------
    # Tool 接口
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "page_agent"

    @property
    def description(self) -> str:
        return (
            "Control web pages using natural language instructions. "
            "Can navigate to URLs, fill forms, click buttons, extract information, "
            "and take screenshots. Supports persistent browser sessions across calls."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["execute", "screenshot", "get_page_info", "close_session"],
                    "description": "Action to perform",
                },
                "url": {
                    "type": "string",
                    "description": (
                        "Target URL to navigate to (only for execute action, "
                        "optional if session already has a page open)"
                    ),
                },
                "instruction": {
                    "type": "string",
                    "description": "Natural language instruction for page operation (required for execute)",
                },
                "session_id": {
                    "type": "string",
                    "description": "Session ID for reusing browser context. Omit to auto-generate.",
                },
            },
            "required": ["action"],
        }

    async def execute(self, action: str, **kwargs: Any) -> str:
        if not self._is_enabled():
            return "Error: page_agent is disabled in config"

        if action == "execute":
            return await self._do_execute(kwargs)
        elif action == "screenshot":
            return await self._do_screenshot(kwargs)
        elif action == "get_page_info":
            return await self._do_get_page_info(kwargs)
        elif action == "close_session":
            return await self._do_close_session(kwargs)
        else:
            return f"Error: unknown action '{action}'"

    # ------------------------------------------------------------------
    # Action 实现
    # ------------------------------------------------------------------

    async def _do_execute(self, kwargs: dict) -> str:
        instruction = kwargs.get("instruction")
        if not instruction:
            return "Error: instruction is required for execute action"

        session_id = kwargs.get("session_id") or f"s_{uuid.uuid4().hex[:8]}"
        url = kwargs.get("url")

        result = await self._rpc("execute", {
            "url": url,
            "instruction": instruction,
            "session_id": session_id,
        })

        if not result.get("success"):
            return self._format_error_result(result, session_id)

        r = result.get("result", {})
        inner_success = r.get("success", True)
        status = "SUCCESS" if inner_success else "ERROR"
        steps = r.get("steps", 0)
        duration = r.get("duration", 0)
        parts = [
            f"[PageAgent {status}] session={r.get('session_id', session_id)} | Steps: {steps} | Duration: {duration}ms",
            f"URL: {r.get('page_url', 'unknown')}",
            f"Title: {r.get('page_title', 'unknown')}",
            "",
            r.get("data", "(no output)"),
        ]

        page_state = r.get("page_state") or {}
        state_lines = self._format_page_state(page_state)
        if state_lines:
            parts.append("")
            parts.append("--- Page State ---")
            parts.extend(state_lines)

        return "\n".join(parts)

    @staticmethod
    def _format_page_state(page_state: dict) -> list[str]:
        """将 runner 返回的页面结构化状态格式化为文本行。"""
        if not page_state:
            return []
        lines: list[str] = []
        headings = page_state.get("headings") or []
        if headings:
            lines.append("Headings: " + " > ".join(headings))
        alerts = page_state.get("alerts") or []
        if alerts:
            for a in alerts:
                lines.append(f"Alert: {a}")
        forms = page_state.get("forms") or []
        if forms:
            for i, form in enumerate(forms):
                inputs = form.get("inputs") or []
                if inputs:
                    fields = []
                    for inp in inputs:
                        name = inp.get("name") or inp.get("placeholder") or inp.get("type", "?")
                        filled = "filled" if inp.get("hasValue") else "empty"
                        fields.append(f"{name}({filled})")
                    lines.append(f"Form[{i}]: " + ", ".join(fields))
        buttons = page_state.get("buttons") or []
        if buttons:
            lines.append("Buttons: " + ", ".join(buttons))
        return lines

    @staticmethod
    def _format_error_result(result: dict, fallback_session_id: str) -> str:
        """将 RPC error / timeout 响应格式化为结构化文本。"""
        err = result.get("error", {})
        if isinstance(err, dict):
            code = err.get("code", "")
            msg = err.get("message", str(err))
            sid = err.get("session_id", fallback_session_id)
            duration = err.get("duration", 0)
            page_url = err.get("page_url", "unknown")
            page_title = err.get("page_title", "unknown")
        else:
            code, msg = "", str(err)
            sid, duration = fallback_session_id, 0
            page_url, page_title = "unknown", "unknown"

        status = "TIMEOUT" if code == "TIMEOUT" else "ERROR"
        parts = [
            f"[PageAgent {status}] session={sid} | Steps: 0 | Duration: {duration}ms",
            f"URL: {page_url}",
            f"Title: {page_title}",
            "",
            f"Error: {msg}",
        ]
        return "\n".join(parts)

    async def _do_screenshot(self, kwargs: dict) -> str:
        session_id = kwargs.get("session_id")
        if not session_id:
            return "Error: session_id is required for screenshot action"

        # 生成截图路径
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        screenshot_dir = self._get_screenshot_dir()
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        filename = f"page-agent-{ts}-{session_id[:8]}.png"
        save_path = str(screenshot_dir / filename)

        result = await self._rpc("screenshot", {
            "session_id": session_id,
            "path": save_path,
        })

        if not result.get("success"):
            err = result.get("error", {})
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            return f"Error: {msg}"

        # 写入 MediaService
        record_id = f"page-agent-{ts}"
        if self._media_service:
            try:
                self._media_service.write_record({
                    "id": record_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "prompt": f"[page_agent screenshot] session={session_id}",
                    "output_images": [filename],
                    "model": "page-agent",
                    "status": "success",
                })
            except Exception as e:
                logger.warning("page_agent: failed to write media record: {}", e)

        return (
            f"[PageAgent Screenshot]\n"
            f"Path: {save_path}\n"
            f"Media record: {record_id}"
        )

    async def _do_get_page_info(self, kwargs: dict) -> str:
        session_id = kwargs.get("session_id")
        if not session_id:
            return "Error: session_id is required for get_page_info action"

        result = await self._rpc("get_page_info", {"session_id": session_id})

        if not result.get("success"):
            err = result.get("error", {})
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            return f"Error: {msg}"

        r = result.get("result", {})
        return (
            f"URL: {r.get('page_url', 'unknown')}\n"
            f"Title: {r.get('page_title', 'unknown')}\n"
            f"Viewport: {r.get('viewport', 'unknown')}"
        )

    async def _do_close_session(self, kwargs: dict) -> str:
        session_id = kwargs.get("session_id")
        if not session_id:
            return "Error: session_id is required for close_session action"

        result = await self._rpc("close_session", {"session_id": session_id})

        if not result.get("success"):
            err = result.get("error", {})
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            return f"Error: {msg}"

        # 清理事件缓存
        self._event_buffer.pop(session_id, None)
        self._last_frame.pop(session_id, None)

        return f"Session {session_id} closed."

    # ------------------------------------------------------------------
    # Screencast 订阅（供 console WS 路由使用）
    # ------------------------------------------------------------------

    async def start_screencast(self, session_id: str, **params: Any) -> dict:
        """启动指定会话的 CDP 帧流。"""
        return await self._rpc("start_screencast", {"session_id": session_id, **params})

    async def stop_screencast(self, session_id: str) -> dict:
        """停止指定会话的 CDP 帧流。"""
        return await self._rpc("stop_screencast", {"session_id": session_id})

    async def get_page_info(self, session_id: str) -> dict[str, Any]:
        """返回结构化页面信息，供 console WS 初始化状态。"""
        return await self._rpc("get_page_info", {"session_id": session_id})

    async def list_sessions(self) -> list[str]:
        """返回 runner 当前持有的会话列表。"""
        if not self._process or self._process.returncode is not None:
            return []

        result = await self._rpc("list_sessions", {})
        if not result.get("success"):
            return []

        sessions = result.get("result", {}).get("sessions", [])
        return [session_id for session_id in sessions if isinstance(session_id, str)]

    def subscribe(self, session_id: str, callback: Callable) -> None:
        """注册推送事件回调（frame/activity/status）。同时回放缓存事件。"""
        if session_id not in self._subscribers:
            self._subscribers[session_id] = []
        self._subscribers[session_id].append(callback)

        # 回放缓存的 activity/status 事件
        for evt in self._event_buffer.get(session_id, []):
            try:
                callback(evt)
            except Exception:
                pass
        # 回放最后一帧
        last_frame = self._last_frame.get(session_id)
        if last_frame:
            try:
                callback(last_frame)
            except Exception:
                pass

    def unsubscribe(self, session_id: str, callback: Callable) -> None:
        """移除推送事件回调。"""
        cbs = self._subscribers.get(session_id, [])
        if callback in cbs:
            cbs.remove(callback)
        if not cbs:
            self._subscribers.pop(session_id, None)

    def get_active_sessions(self) -> list[str]:
        """返回当前已有订阅者的 session id 列表。"""
        return list(self._subscribers.keys())

    # ------------------------------------------------------------------
    # Runner 进程管理
    # ------------------------------------------------------------------

    async def _ensure_runner(self) -> None:
        """懒启动 runner 进程。"""
        async with self._lock:
            if self._process and self._process.returncode is None:
                return

            node_bin = shutil.which("node")
            if not node_bin:
                raise RuntimeError("node not found in PATH")

            if not _RUNNER_SCRIPT.exists():
                raise RuntimeError(f"runner script not found: {_RUNNER_SCRIPT}")

            self._process = await asyncio.create_subprocess_exec(
                node_bin, str(_RUNNER_SCRIPT),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy(),
            )
            logger.info("page_agent: runner started (pid={})", self._process.pid)

            # 后台读取 stdout
            self._reader_task = asyncio.create_task(self._read_stdout())

            # 后台读取 stderr（日志/心跳）
            asyncio.create_task(self._read_stderr())

            # 空闲回收
            self._idle_task = asyncio.create_task(self._idle_watchdog())

            # 发送 init 配置（直接写 stdin，不走 _rpc 以避免重入 lock）
            await self._send_init_direct()

    async def _send_init_direct(self) -> None:
        """在 lock 内直接发送 init，绕过 _rpc 避免死锁。"""
        cfg = self._config
        api_key = ""
        if cfg:
            api_key = getattr(cfg, "api_key", "") or ""
            if not api_key:
                env_name = getattr(cfg, "api_key_env", "PAGE_AGENT_API_KEY")
                api_key = os.environ.get(env_name, "")

        params = {
            "headless": getattr(cfg, "headless", True) if cfg else True,
            "browserType": getattr(cfg, "browser_type", "chromium") if cfg else "chromium",
            "viewportWidth": getattr(cfg, "viewport_width", 1280) if cfg else 1280,
            "viewportHeight": getattr(cfg, "viewport_height", 720) if cfg else 720,
            "apiBase": getattr(cfg, "api_base", "") if cfg else "",
            "apiKey": api_key,
            "model": getattr(cfg, "model", "") if cfg else "",
            "maxSteps": getattr(cfg, "max_steps", 40) if cfg else 40,
            "stepDelay": getattr(cfg, "step_delay", 0.4) if cfg else 0.4,
            "language": getattr(cfg, "language", "zh-CN") if cfg else "zh-CN",
        }

        self._req_counter += 1
        req_id = f"req-{self._req_counter}"
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[req_id] = fut

        await self._write_stdin({"id": req_id, "method": "init", "params": params})

        try:
            await asyncio.wait_for(fut, timeout=10)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            logger.warning("page_agent: init RPC timeout")

    async def _read_stdout(self) -> None:
        """持续读取 runner stdout，分发 RPC 响应和推送事件。"""
        assert self._process and self._process.stdout
        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode("utf-8", errors="replace").strip())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                # 有 id -> RPC 响应
                msg_id = msg.get("id")
                if msg_id and msg_id in self._pending:
                    fut = self._pending.pop(msg_id)
                    if not fut.done():
                        fut.set_result(msg)
                    continue

                # 无 id -> 推送事件（frame/activity/status）
                session_id = msg.get("session_id")
                if not session_id:
                    continue

                # 缓存事件（无论是否有订阅者）
                msg_type = msg.get("type")
                if msg_type == "frame":
                    self._last_frame[session_id] = msg
                elif msg_type in ("activity", "status"):
                    buf = self._event_buffer.setdefault(session_id, [])
                    buf.append(msg)
                    if len(buf) > self._EVENT_BUFFER_SIZE:
                        buf[:] = buf[-self._EVENT_BUFFER_SIZE:]

                # 分发给订阅者
                if session_id in self._subscribers:
                    for cb in self._subscribers[session_id]:
                        try:
                            cb(msg)
                        except Exception:
                            pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("page_agent: stdout reader error: {}", e)
        finally:
            # runner 退出，清理所有 pending futures
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_result({
                        "success": False,
                        "error": {"code": "RUNNER_EXIT", "message": "runner process exited"},
                    })
            self._pending.clear()

    async def _read_stderr(self) -> None:
        """读取 runner stderr（日志/心跳）。"""
        assert self._process and self._process.stderr
        try:
            while True:
                line = await self._process.stderr.readline()
                if not line:
                    break
                logger.debug("page_agent runner: {}", line.decode("utf-8", errors="replace").rstrip())
        except (asyncio.CancelledError, Exception):
            pass

    async def _idle_watchdog(self) -> None:
        """空闲超时自动关闭 runner。"""
        try:
            while True:
                await asyncio.sleep(60)
                if time.monotonic() - self._last_activity > _IDLE_TIMEOUT:
                    logger.info("page_agent: idle timeout, shutting down runner")
                    await self._shutdown_runner()
                    break
        except asyncio.CancelledError:
            pass

    async def _shutdown_runner(self) -> None:
        """优雅关闭 runner 进程。"""
        if not self._process or self._process.returncode is not None:
            return

        try:
            await self._write_stdin({"id": "shutdown", "method": "shutdown", "params": {}})
            await asyncio.wait_for(self._process.wait(), timeout=5)
        except (asyncio.TimeoutError, Exception):
            try:
                self._process.kill()
            except Exception:
                pass

        self._process = None
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
        if self._idle_task:
            self._idle_task.cancel()
            self._idle_task = None

    def _sync_cleanup(self) -> None:
        """atexit 同步清理。"""
        if self._process and self._process.returncode is None:
            try:
                self._process.kill()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # RPC 通信
    # ------------------------------------------------------------------

    async def _rpc(self, method: str, params: dict) -> dict:
        """发送 RPC 请求并等待响应。"""
        await self._ensure_runner()
        self._last_activity = time.monotonic()

        self._req_counter += 1
        req_id = f"req-{self._req_counter}"

        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[req_id] = fut

        await self._write_stdin({"id": req_id, "method": method, "params": params})

        timeout = getattr(self._config, "timeout", 120) if self._config else 120
        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            return {
                "success": False,
                "error": {"code": "TIMEOUT", "message": f"RPC timeout after {timeout}s"},
            }

    async def _write_stdin(self, msg: dict) -> None:
        """向 runner stdin 写入一行 JSON 并 flush。"""
        if not self._process or not self._process.stdin:
            return
        data = json.dumps(msg, ensure_ascii=False) + "\n"
        self._process.stdin.write(data.encode("utf-8"))
        await self._process.stdin.drain()

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _is_enabled(self) -> bool:
        if self._config is None:
            return True
        return getattr(self._config, "enabled", True)

    def _get_screenshot_dir(self) -> Path:
        if self._config:
            custom = getattr(self._config, "screenshot_dir", "")
            if custom:
                return Path(custom).expanduser()
        return Path.home() / ".nanobot" / "media" / "generated"
