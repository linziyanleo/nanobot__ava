"""Backfill incomplete conversation turns in session JSONL files."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from nanobot.session.manager import Session

PLACEHOLDER_TEXT = (
    "[auto-backfill] This historical turn had no final assistant reply. "
    "A placeholder was inserted to preserve turn integrity."
)


def _is_assistant_final(msg: dict[str, Any]) -> bool:
    return msg.get("role") == "assistant" and not msg.get("tool_calls")


def _placeholder_message() -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": PLACEHOLDER_TEXT,
        "timestamp": datetime.now().isoformat(),
        "metadata": {"auto_backfill": True},
    }


def _backfill_messages(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Insert assistant placeholders for unresolved user turns."""
    out: list[dict[str, Any]] = []
    pending_user = False
    inserted = 0

    for msg in messages:
        role = msg.get("role")
        if role == "user":
            if pending_user:
                out.append(_placeholder_message())
                inserted += 1
            pending_user = True
            out.append(msg)
            continue

        out.append(msg)
        if _is_assistant_final(msg) and pending_user:
            pending_user = False

    if pending_user:
        out.append(_placeholder_message())
        inserted += 1

    return out, inserted


def _load_session(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metadata_line: dict[str, Any] | None = None
    messages: list[dict[str, Any]] = []

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if data.get("_type") == "metadata" and metadata_line is None:
                metadata_line = data
            else:
                messages.append(data)

    if metadata_line is None:
        now = datetime.now().isoformat()
        key = path.stem.replace("_", ":", 1)
        metadata_line = {
            "_type": "metadata",
            "key": key,
            "created_at": now,
            "updated_at": now,
            "metadata": {},
            "last_consolidated": 0,
        }

    return metadata_line, messages


def _save_session(path: Path, metadata_line: dict[str, Any], messages: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
        for msg in messages:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")


def backfill_workspace_sessions(workspace: Path, dry_run: bool = False) -> dict[str, int]:
    sessions_dir = workspace / "sessions"
    if not sessions_dir.exists():
        return {"files_scanned": 0, "files_changed": 0, "placeholders_added": 0}

    scanned = 0
    changed = 0
    placeholders = 0

    for session_file in sorted(sessions_dir.glob("*.jsonl")):
        scanned += 1
        metadata_line, messages = _load_session(session_file)
        fixed_messages, inserted = _backfill_messages(messages)
        computed_completed = Session.compute_last_completed(fixed_messages)
        old_completed = metadata_line.get("last_completed")
        needs_checkpoint_update = old_completed != computed_completed

        if inserted == 0 and not needs_checkpoint_update:
            continue

        changed += 1
        placeholders += inserted

        metadata_line["updated_at"] = datetime.now().isoformat()
        metadata_line["last_completed"] = computed_completed
        metadata_line.setdefault("metadata", {})
        metadata_line["metadata"]["auto_backfill"] = True

        if not dry_run:
            _save_session(session_file, metadata_line, fixed_messages)

    return {
        "files_scanned": scanned,
        "files_changed": changed,
        "placeholders_added": placeholders,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill incomplete turns in session JSONL files.")
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Workspace path that contains the sessions directory.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing files.")
    args = parser.parse_args()

    stats = backfill_workspace_sessions(args.workspace, dry_run=args.dry_run)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
