"""Gateway process control."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from loguru import logger

from ava.console.models import GatewayStatus

_GATEWAY_PID_FILE = Path.home() / ".nanobot" / "gateway.pid"


class GatewayService:
    def __init__(
        self,
        skill_dir: Path | None = None,
        gateway_port: int = 18790,
        console_port: int = 6688,
    ):
        self._skill_dir = skill_dir
        self._gateway_port = gateway_port
        self._console_port = console_port
        # Track background restart tasks to prevent resource leaks
        self._restart_task: asyncio.Task[dict[str, Any]] | None = None

    def _find_gateway_pid(self) -> int | None:
        if not _GATEWAY_PID_FILE.exists():
            return None
        try:
            pid = int(_GATEWAY_PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return pid
        except (ProcessLookupError, ValueError, PermissionError, OSError):
            return None

    def get_status(self) -> GatewayStatus:
        pid = self._find_gateway_pid()
        if pid is None:
            return GatewayStatus(running=False, gateway_port=self._gateway_port, console_port=self._console_port)

        try:
            result = subprocess.run(
                ["ps", "-o", "etime=", "-p", str(pid)],
                capture_output=True, text=True, timeout=5,
            )
            uptime_str = result.stdout.strip() if result.returncode == 0 else ""
            uptime_seconds = self._parse_etime(uptime_str) if uptime_str else None
        except subprocess.TimeoutExpired:
            uptime_seconds = None

        return GatewayStatus(running=True, pid=pid, uptime_seconds=uptime_seconds, gateway_port=self._gateway_port, console_port=self._console_port)

    @staticmethod
    def _parse_etime(etime: str) -> float:
        """Parse ps etime format: [[DD-]HH:]MM:SS"""
        parts = etime.strip().replace("-", ":").split(":")
        parts = [int(p) for p in parts]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 4:
            return parts[0] * 86400 + parts[1] * 3600 + parts[2] * 60 + parts[3]
        return 0.0

    async def restart(self, delay_ms: int = 5000, force: bool = False) -> dict:
        if self._skill_dir:
            script = self._skill_dir / "restart_gateway" / "scripts" / "restart_gateway.sh"
            if script.exists():
                cmd = ["bash", str(script), "--delay", str(delay_ms), "--confirm"]
                if force:
                    cmd.append("--force")
                
                # Cancel any existing restart task to prevent resource leaks
                if self._restart_task and not self._restart_task.done():
                    self._restart_task.cancel()
                    
                    try:
                        await self._restart_task
                    except asyncio.CancelledError:
                        pass
                
                # Launch restart in a managed background task
                self._restart_task = asyncio.create_task(
                    self._run_restart_subprocess(cmd)
                )
                
                return {
                    "status": "restart_scheduled",
                    "delay_ms": delay_ms,
                    "force": force,
                    "message": f"Gateway restart scheduled in {delay_ms}ms",
                }

        return {"status": "error", "message": "Restart script not found"}

    async def _run_restart_subprocess(self, cmd: list[str]) -> dict[str, Any]:
        """Run restart script as a managed subprocess with proper resource cleanup."""
        process: asyncio.subprocess.Process | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # Wait for process and consume pipes to prevent resource leaks
            # Use a generous timeout since restart script may sleep
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=120.0,  # 2 minutes max
            )
            if process.returncode != 0:
                logger.warning(
                    "Gateway restart script exited with code {}: {}",
                    process.returncode,
                    stderr.decode(errors="replace")[:500] if stderr else "(no stderr)",
                )
            return {"status": "completed", "returncode": process.returncode}
        except asyncio.TimeoutError:
            if process:
                process.kill()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.error("Gateway restart process did not terminate after kill")
            return {"status": "timeout"}
        except asyncio.CancelledError:
            if process and process.returncode is None:
                process.kill()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
            raise
        except Exception as e:
            logger.error("Gateway restart subprocess error: {}", e)
            return {"status": "error", "message": str(e)}
