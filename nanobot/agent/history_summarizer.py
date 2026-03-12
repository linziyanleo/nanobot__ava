"""Turn-level history summarization for reducing LLM context token usage.

Compresses older conversation turns from the full message format
(user → assistant+tool_calls → tool_results → assistant_final) into
compact two-message pairs (user, assistant) while preserving recent
messages in their original format for tool-call compatibility.
"""

from __future__ import annotations

import re
from typing import Any


class HistorySummarizer:
    """Summarize old conversation turns to save tokens."""

    _SCHEDULED_RE = re.compile(
        r"\[Scheduled Task\].*?Scheduled instruction:\s*(.+)",
        re.DOTALL,
    )
    _STICKER_RE = re.compile(r"Sticker\s+(\d+)\s*\(([^)]+)\)")

    def __init__(
        self,
        *,
        enabled: bool = True,
        protect_recent: int = 20,
        tool_result_max_chars: int = 200,
    ) -> None:
        self.enabled = enabled
        self.protect_recent = protect_recent
        self.tool_result_max_chars = tool_result_max_chars

    def summarize(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Summarize older turns in history, keeping recent messages intact."""
        if not self.enabled or not history:
            return history

        if len(history) <= self.protect_recent:
            return history

        to_summarize = history[:-self.protect_recent]
        protected = history[-self.protect_recent:]

        turns = self._split_turns(to_summarize)
        summarized: list[dict[str, Any]] = []
        for turn in turns:
            summarized.extend(self._summarize_turn(turn))

        return summarized + protected

    @staticmethod
    def _split_turns(messages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Split messages into turns, each starting with a user message."""
        turns: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []

        for msg in messages:
            if msg.get("role") == "user":
                if current:
                    turns.append(current)
                current = [msg]
            else:
                if current:
                    current.append(msg)
                # orphan non-user messages at the start are dropped

        if current:
            turns.append(current)
        return turns

    def _summarize_turn(self, turn: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compress a turn into [user_msg, assistant_msg]."""
        if not turn:
            return []

        user_msg = turn[0]
        user_content = user_msg.get("content", "")

        if isinstance(user_content, str):
            user_content = self._simplify_scheduled_task(user_content)

        tool_lines: list[str] = []
        final_content = ""

        for msg in turn[1:]:
            role = msg.get("role")

            if role == "tool":
                name = msg.get("name", "unknown")
                content = msg.get("content", "")
                if isinstance(content, str):
                    summary = self._summarize_tool_result(name, content)
                    tool_lines.append(f"Tool: {name} → {summary}")

            elif role == "assistant":
                if not msg.get("tool_calls"):
                    content = msg.get("content")
                    if content and isinstance(content, str) and content.strip():
                        final_content = content.strip()

        parts: list[str] = []
        if tool_lines:
            parts.append("\n".join(tool_lines))
        if final_content:
            parts.append(final_content)

        assistant_content = "\n\n".join(parts) if parts else ""

        result = [{"role": "user", "content": user_content}]
        if assistant_content:
            result.append({"role": "assistant", "content": assistant_content})

        return result

    def _summarize_tool_result(self, name: str, content: str) -> str:
        """Produce a compact summary for a tool result."""
        if name == "send_sticker":
            m = self._STICKER_RE.search(content)
            if m:
                return f"Sticker {m.group(1)} {m.group(2)}"
            return "[sent]"

        if name in ("message", "send_message"):
            return "[sent]"

        if len(content) <= self.tool_result_max_chars:
            return content
        return content[:self.tool_result_max_chars] + "..."

    @classmethod
    def _simplify_scheduled_task(cls, content: str) -> str:
        """Simplify scheduled task trigger messages."""
        m = cls._SCHEDULED_RE.search(content)
        if m:
            instruction = m.group(1).strip()
            return f"[Scheduled: {instruction}]"
        return content
