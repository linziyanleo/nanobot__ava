"""Chat session management for console conversations."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Awaitable


class ChatService:
    def __init__(self, agent_loop, workspace: Path, db: Any | None = None):
        self._agent = agent_loop
        self._sessions_dir = workspace / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._db = db

    @property
    def _use_db(self) -> bool:
        return self._db is not None

    @staticmethod
    def _derive_scene(key: str) -> str:
        if key.startswith("telegram:"):
            return "telegram"
        if key.startswith("console:"):
            return "console"
        if key.startswith("cli:"):
            return "cli"
        if key.startswith("cron:"):
            return "cron"
        if key == "heartbeat":
            return "heartbeat"
        if key.startswith("feishu:"):
            return "feishu"
        if key.startswith("discord:"):
            return "discord"
        return "other"

    def list_sessions(self, user_id: str | None = None) -> list[dict]:
        if self._use_db:
            rows = self._db.fetchall(
                """SELECT s.key, s.created_at, s.updated_at, s.token_stats,
                          (SELECT COUNT(*) FROM session_messages WHERE session_id = s.id) as msg_count
                   FROM sessions s
                   ORDER BY s.updated_at DESC"""
            )
            sessions = []
            for r in rows:
                key = r["key"]
                ts: dict = {}
                if r["token_stats"]:
                    try:
                        ts = json.loads(r["token_stats"])
                    except json.JSONDecodeError:
                        pass
                sessions.append({
                    "key": key,
                    "scene": self._derive_scene(key),
                    "created_at": r["created_at"] or "",
                    "updated_at": r["updated_at"] or "",
                    "token_stats": {
                        "total_prompt_tokens": ts.get("total_prompt_tokens", 0),
                        "total_completion_tokens": ts.get("total_completion_tokens", 0),
                        "total_tokens": ts.get("total_tokens", 0),
                        "llm_calls": ts.get("llm_calls", 0),
                    },
                    "message_count": r["msg_count"],
                })
            return sessions

        sessions = []
        for f in self._sessions_dir.glob("*.jsonl"):
            if f.name.startswith("_"):
                continue
            first_line = ""
            lines = f.read_text("utf-8").splitlines()
            if lines:
                first_line = lines[0]
            key = f.stem.replace("_", ":", 1)
            created_at = ""
            updated_at = ""
            token_stats = {
                "total_prompt_tokens": 0, "total_completion_tokens": 0,
                "total_tokens": 0, "llm_calls": 0,
            }
            msg_count = max(0, len(lines) - 1)
            if first_line:
                try:
                    parsed = json.loads(first_line)
                    if parsed.get("_type") == "metadata":
                        key = parsed.get("key", key)
                        created_at = parsed.get("created_at", "")
                        updated_at = parsed.get("updated_at", "")
                        token_stats = parsed.get("token_stats", token_stats)
                except json.JSONDecodeError:
                    pass
            sessions.append({
                "key": key,
                "scene": self._derive_scene(key),
                "created_at": created_at,
                "updated_at": updated_at,
                "token_stats": token_stats,
                "message_count": msg_count,
            })
        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return sessions

    def get_messages(self, session_key: str) -> list[dict]:
        """Return full message details for a session from DB or JSONL."""
        if self._use_db:
            row = self._db.fetchone("SELECT id FROM sessions WHERE key = ?", (session_key,))
            if not row:
                return []
            msg_rows = self._db.fetchall(
                """SELECT role, content, tool_calls, tool_call_id, name,
                          reasoning_content, timestamp
                   FROM session_messages
                   WHERE session_id = ?
                   ORDER BY seq""",
                (row["id"],),
            )
            messages: list[dict] = []
            for mr in msg_rows:
                msg: dict[str, Any] = {"role": mr["role"]}
                content = mr["content"]
                if content is not None:
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, list):
                            msg["content"] = parsed
                        else:
                            msg["content"] = content
                    except (json.JSONDecodeError, TypeError):
                        msg["content"] = content
                else:
                    msg["content"] = None
                if mr["tool_calls"]:
                    try:
                        msg["tool_calls"] = json.loads(mr["tool_calls"])
                    except json.JSONDecodeError:
                        pass
                if mr["tool_call_id"]:
                    msg["tool_call_id"] = mr["tool_call_id"]
                if mr["name"]:
                    msg["name"] = mr["name"]
                if mr["reasoning_content"]:
                    msg["reasoning_content"] = mr["reasoning_content"]
                if mr["timestamp"]:
                    msg["timestamp"] = mr["timestamp"]
                messages.append(msg)
            return messages

        safe_key = session_key.replace(":", "_")
        session_file = self._sessions_dir / f"{safe_key}.jsonl"
        if not session_file.exists():
            return []
        messages = []
        for line in session_file.read_text("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("_type") == "metadata":
                    continue
                if entry.get("role"):
                    messages.append(entry)
            except json.JSONDecodeError:
                continue
        return messages

    def create_session(self, user_id: str, title: str = "") -> str:
        sid = uuid.uuid4().hex[:8]
        now = datetime.now(timezone.utc).isoformat()
        session_title = title or f"Session {sid}"
        session_key = f"console:{sid}"

        if self._use_db:
            meta = json.dumps({"title": session_title, "user": user_id}, ensure_ascii=False)
            ts_json = json.dumps({
                "total_prompt_tokens": 0, "total_completion_tokens": 0,
                "total_tokens": 0, "llm_calls": 0,
            })
            self._db.execute(
                """INSERT INTO sessions (key, created_at, updated_at, metadata, token_stats)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_key, now, now, meta, ts_json),
            )
            self._db.commit()
        else:
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
        if self._use_db:
            session_key = f"console:{session_id}"
            row = self._db.fetchone("SELECT id FROM sessions WHERE key = ?", (session_key,))
            if not row:
                return []
            msg_rows = self._db.fetchall(
                """SELECT role, content, timestamp FROM session_messages
                   WHERE session_id = ? AND role IN ('user', 'assistant') AND content IS NOT NULL AND content != ''
                   ORDER BY seq""",
                (row["id"],),
            )
            return [
                {"role": r["role"], "content": r["content"], "timestamp": r["timestamp"] or ""}
                for r in msg_rows
            ]

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
        if self._use_db:
            session_key = f"console:{session_id}"
            self._db.execute("DELETE FROM sessions WHERE key = ?", (session_key,))
            self._db.commit()
            if self._agent and hasattr(self._agent, "sessions"):
                self._agent.sessions.invalidate(session_key)
            return True

        session_file = self._sessions_dir / f"console_{session_id}.jsonl"
        if not session_file.exists():
            return False
        session_file.unlink()
        return True
