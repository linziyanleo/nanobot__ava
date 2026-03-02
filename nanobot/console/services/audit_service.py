"""Audit logging with JSONL file storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from nanobot.console.models import AuditEntry


class AuditService:
    def __init__(self, console_dir: Path):
        self._file = console_dir / "audit.jsonl"
        console_dir.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        user: str,
        role: str,
        action: str,
        target: str,
        detail: dict | None = None,
        ip: str = "",
    ) -> None:
        entry = AuditEntry(
            ts=datetime.now(timezone.utc).isoformat(),
            user=user,
            role=role,
            action=action,
            target=target,
            detail=detail,
            ip=ip,
        )
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")

    def query(
        self,
        page: int = 1,
        size: int = 50,
        user: str | None = None,
        action: str | None = None,
    ) -> dict:
        if not self._file.exists():
            return {"entries": [], "total": 0, "page": page, "size": size}

        all_entries: list[AuditEntry] = []
        for line in self._file.read_text("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = AuditEntry.model_validate_json(line)
                if user and entry.user != user:
                    continue
                if action and entry.action != action:
                    continue
                all_entries.append(entry)
            except Exception:
                continue

        all_entries.reverse()
        total = len(all_entries)
        start = (page - 1) * size
        page_entries = all_entries[start : start + size]

        return {
            "entries": [e.model_dump() for e in page_entries],
            "total": total,
            "page": page,
            "size": size,
        }
