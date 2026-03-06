"""Chat session management for console conversations."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Awaitable


class ChatService:
    def __init__(self, agent_loop, workspace: Path):
        self._agent = agent_loop
        self._sessions_dir = workspace / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def list_sessions(self, user_id: str | None = None) -> list[dict]:
        sessions = []
        for f in self._sessions_dir.glob("console_*.jsonl"):
            sid = f.stem.removeprefix("console_")
            first_line = ""
            lines = f.read_text("utf-8").splitlines()
            if lines:
                first_line = lines[0]
            title = sid
            created_at = ""
            msg_count = max(0, len(lines) - 1)
            if first_line:
                try:
                    parsed = json.loads(first_line)
                    if parsed.get("_type") == "metadata":
                        title = parsed.get("title", parsed.get("key", sid))
                        created_at = parsed.get("created_at", "")
                except json.JSONDecodeError:
                    pass
            sessions.append({
                "session_id": sid,
                "title": title,
                "created_at": created_at,
                "message_count": msg_count,
            })
        sessions.sort(key=lambda s: s["created_at"], reverse=True)
        return sessions

    def create_session(self, user_id: str, title: str = "") -> str:
        sid = uuid.uuid4().hex[:8]
        now = datetime.now(timezone.utc).isoformat()
        session_title = title or f"Session {sid}"
        session_key = f"console:{sid}"

        session_file = self._sessions_dir / f"console_{sid}.jsonl"
        metadata_line = json.dumps({
            "_type": "metadata",
            "key": session_key,
            "created_at": now,
            "updated_at": now,
            "title": session_title,
            "user": user_id,
            "token_stats": {
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "llm_calls": 0,
            },
        }, ensure_ascii=False)
        session_file.write_text(metadata_line + "\n", "utf-8")
        return sid

    async def send_message(
        self,
        session_id: str,
        message: str,
        user_id: str,
        on_progress: Callable[..., Awaitable[None]] | None = None,
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
        session_file = self._sessions_dir / f"console_{session_id}.jsonl"
        if not session_file.exists():
            return False
        session_file.unlink()
        return True
