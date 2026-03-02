"""Chat session management for console conversations."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Callable, Awaitable


class ChatService:
    def __init__(self, agent_loop, workspace: Path):
        self._agent = agent_loop
        self._sessions_dir = workspace / "sessions"
        self._meta_file = workspace / "sessions" / "_console_meta.json"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def _load_meta(self) -> dict:
        if self._meta_file.exists():
            return json.loads(self._meta_file.read_text("utf-8"))
        return {}

    def _save_meta(self, meta: dict) -> None:
        self._meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), "utf-8")

    def list_sessions(self, user_id: str | None = None) -> list[dict]:
        meta = self._load_meta()
        sessions = []
        for sid, info in meta.items():
            if user_id and info.get("user") != user_id:
                continue
            session_file = self._sessions_dir / f"console_{sid}.jsonl"
            msg_count = 0
            if session_file.exists():
                msg_count = sum(1 for line in session_file.read_text("utf-8").splitlines() if line.strip())
            sessions.append({
                "session_id": sid,
                "title": info.get("title", ""),
                "created_at": info.get("created_at", ""),
                "message_count": msg_count,
            })
        sessions.sort(key=lambda s: s["created_at"], reverse=True)
        return sessions

    def create_session(self, user_id: str, title: str = "") -> str:
        sid = uuid.uuid4().hex[:8]
        meta = self._load_meta()
        meta[sid] = {
            "user": user_id,
            "title": title or f"Session {len(meta) + 1}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_meta(meta)
        return sid

    async def send_message(
        self,
        session_id: str,
        message: str,
        user_id: str,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        session_key = f"console:{session_id}"
        response = await self._agent.process_direct(
            content=message,
            session_key=session_key,
            channel="console",
            chat_id=user_id,
            on_progress=on_progress,
        )
        return response or ""

    def get_history(self, session_id: str) -> list[dict]:
        session_file = self._sessions_dir / f"console_{session_id}.jsonl"
        if not session_file.exists():
            return []

        messages = []
        for line in session_file.read_text("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                role = entry.get("role", "")
                content = entry.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({
                        "role": role,
                        "content": content,
                        "timestamp": entry.get("timestamp", ""),
                    })
            except json.JSONDecodeError:
                continue
        return messages

    def delete_session(self, session_id: str) -> bool:
        meta = self._load_meta()
        if session_id not in meta:
            return False
        del meta[session_id]
        self._save_meta(meta)
        session_file = self._sessions_dir / f"console_{session_id}.jsonl"
        if session_file.exists():
            session_file.unlink()
        return True
