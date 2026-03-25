"""Categorized memory system with per-person identity resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.utils.helpers import ensure_dir

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


def _yaml_load(path: Path) -> dict:
    """Load YAML file, fallback to basic parsing if PyYAML unavailable."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if yaml is not None:
        return yaml.safe_load(text) or {}
    # Minimal fallback: empty dict when no yaml lib
    return {}


def _yaml_dump(data: dict, path: Path) -> None:
    """Write YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML is required for identity map operations. Install with: pip install pyyaml")
    ensure_dir(path.parent)
    path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")


class IdentityResolver:
    """Resolves channel:chat_id pairs to a person name using identity_map.yaml."""

    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace
        self._map_file = workspace / "memory" / "identity_map.yaml"
        self._cache: dict | None = None

    def _load(self) -> dict:
        if self._cache is None:
            self._cache = _yaml_load(self._map_file)
        return self._cache

    def _save(self, data: dict) -> None:
        _yaml_dump(data, self._map_file)
        self._cache = data

    def _invalidate(self) -> None:
        self._cache = None

    @staticmethod
    def _match_id(entry_id: str | list, chat_id: str) -> bool:
        """Check if chat_id matches entry_id (supports both string and list)."""
        if isinstance(entry_id, list):
            return str(chat_id) in [str(i) for i in entry_id]
        return str(entry_id) == str(chat_id)

    def resolve(self, channel: str, chat_id: str) -> str | None:
        """Resolve channel:chat_id to person name. Returns None if not mapped."""
        data = self._load()
        persons = data.get("persons") or {}
        if isinstance(persons, dict):
            for person_name, info in persons.items():
                if not isinstance(info, dict):
                    continue
                for entry in info.get("ids", []):
                    if entry.get("channel") == channel and self._match_id(entry.get("id", []), chat_id):
                        return person_name
        return None

    def add_mapping(
        self,
        person_name: str,
        channel: str,
        chat_id: str,
        display_name: str | None = None,
    ) -> None:
        """Add or update an identity mapping. Appends to existing channel's id list."""
        data = self._load()
        persons = data.setdefault("persons", {})
        if not isinstance(persons, dict):
            persons = {}
            data["persons"] = persons

        person = persons.setdefault(person_name, {})
        if display_name:
            person["display_name"] = display_name

        ids = person.setdefault("ids", [])
        for entry in ids:
            if entry.get("channel") == channel:
                id_val = entry.get("id", [])
                if isinstance(id_val, list):
                    if str(chat_id) in [str(i) for i in id_val]:
                        return  # already exists
                    id_val.append(str(chat_id))
                else:
                    if str(id_val) == str(chat_id):
                        return  # already exists
                    entry["id"] = [str(id_val), str(chat_id)]
                self._save(data)
                logger.info("Identity mapped: {}:{} -> {} (appended)", channel, chat_id, person_name)
                return

        ids.append({"channel": channel, "id": [str(chat_id)]})
        self._save(data)
        logger.info("Identity mapped: {}:{} -> {}", channel, chat_id, person_name)

    def list_persons(self) -> dict[str, Any]:
        """Return all persons with their display names and IDs."""
        data = self._load()
        persons = data.get("persons") or {}
        if not isinstance(persons, dict):
            return {}
        return {
            name: {
                "display_name": info.get("display_name", name),
                "ids": info.get("ids", []),
            }
            for name, info in persons.items()
            if isinstance(info, dict)
        }


class CategorizedMemoryStore:
    """Per-person memory store with identity resolution and source-level tracking."""

    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace
        self._memory_dir = ensure_dir(workspace / "memory")
        self._persons_dir = ensure_dir(self._memory_dir / "persons")
        self._resolver = IdentityResolver(workspace)

    @property
    def resolver(self) -> IdentityResolver:
        return self._resolver

    def resolve_person(self, channel: str, chat_id: str) -> str | None:
        return self._resolver.resolve(channel, chat_id)

    def _person_dir(self, person_name: str) -> Path:
        return ensure_dir(self._persons_dir / person_name)

    def _person_memory_file(self, person_name: str) -> Path:
        return self._person_dir(person_name) / "MEMORY.md"

    def _person_history_file(self, person_name: str) -> Path:
        return self._person_dir(person_name) / "HISTORY.md"

    def _source_dir(self, person_name: str) -> Path:
        return ensure_dir(self._person_dir(person_name) / "sources")

    def _source_file(self, person_name: str, channel: str, chat_id: str) -> Path:
        safe_id = str(chat_id).replace("/", "_").replace("\\", "_")
        return self._source_dir(person_name) / f"{channel}_{safe_id}.md"

    def _resolve_or_anonymous(self, channel: str, chat_id: str) -> str:
        """Resolve to person name, or 'anonymous' if not mapped."""
        return self._resolver.resolve(channel, chat_id) or "anonymous"

    # ── Person-level memory ──

    def get_person_memory(self, person_name: str) -> str:
        f = self._person_memory_file(person_name)
        return f.read_text(encoding="utf-8") if f.exists() else ""

    def write_person_memory(self, person_name: str, content: str) -> None:
        self._person_memory_file(person_name).write_text(content, encoding="utf-8")
        logger.debug("Person memory written: {}", person_name)

    def append_person_history(self, person_name: str, entry: str) -> None:
        f = self._person_history_file(person_name)
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(entry.rstrip() + "\n\n")

    # ── Source-level memory ──

    def get_source_memory(self, channel: str, chat_id: str) -> str:
        person = self._resolve_or_anonymous(channel, chat_id)
        f = self._source_file(person, channel, chat_id)
        return f.read_text(encoding="utf-8") if f.exists() else ""

    def write_source_note(self, channel: str, chat_id: str, content: str) -> None:
        person = self._resolve_or_anonymous(channel, chat_id)
        self._source_file(person, channel, chat_id).write_text(content, encoding="utf-8")

    # ── Combined context (for system prompt injection) ──

    def get_combined_context(self, channel: str | None, chat_id: str | None) -> str:
        """Build combined memory context for the current person.

        Returns person-level memory if identity is resolved, empty string otherwise.
        Global memory is handled separately by MemoryStore.
        """
        if not channel or not chat_id:
            return ""
        person = self._resolver.resolve(channel, chat_id)
        if not person:
            return ""
        mem = self.get_person_memory(person)
        if not mem:
            return ""
        display = self._resolver.list_persons().get(person, {}).get("display_name", person)
        return f"## Personal Memory ({display})\n{mem}"

    # ── Identity management ──

    def add_identity(
        self,
        person_name: str,
        channel: str,
        chat_id: str,
        display_name: str | None = None,
    ) -> None:
        self._resolver.add_mapping(person_name, channel, chat_id, display_name)

    def list_persons(self) -> list[dict]:
        persons = self._resolver.list_persons()
        return [
            {"name": name, "display_name": info["display_name"], "ids": info["ids"]}
            for name, info in persons.items()
        ]

    # ── Consolidation hook ──

    def on_consolidate(
        self,
        channel: str,
        chat_id: str,
        history_entry: str,
        person_memory_facts: str,
    ) -> None:
        """Called after consolidation to sync person-level memory."""
        person = self._resolver.resolve(channel, chat_id)
        if not person:
            return
        if history_entry:
            self.append_person_history(person, history_entry)
        if person_memory_facts:
            existing = self.get_person_memory(person)
            if person_memory_facts != existing:
                self.write_person_memory(person, person_memory_facts)
        logger.info("Person memory synced for {} ({}:{})", person, channel, chat_id)
