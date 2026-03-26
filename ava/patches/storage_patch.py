"""SQLite storage patch for nanobot SessionManager."""

from __future__ import annotations

from pathlib import Path

from typing import Any

from loguru import logger

from ava.launcher import register_patch
from ava.storage import Database


def apply_storage_patch() -> str:
    """
    Patch SessionManager to use SQLite instead of JSONL for session storage.

    Returns:
        Description of what was patched.
    """
    from nanobot.config.paths import get_workspace_path
    from nanobot.session.manager import SessionManager, Session

    workspace = get_workspace_path()
    db_path = workspace / "data" / "nanobot.db"
    db = Database(db_path)

    original_save = SessionManager.save
    original_load = SessionManager._load
    original_list = SessionManager.list_sessions

    def patched_save(self: SessionManager, session: Session) -> None:
        """Save session to SQLite database."""
        conn = db._get_conn()
        
        metadata_json = __import__("json").dumps(session.metadata, ensure_ascii=False)
        token_stats_json = __import__("json").dumps(
            session.metadata.get("token_stats", {}), ensure_ascii=False
        )
        
        conn.execute(
            """INSERT OR REPLACE INTO sessions
               (key, created_at, updated_at, metadata, last_consolidated, last_completed, token_stats)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session.key,
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
                metadata_json,
                session.last_consolidated,
                session.metadata.get("last_completed"),
                token_stats_json,
            ),
        )
        
        session_row = conn.execute(
            "SELECT id FROM sessions WHERE key = ?", (session.key,)
        ).fetchone()
        
        if session_row:
            session_id = session_row["id"]
            conn.execute("DELETE FROM session_messages WHERE session_id = ?", (session_id,))
            
            for seq, msg in enumerate(session.messages):
                tool_calls_json = __import__("json").dumps(
                    msg.get("tool_calls", []), ensure_ascii=False
                ) if msg.get("tool_calls") else None
                
                conn.execute(
                    """INSERT INTO session_messages
                       (session_id, seq, role, content, tool_calls, tool_call_id, name, reasoning_content, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session_id,
                        seq,
                        msg.get("role", ""),
                        msg.get("content") if isinstance(msg.get("content"), str) else __import__("json").dumps(msg.get("content"), ensure_ascii=False) if msg.get("content") else None,
                        tool_calls_json,
                        msg.get("tool_call_id"),
                        msg.get("name"),
                        msg.get("reasoning_content"),
                        msg.get("timestamp"),
                    ),
                )
        
        conn.commit()
        self._cache[session.key] = session

    def patched_load(self: SessionManager, key: str) -> Session | None:
        """Load session from SQLite database, then apply backfill."""
        conn = db._get_conn()

        session_row = conn.execute(
            "SELECT * FROM sessions WHERE key = ?", (key,)
        ).fetchone()

        if not session_row:
            return None

        messages = []
        msg_rows = conn.execute(
            "SELECT * FROM session_messages WHERE session_id = ? ORDER BY seq",
            (session_row["id"],),
        ).fetchall()

        for msg_row in msg_rows:
            msg = {
                "role": msg_row["role"],
                "content": msg_row["content"],
                "timestamp": msg_row["timestamp"],
            }
            if msg_row["tool_calls"]:
                msg["tool_calls"] = __import__("json").loads(msg_row["tool_calls"])
            if msg_row["tool_call_id"]:
                msg["tool_call_id"] = msg_row["tool_call_id"]
            if msg_row["name"]:
                msg["name"] = msg_row["name"]
            if msg_row["reasoning_content"]:
                msg["reasoning_content"] = msg_row["reasoning_content"]
            messages.append(msg)

        metadata = __import__("json").loads(session_row["metadata"])
        metadata["token_stats"] = __import__("json").loads(session_row["token_stats"])
        if session_row["last_completed"]:
            metadata["last_completed"] = session_row["last_completed"]

        session = Session(
            key=key,
            messages=messages,
            created_at=__import__("datetime").datetime.fromisoformat(session_row["created_at"]),
            metadata=metadata,
            last_consolidated=session_row["last_consolidated"],
        )

        # Apply backfill after SQLite load (replaces channel_patch's _load wrapper)
        try:
            from ava.session.backfill_turns import _backfill_messages
            fixed_messages, inserted, normalized = _backfill_messages(session.messages)
            if inserted > 0 or normalized > 0:
                session.messages = fixed_messages
                logger.info(
                    "Backfilled session {}: {} placeholders added, {} normalized",
                    key, inserted, normalized,
                )
        except Exception as exc:
            logger.warning("Backfill failed for session {}: {}", key, exc)

        return session

    def patched_list(self: SessionManager) -> list[dict[str, Any]]:
        """List all sessions from SQLite database."""
        conn = db._get_conn()
        rows = conn.execute(
            "SELECT key, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        
        return [
            {
                "key": row["key"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "path": str(db_path),
            }
            for row in rows
        ]

    SessionManager.save = patched_save
    SessionManager._load = patched_load
    SessionManager.list_sessions = patched_list

    # Share db with loop_patch so AgentLoop gets the same instance
    try:
        from ava.patches.loop_patch import set_shared_db
        set_shared_db(db)
    except Exception as exc:
        logger.warning("Could not share db with loop_patch: {}", exc)

    return "SessionManager patched to use SQLite storage"


register_patch("sqlite_storage", apply_storage_patch)
