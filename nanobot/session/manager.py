"""Session management for conversation history.

Supports SQLite backend (primary) with JSONL fallback for legacy compatibility.
"""

import json
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from nanobot.config.paths import get_legacy_sessions_dir
from nanobot.utils.helpers import ensure_dir, safe_filename


@dataclass
class Session:
    """A conversation session.

    Stores messages in memory. Persistence is handled by SessionManager
    (SQLite primary, JSONL legacy fallback).

    Important: Messages are append-only for LLM cache efficiency.
    The consolidation process writes summaries to MEMORY.md/HISTORY.md
    but does NOT modify the messages list or get_history() output.
    """

    key: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_consolidated: int = 0
    last_completed: int | None = None
    token_stats: dict[str, int] = field(default_factory=lambda: {
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_tokens": 0,
        "llm_calls": 0,
    })

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

    @staticmethod
    def _is_assistant_final(msg: dict[str, Any]) -> bool:
        return msg.get("role") == "assistant" and not msg.get("tool_calls")

    @classmethod
    def compute_last_completed(cls, messages: list[dict[str, Any]]) -> int:
        """Return the end index (exclusive) of the last completed user turn."""
        waiting_user_reply = False
        saw_assistant = False
        last_completed = 0
        for idx, msg in enumerate(messages):
            role = msg.get("role")
            if role == "user":
                if waiting_user_reply and saw_assistant:
                    last_completed = idx
                waiting_user_reply = True
                saw_assistant = False
            elif role == "assistant":
                saw_assistant = True
                if not msg.get("tool_calls") and waiting_user_reply:
                    waiting_user_reply = False
                    saw_assistant = False
                    last_completed = idx + 1
        return last_completed

    @staticmethod
    def _find_legal_start(messages: list[dict[str, Any]]) -> int:
        """Find first index where every tool result has a matching assistant tool_call."""
        declared: set[str] = set()
        start = 0
        for i, msg in enumerate(messages):
            role = msg.get("role")
            if role == "assistant":
                for tc in msg.get("tool_calls") or []:
                    if isinstance(tc, dict) and tc.get("id"):
                        declared.add(str(tc["id"]))
            elif role == "tool":
                tid = msg.get("tool_call_id")
                if tid and str(tid) not in declared:
                    start = i + 1
                    declared.clear()
                    for prev in messages[start:i + 1]:
                        if prev.get("role") == "assistant":
                            for tc in prev.get("tool_calls") or []:
                                if isinstance(tc, dict) and tc.get("id"):
                                    declared.add(str(tc["id"]))
        return start

    def get_history(self, max_messages: int = 500) -> list[dict[str, Any]]:
        """Return unconsolidated messages for LLM input, aligned to a user turn."""
        cutoff = self.last_completed if isinstance(self.last_completed, int) and self.last_completed >= 0 else len(self.messages)
        cutoff = min(cutoff, len(self.messages))
        start = min(self.last_consolidated, cutoff)
        unconsolidated = self.messages[start:cutoff]
        sliced = unconsolidated[-max_messages:]

        for i, m in enumerate(sliced):
            if m.get("role") == "user":
                sliced = sliced[i:]
                break

        # Some providers reject orphan tool results if the matching assistant
        # tool_calls message fell outside the fixed-size history window.
        start = self._find_legal_start(sliced)
        if start:
            sliced = sliced[start:]
        out: list[dict[str, Any]] = []
        for m in sliced:
            entry: dict[str, Any] = {"role": m["role"], "content": m.get("content", "")}
            for k in ("tool_calls", "tool_call_id", "name"):
                if k in m:
                    entry[k] = m[k]
            out.append(entry)
        return out

    def clear(self) -> None:
        self.messages = []
        self.last_consolidated = 0
        self.last_completed = None
        self.updated_at = datetime.now()


class SessionManager:
    """Manages conversation sessions with SQLite backend (primary) or JSONL fallback."""

    def __init__(self, workspace: Path, db: Any | None = None):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(self.workspace / "sessions")
        self.legacy_sessions_dir = get_legacy_sessions_dir()
        self._cache: dict[str, Session] = {}
        self._db = db
        self._saved_counts: dict[str, int] = {}

    @property
    def _use_db(self) -> bool:
        return self._db is not None

    def _get_session_path(self, key: str) -> Path:
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"

    def _get_legacy_session_path(self, key: str) -> Path:
        safe_key = safe_filename(key.replace(":", "_"))
        return self.legacy_sessions_dir / f"{safe_key}.jsonl"

    def get_or_create(self, key: str) -> Session:
        if key in self._cache:
            return self._cache[key]

        session = self._load(key)
        if session is None:
            session = Session(key=key)
            if self._use_db:
                self._db.execute(
                    """INSERT OR IGNORE INTO sessions (key, created_at, updated_at)
                       VALUES (?, ?, ?)""",
                    (key, session.created_at.isoformat(), session.updated_at.isoformat()),
                )
                self._db.commit()

        self._cache[key] = session
        self._saved_counts[key] = len(session.messages)
        return session

    def _load(self, key: str) -> Session | None:
        if self._use_db:
            return self._load_from_db(key)
        return self._load_from_jsonl(key)

    def _load_from_db(self, key: str) -> Session | None:
        row = self._db.fetchone("SELECT * FROM sessions WHERE key = ?", (key,))
        if not row:
            return None

        session_id = row["id"]
        messages: list[dict[str, Any]] = []

        msg_rows = self._db.fetchall(
            "SELECT * FROM session_messages WHERE session_id = ? ORDER BY seq",
            (session_id,),
        )
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
                msg["content"] = ""
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

        meta = {}
        try:
            meta = json.loads(row["metadata"]) if row["metadata"] else {}
        except json.JSONDecodeError:
            pass

        ts = {}
        try:
            ts = json.loads(row["token_stats"]) if row["token_stats"] else {}
        except json.JSONDecodeError:
            pass

        last_completed = Session.compute_last_completed(messages)

        created_at = datetime.now()
        if row["created_at"]:
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except ValueError:
                pass

        return Session(
            key=key,
            messages=messages,
            created_at=created_at,
            metadata=meta,
            last_consolidated=row["last_consolidated"] or 0,
            last_completed=last_completed,
            token_stats=ts if ts else {
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "llm_calls": 0,
            },
        )

    def _load_from_jsonl(self, key: str) -> Session | None:
        """Legacy JSONL loader (fallback when no DB)."""
        path = self._get_session_path(key)
        if not path.exists():
            legacy_path = self._get_legacy_session_path(key)
            if legacy_path.exists():
                try:
                    shutil.move(str(legacy_path), str(path))
                    logger.info("Migrated session {} from legacy path", key)
                except Exception:
                    logger.exception("Failed to migrate session {}", key)

        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None
            last_consolidated = 0
            last_completed: int | None = None
            token_stats = {
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "llm_calls": 0,
            }

            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                        last_consolidated = data.get("last_consolidated", 0)
                        last_completed = data.get("last_completed")
                        token_stats = data.get("token_stats", token_stats)
                    else:
                        messages.append(data)

            last_completed = Session.compute_last_completed(messages)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata,
                last_consolidated=last_consolidated,
                last_completed=last_completed,
                token_stats=token_stats,
            )
        except Exception as e:
            logger.warning("Failed to load session {}: {}", key, e)
            return None

    def save(self, session: Session) -> None:
        if self._use_db:
            self._save_to_db(session)
        else:
            self._save_to_jsonl(session)

    def _save_to_db(self, session: Session) -> None:
        row = self._db.fetchone("SELECT id FROM sessions WHERE key = ?", (session.key,))
        if not row:
            self._db.execute(
                """INSERT INTO sessions (key, created_at, updated_at, metadata,
                   last_consolidated, last_completed, token_stats)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.key,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    json.dumps(session.metadata, ensure_ascii=False),
                    session.last_consolidated,
                    session.last_completed,
                    json.dumps(session.token_stats, ensure_ascii=False),
                ),
            )
            self._db.commit()
            row = self._db.fetchone("SELECT id FROM sessions WHERE key = ?", (session.key,))

        session_id = row["id"]
        prev_count = self._saved_counts.get(session.key, 0)
        new_messages = session.messages[prev_count:]

        for i, msg in enumerate(new_messages):
            seq = prev_count + i
            content = msg.get("content")
            if isinstance(content, list):
                content_str = json.dumps(content, ensure_ascii=False)
            elif content is None:
                content_str = None
            else:
                content_str = str(content)

            tool_calls_json = json.dumps(msg["tool_calls"], ensure_ascii=False) if msg.get("tool_calls") else None

            self._db.execute(
                """INSERT INTO session_messages
                   (session_id, seq, role, content, tool_calls, tool_call_id, name, reasoning_content, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    seq,
                    msg.get("role", ""),
                    content_str,
                    tool_calls_json,
                    msg.get("tool_call_id"),
                    msg.get("name"),
                    msg.get("reasoning_content"),
                    msg.get("timestamp"),
                ),
            )

        session.last_completed = Session.compute_last_completed(session.messages)
        self._db.execute(
            """UPDATE sessions SET updated_at=?, metadata=?, last_consolidated=?,
               last_completed=?, token_stats=? WHERE id=?""",
            (
                session.updated_at.isoformat(),
                json.dumps(session.metadata, ensure_ascii=False),
                session.last_consolidated,
                session.last_completed,
                json.dumps(session.token_stats, ensure_ascii=False),
                session_id,
            ),
        )
        self._db.commit()
        self._saved_counts[session.key] = len(session.messages)
        self._cache[session.key] = session

    def _save_to_jsonl(self, session: Session) -> None:
        """Legacy JSONL saver."""
        path = self._get_session_path(session.key)
        with open(path, "w", encoding="utf-8") as f:
            metadata_line = {
                "_type": "metadata",
                "key": session.key,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata,
                "last_consolidated": session.last_consolidated,
                "last_completed": session.last_completed,
                "token_stats": session.token_stats,
            }
            f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
            for msg in session.messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self._cache[session.key] = session

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)
        self._saved_counts.pop(key, None)

    def delete_session(self, key: str) -> None:
        """Delete a session from DB and cache."""
        if self._use_db:
            self._db.execute("DELETE FROM sessions WHERE key = ?", (key,))
            self._db.commit()
        else:
            path = self._get_session_path(key)
            if path.exists():
                path.unlink()
        self.invalidate(key)

    def list_sessions(self) -> list[dict[str, Any]]:
        if self._use_db:
            rows = self._db.fetchall(
                "SELECT key, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
            )
            return [
                {
                    "key": r["key"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]

        sessions = []
        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            key = data.get("key") or path.stem.replace("_", ":", 1)
                            sessions.append({
                                "key": key,
                                "created_at": data.get("created_at"),
                                "updated_at": data.get("updated_at"),
                                "path": str(path)
                            })
            except Exception:
                continue
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)

    def search_messages(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search session messages by content (SQLite only)."""
        if not self._use_db:
            return []
        rows = self._db.fetchall(
            """SELECT s.key, sm.seq, sm.role, sm.content, sm.timestamp
               FROM session_messages sm
               JOIN sessions s ON s.id = sm.session_id
               WHERE sm.content LIKE ?
               ORDER BY sm.timestamp DESC LIMIT ?""",
            (f"%{query}%", limit),
        )
        return [dict(r) for r in rows]
