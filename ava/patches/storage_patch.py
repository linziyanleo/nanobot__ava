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
    from nanobot.config.paths import get_data_dir
    from nanobot.session.manager import SessionManager, Session

    db_path = get_data_dir() / "nanobot.db"
    db = Database(db_path)

    # Register global singleton so other patches (skills_patch) can access it
    from ava.storage import set_db
    set_db(db)

    original_save = SessionManager.save
    original_load = SessionManager._load
    original_list = SessionManager.list_sessions

    def patched_save(self: SessionManager, session: Session) -> None:
        """Save session to SQLite database (incremental append).

        Only inserts messages whose seq >= current DB count, avoiding the
        destructive DELETE-then-INSERT pattern that caused history loss.
        A full rewrite is only performed when messages were actually removed
        from the in-memory list (e.g. session.clear() or retain_recent_legal_suffix).
        """
        import json as _json

        conn = db._get_conn()

        metadata_json = _json.dumps(session.metadata, ensure_ascii=False)
        token_stats_json = _json.dumps(
            session.metadata.get("token_stats", {}), ensure_ascii=False
        )

        conn.execute(
            """INSERT INTO sessions
               (key, created_at, updated_at, metadata, last_consolidated, last_completed, token_stats)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   updated_at = excluded.updated_at,
                   metadata = excluded.metadata,
                   last_consolidated = excluded.last_consolidated,
                   last_completed = excluded.last_completed,
                   token_stats = excluded.token_stats""",
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

            # Count existing messages in DB
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM session_messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            db_count = row["cnt"] if row else 0

            mem_count = len(session.messages)

            # Detect if messages were reset (clear/retain/reassigned):
            # Compare first message timestamp — if it differs, the list was rebuilt.
            needs_rewrite = mem_count < db_count
            if not needs_rewrite and db_count > 0 and mem_count > 0:
                first_db = conn.execute(
                    "SELECT timestamp FROM session_messages WHERE session_id = ? AND seq = 0",
                    (session_id,),
                ).fetchone()
                if first_db:
                    mem_ts = session.messages[0].get("timestamp", "")
                    if first_db["timestamp"] != mem_ts:
                        needs_rewrite = True

            if needs_rewrite:
                conn.execute("DELETE FROM session_messages WHERE session_id = ?", (session_id,))
                start_seq = 0
            else:
                # Incremental: only append new messages
                start_seq = db_count

            for seq in range(start_seq, mem_count):
                msg = session.messages[seq]
                tool_calls_json = (
                    _json.dumps(msg.get("tool_calls", []), ensure_ascii=False)
                    if msg.get("tool_calls") else None
                )
                content = msg.get("content")
                if content is not None and not isinstance(content, str):
                    content = _json.dumps(content, ensure_ascii=False)

                conn.execute(
                    """INSERT INTO session_messages
                       (session_id, seq, role, content, tool_calls, tool_call_id, name, reasoning_content, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session_id,
                        seq,
                        msg.get("role", ""),
                        content,
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
