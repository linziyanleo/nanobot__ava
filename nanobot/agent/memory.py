"""Memory system for persistent agent memory."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from nanobot.utils.helpers import ensure_dir

if TYPE_CHECKING:
    from nanobot.agent.categorized_memory import CategorizedMemoryStore
    from nanobot.providers.base import LLMProvider
    from nanobot.session.manager import Session


_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save the memory consolidation result to persistent storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": "A paragraph (2-5 sentences) summarizing key events/decisions/topics for "
                        "history search. Start with [YYYY-MM-DD HH:MM].",
                    },
                    "memory_update": {
                        "type": "string",
                        "description": "Full updated GLOBAL long-term memory as markdown. Only include shared, "
                        "stable facts that apply across users/sessions.",
                    },
                    "person_memory_update": {
                        "type": "string",
                        "description": "Optional full updated PERSON long-term memory for current user/session "
                        "as markdown. Only include stable user-specific facts.",
                    },
                    "self_memory_update": {
                        "type": "string",
                        "description": "Optional full updated Nanobot self memory as markdown. "
                        "Only include stable self-related facts.",
                    },
                },
                "required": ["history_entry", "memory_update"],
            },
        },
    }
]


class MemoryStore:
    """Two-layer memory: MEMORY.md (long-term facts) + HISTORY.md (grep-searchable log)."""

    _BULLET_RE = re.compile(r"^\s*[-*]\s+")
    _HISTORY_STYLE_TS_RE = re.compile(r"^\s*\[?\d{4}-\d{2}-\d{2}[^\]]*\]?")

    def __init__(self, workspace: Path):
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "HISTORY.md"
        self.self_memory_file = self.memory_dir / "self" / "MEMORY.md"

    def read_long_term(self) -> str:
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def write_long_term(self, content: str) -> None:
        self.memory_file.write_text(content, encoding="utf-8")

    def append_history(self, entry: str) -> None:
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(entry.rstrip() + "\n\n")

    def read_self_memory(self) -> str:
        if self.self_memory_file.exists():
            return self.self_memory_file.read_text(encoding="utf-8")
        return ""

    def write_self_memory(self, content: str) -> None:
        ensure_dir(self.self_memory_file.parent)
        self.self_memory_file.write_text(content, encoding="utf-8")

    def get_memory_context(self) -> str:
        long_term = self.read_long_term()
        return f"## Long-term Memory\n{long_term}" if long_term else ""

    def get_self_memory_context(self) -> str:
        self_memory = self.read_self_memory()
        return f"## Nanobot Self Memory\n{self_memory}" if self_memory else ""

    @classmethod
    def _normalize_memory_line(cls, text: str) -> str:
        return " ".join(text.strip().lower().split())

    @classmethod
    def _apply_stability_rules(cls, content: str, scope: str) -> str:
        """Apply deterministic rules to complement LLM memory extraction."""
        del scope  # Reserved for scope-specific rules in future iterations.
        if not content.strip():
            return ""

        output: list[str] = []
        seen_bullets: set[str] = set()

        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                output.append(line)
                continue

            # Guardrail: history-style timestamp lines should stay in HISTORY.md, not MEMORY.md.
            if cls._HISTORY_STYLE_TS_RE.match(stripped):
                continue

            if cls._BULLET_RE.match(stripped):
                bullet_text = cls._BULLET_RE.sub("", stripped)
                norm = cls._normalize_memory_line(bullet_text)
                if norm in seen_bullets:
                    continue
                seen_bullets.add(norm)

            output.append(line)

        return "\n".join(output).strip()

    @staticmethod
    def _parse_session_key(key: str) -> tuple[str | None, str | None]:
        """Extract (channel, chat_id) from a session key like 'telegram:xxxxxxxxxx'."""
        if ":" in key:
            channel, chat_id = key.split(":", 1)
            return channel, chat_id
        return None, None

    async def consolidate(
        self,
        session: Session,
        provider: LLMProvider,
        model: str,
        *,
        archive_all: bool = False,
        memory_window: int = 50,
        categorized_store: CategorizedMemoryStore | None = None,
    ) -> bool:
        """Consolidate old messages into MEMORY.md + HISTORY.md via LLM tool call.

        Returns True on success (including no-op), False on failure.
        """
        if archive_all:
            old_messages = session.messages
            keep_count = 0
            logger.info("Memory consolidation (archive_all): {} messages", len(session.messages))
        else:
            keep_count = memory_window // 2
            if len(session.messages) <= keep_count:
                return True
            if len(session.messages) - session.last_consolidated <= 0:
                return True
            old_messages = session.messages[session.last_consolidated:-keep_count]
            if not old_messages:
                return True
            logger.info("Memory consolidation: {} to consolidate, {} keep", len(old_messages), keep_count)

        lines = []
        for m in old_messages:
            if not m.get("content"):
                continue
            tools = f" [tools: {', '.join(m['tools_used'])}]" if m.get("tools_used") else ""
            lines.append(f"[{m.get('timestamp', '?')[:16]}] {m['role'].upper()}{tools}: {m['content']}")

        channel, chat_id = self._parse_session_key(session.key)
        person_name = None
        if categorized_store is not None and channel and chat_id:
            person_name = categorized_store.resolve_person(channel, chat_id)

        current_memory = self.read_long_term()
        current_self_memory = self.read_self_memory()
        prompt = f"""Process this conversation and call the save_memory tool with your consolidation.

## Current Long-term Memory
{current_memory or "(empty)"}

## Current Nanobot Self Memory
{current_self_memory or "(empty)"}

## Current Session Identity
channel={channel or "unknown"}
chat_id={chat_id or "unknown"}
person={person_name or "unmapped"}

## Conversation to Process
{chr(10).join(lines)}

## Output Rules
1) history_entry: history timeline summary only (2-5 sentences).
2) memory_update: GLOBAL memory only. Keep only shared, stable facts.
3) person_memory_update: PERSON memory only for current session user (if identifiable).
4) self_memory_update: Nanobot self memory only.
5) Stability criterion (LLM stage): keep a fact only if it is recurring, long-lived, or affects future decisions.
   Exclude one-off timeline details and operational noise."""

        try:
            chat_kwargs = dict(
                messages=[
                    {"role": "system", "content": "You are a memory consolidation agent. You MUST call the save_memory tool with your consolidation result. Do NOT reply with plain text."},
                    {"role": "user", "content": prompt},
                ],
                tools=_SAVE_MEMORY_TOOL,
                model=model,
                tool_choice="required",
            )
            response = await provider.chat(**chat_kwargs)

            if not response.has_tool_calls:
                logger.warning("Memory consolidation: LLM did not call save_memory (attempt 1), retrying")
                chat_kwargs["tool_choice"] = {"type": "function", "function": {"name": "save_memory"}}
                response = await provider.chat(**chat_kwargs)

            if not response.has_tool_calls:
                logger.warning("Memory consolidation: LLM did not call save_memory after retry, skipping")
                return False

            args = response.tool_calls[0].arguments
            # Some providers return arguments as a JSON string instead of dict
            if isinstance(args, str):
                args = json.loads(args)
            # Some providers return arguments as a list (handle edge case)
            if isinstance(args, list):
                if args and isinstance(args[0], dict):
                    args = args[0]
                else:
                    logger.warning("Memory consolidation: unexpected arguments as empty or non-dict list")
                    return False
            if not isinstance(args, dict):
                logger.warning("Memory consolidation: unexpected arguments type {}", type(args).__name__)
                return False

            entry = args.get("history_entry", "")
            if not isinstance(entry, str):
                entry = json.dumps(entry, ensure_ascii=False)

            update = args.get("memory_update", current_memory)
            if not isinstance(update, str):
                update = json.dumps(update, ensure_ascii=False)
            update = self._apply_stability_rules(update, scope="global") or current_memory

            person_update = args.get("person_memory_update", "")
            if not isinstance(person_update, str):
                person_update = json.dumps(person_update, ensure_ascii=False)
            person_update = self._apply_stability_rules(person_update, scope="person")

            self_update = args.get("self_memory_update", current_self_memory)
            if not isinstance(self_update, str):
                self_update = json.dumps(self_update, ensure_ascii=False)
            self_update = self._apply_stability_rules(self_update, scope="self") or current_self_memory

            if entry:
                self.append_history(entry)
            if update != current_memory:
                self.write_long_term(update)
            if self_update != current_self_memory:
                self.write_self_memory(self_update)

            # Sync to person-level memory if categorized store is available
            if categorized_store is not None:
                if channel and chat_id:
                    categorized_store.on_consolidate(
                        channel, chat_id,
                        history_entry=entry or "",
                        person_memory_facts=person_update or "",
                    )

            session.last_consolidated = 0 if archive_all else len(session.messages) - keep_count
            logger.info("Memory consolidation done: {} messages, last_consolidated={}", len(session.messages), session.last_consolidated)
            return True
        except Exception:
            logger.exception("Memory consolidation failed")
            return False
