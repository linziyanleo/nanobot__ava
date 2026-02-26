"""Memory tool for agent-driven categorized memory operations."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.categorized_memory import CategorizedMemoryStore


class MemoryTool(Tool):
    """Tool for the agent to recall, remember, and manage categorized memory."""

    def __init__(self, store: CategorizedMemoryStore) -> None:
        self._store = store
        self._channel: str = ""
        self._chat_id: str = ""

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current conversation context for identity resolution."""
        self._channel = channel
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "memory"

    @property
    def description(self) -> str:
        return (
            "Manage categorized memory. Actions:\n"
            "- recall: Retrieve memory for a person or the current user\n"
            "- remember: Store a memory note for the current person\n"
            "- list_persons: List all known persons and their IDs\n"
            "- map_identity: Link the current channel:id to a person name\n"
            "- search_history: Search history logs with a keyword"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["recall", "remember", "list_persons", "map_identity", "search_history"],
                    "description": "The memory action to perform",
                },
                "content": {
                    "type": "string",
                    "description": "Content to store (for 'remember') or search query (for 'search_history')",
                },
                "person": {
                    "type": "string",
                    "description": "Person name to target (optional, defaults to current user)",
                },
                "scope": {
                    "type": "string",
                    "enum": ["person", "source"],
                    "description": "Memory scope: 'person' (cross-channel) or 'source' (channel-specific). Default: person",
                },
                "display_name": {
                    "type": "string",
                    "description": "Display name for the person (for 'map_identity')",
                },
            },
            "required": ["action"],
        }

    async def execute(self, action: str, **kwargs: Any) -> str:
        if action == "recall":
            return self._recall(**kwargs)
        elif action == "remember":
            return self._remember(**kwargs)
        elif action == "list_persons":
            return self._list_persons()
        elif action == "map_identity":
            return self._map_identity(**kwargs)
        elif action == "search_history":
            return self._search_history(**kwargs)
        else:
            return f"Unknown action: {action}. Use: recall, remember, list_persons, map_identity, search_history"

    def _recall(self, person: str | None = None, scope: str = "person", **_: Any) -> str:
        """Retrieve memory for a person or the current user."""
        if person:
            target = person
        else:
            target = self._store.resolve_person(self._channel, self._chat_id)

        if not target:
            return "No person identity mapped for the current session. Use map_identity first, or specify a person name."

        if scope == "source":
            mem = self._store.get_source_memory(self._channel, self._chat_id)
            label = f"Source memory ({self._channel}:{self._chat_id})"
        else:
            mem = self._store.get_person_memory(target)
            label = f"Person memory ({target})"

        if not mem:
            return f"{label}: (empty)"
        return f"{label}:\n{mem}"

    def _remember(self, content: str | None = None, scope: str = "person", person: str | None = None, **_: Any) -> str:
        """Store a memory note."""
        if not content:
            return "Error: 'content' is required for remember action."

        if person:
            target = person
        else:
            target = self._store.resolve_person(self._channel, self._chat_id)

        if not target:
            return "No person identity mapped for the current session. Use map_identity first, or specify a person name."

        if scope == "source":
            existing = self._store.get_source_memory(self._channel, self._chat_id)
            updated = f"{existing}\n{content}".strip() if existing else content
            self._store.write_source_note(self._channel, self._chat_id, updated)
            return f"Source memory updated for {target} ({self._channel}:{self._chat_id})"
        else:
            existing = self._store.get_person_memory(target)
            updated = f"{existing}\n{content}".strip() if existing else content
            self._store.write_person_memory(target, updated)
            return f"Person memory updated for {target}"

    def _list_persons(self, **_: Any) -> str:
        """List all known persons."""
        persons = self._store.list_persons()
        if not persons:
            return "No persons mapped yet. Use map_identity to add the first one."

        lines = []
        for p in persons:
            ids = ", ".join(f"{e['channel']}:{e['id']}" for e in p["ids"])
            lines.append(f"- {p['display_name']} ({p['name']}): {ids}")
        return "Known persons:\n" + "\n".join(lines)

    def _map_identity(self, person: str | None = None, display_name: str | None = None, **_: Any) -> str:
        """Map the current channel:id to a person."""
        if not person:
            return "Error: 'person' (person name key) is required for map_identity."
        if not self._channel or not self._chat_id:
            return "Error: No channel/chat_id context available."

        self._store.add_identity(person, self._channel, self._chat_id, display_name)
        label = display_name or person
        return f"Mapped {self._channel}:{self._chat_id} -> {label} ({person})"

    def _search_history(self, content: str | None = None, person: str | None = None, **_: Any) -> str:
        """Search history logs, with automatic fallback to raw session files."""
        if not content:
            return "Error: 'content' (search query) is required for search_history."

        if person:
            target = person
        else:
            target = self._store.resolve_person(self._channel, self._chat_id)

        search_paths = []
        memory_dir = self._store._workspace / "memory"

        global_history = memory_dir / "HISTORY.md"
        if global_history.exists():
            search_paths.append(str(global_history))

        if target:
            person_history = memory_dir / "persons" / target / "HISTORY.md"
            if person_history.exists():
                search_paths.append(str(person_history))

        if search_paths:
            try:
                result = subprocess.run(
                    ["grep", "-i", "-n", content, *search_paths],
                    capture_output=True, text=True, timeout=5,
                )
                output = result.stdout.strip()
                if output:
                    lines = output.split("\n")
                    if len(lines) > 50:
                        lines = lines[:50]
                        output = "\n".join(lines) + "\n... (truncated, 50+ matches)"
                    else:
                        output = "\n".join(lines)
                    return f"Search results for '{content}':\n{output}"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # Fallback: search raw session files
        session_results = self._search_sessions(content, target)
        if session_results:
            return f"Search results for '{content}' (from session history):\n{session_results}"

        return f"No matches found for '{content}' in history."

    _SESSIONS_MAX_RESULTS = 20
    _SESSIONS_MAX_CHARS = 500

    def _search_sessions(self, query: str, person: str | None) -> str:
        """Search raw session JSONL files by content field."""
        session_files = self._get_session_files_for_person(person) if person else []
        if not session_files and self._channel and self._chat_id:
            current = self._store._workspace / "sessions" / f"{self._channel}_{self._chat_id}.jsonl"
            if current.exists():
                session_files = [current]

        if not session_files:
            return ""

        query_lower = query.lower()
        matches: list[str] = []

        for path in session_files:
            try:
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if data.get("_type") == "metadata":
                            continue
                        msg_content = data.get("content", "")
                        if not isinstance(msg_content, str) or query_lower not in msg_content.lower():
                            continue
                        ts = data.get("timestamp", "?")
                        role = data.get("role", "?")
                        snippet = msg_content[:self._SESSIONS_MAX_CHARS]
                        if len(msg_content) > self._SESSIONS_MAX_CHARS:
                            snippet += "..."
                        matches.append(f"[{ts}] {role}: {snippet}")
                        if len(matches) >= self._SESSIONS_MAX_RESULTS:
                            break
            except OSError:
                continue
            if len(matches) >= self._SESSIONS_MAX_RESULTS:
                break

        if not matches:
            return ""

        result = "\n".join(matches)
        if len(matches) >= self._SESSIONS_MAX_RESULTS:
            result += f"\n... (showing first {self._SESSIONS_MAX_RESULTS} matches)"
        return result

    def _get_session_files_for_person(self, person_name: str) -> list[Path]:
        """Get all session files associated with a person via identity_map."""
        sessions_dir = self._store._workspace / "sessions"
        if not sessions_dir.exists():
            return []

        persons = self._store.resolver.list_persons()
        info = persons.get(person_name)
        if not info:
            return []

        paths: list[Path] = []
        for entry in info.get("ids", []):
            channel = entry.get("channel", "")
            ids = entry.get("id", [])
            if isinstance(ids, str):
                ids = [ids]
            for chat_id in ids:
                p = sessions_dir / f"{channel}_{chat_id}.jsonl"
                if p.exists():
                    paths.append(p)
        return paths
