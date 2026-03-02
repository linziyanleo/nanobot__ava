"""Gateway process control."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import time
from pathlib import Path

from nanobot.console.models import GatewayStatus


class GatewayService:
    def __init__(self, skill_dir: Path | None = None):
        self._skill_dir = skill_dir

    def _find_gateway_pid(self) -> int | None:
        try:
            result = subprocess.run(
                ["pgrep", "-f", "nanobot gateway"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                my_pid = os.getpid()
                for line in result.stdout.strip().splitlines():
                    pid = int(line.strip())
                    if pid != my_pid:
                        return pid
        except (subprocess.TimeoutExpired, ValueError):
            pass
        return None

    def get_status(self) -> GatewayStatus:
        pid = self._find_gateway_pid()
        if pid is None:
            return GatewayStatus(running=False)

        try:
            result = subprocess.run(
                ["ps", "-o", "etime=", "-p", str(pid)],
                capture_output=True, text=True, timeout=5,
            )
            uptime_str = result.stdout.strip() if result.returncode == 0 else ""
            uptime_seconds = self._parse_etime(uptime_str) if uptime_str else None
        except subprocess.TimeoutExpired:
            uptime_seconds = None

        return GatewayStatus(running=True, pid=pid, uptime_seconds=uptime_seconds)

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
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                # Don't await — it's a background restart
                return {
                    "status": "restart_scheduled",
                    "delay_ms": delay_ms,
                    "force": force,
                    "message": f"Gateway restart scheduled in {delay_ms}ms",
                }

        return {"status": "error", "message": "Restart script not found"}
