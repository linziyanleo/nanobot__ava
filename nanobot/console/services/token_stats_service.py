"""Token usage statistics collector — records per-call LLM usage to a local JSON file."""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class TokenUsageRecord:
    """A single LLM call's token usage with context."""

    timestamp: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    session_key: str = ""
    user_message: str = ""
    output_content: str = ""
    system_prompt_preview: str = ""
    full_request_payload: str = ""


class TokenStatsCollector:
    """Collects per-call LLM token usage and persists to a JSON file.

    Thread-safe via a lock. Records are kept in memory and flushed
    to ``data_dir / token_stats.json`` on every ``flush()`` call.
    """

    def __init__(self, data_dir: Path, max_records: int = 10000):
        self._data_dir = data_dir
        self._max_records = max_records
        self._records: list[TokenUsageRecord] = []
        self._lock = threading.Lock()
        self._dirty = False
        self._file = data_dir / "token_stats.json"
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        model: str,
        provider: str,
        usage: dict[str, int],
        session_key: str = "",
        user_message: str = "",
        output_content: str = "",
        system_prompt: str = "",
        full_request_payload: str = "",
    ) -> None:
        """Append a single LLM call record."""
        rec = TokenUsageRecord(
            timestamp=datetime.now().isoformat(),
            model=model,
            provider=provider,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            session_key=session_key,
            user_message=user_message,
            output_content=output_content,
            system_prompt_preview=system_prompt,
            full_request_payload=full_request_payload,
        )
        with self._lock:
            self._records.append(rec)
            self._dirty = True
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
        self.flush()

    def get_records(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """Return records in reverse-chronological order (newest first)."""
        with self._lock:
            reversed_records = list(reversed(self._records))
            sliced = reversed_records[offset: offset + limit]
            return [asdict(r) for r in sliced]

    def get_total_count(self) -> int:
        with self._lock:
            return len(self._records)

    def get_summary(self) -> dict[str, Any]:
        """Full summary: totals + by_model + by_provider."""
        return {
            "totals": self.get_totals(),
            "by_model": self.get_by_model(),
            "by_provider": self.get_by_provider(),
        }

    def get_totals(self) -> dict[str, int]:
        with self._lock:
            prompt = sum(r.prompt_tokens for r in self._records)
            completion = sum(r.completion_tokens for r in self._records)
            total = sum(r.total_tokens for r in self._records)
            return {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": total,
                "total_calls": len(self._records),
            }

    def get_by_model(self) -> list[dict[str, Any]]:
        with self._lock:
            agg: dict[str, dict[str, int]] = defaultdict(
                lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
            )
            for r in self._records:
                d = agg[r.model]
                d["prompt_tokens"] += r.prompt_tokens
                d["completion_tokens"] += r.completion_tokens
                d["total_tokens"] += r.total_tokens
                d["calls"] += 1
            return [{"model": k, **v} for k, v in sorted(agg.items(), key=lambda x: -x[1]["total_tokens"])]

    def get_by_provider(self) -> list[dict[str, Any]]:
        with self._lock:
            agg: dict[str, dict[str, int]] = defaultdict(
                lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
            )
            for r in self._records:
                d = agg[r.provider]
                d["prompt_tokens"] += r.prompt_tokens
                d["completion_tokens"] += r.completion_tokens
                d["total_tokens"] += r.total_tokens
                d["calls"] += 1
            return [{"provider": k, **v} for k, v in sorted(agg.items(), key=lambda x: -x[1]["total_tokens"])]

    def get_timeline(self, interval: str = "hour") -> list[dict[str, Any]]:
        """Aggregate records by time bucket. interval: 'hour' or 'day'."""
        with self._lock:
            buckets: dict[str, dict[str, int]] = defaultdict(
                lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}
            )
            for r in self._records:
                try:
                    dt = datetime.fromisoformat(r.timestamp)
                except ValueError:
                    continue
                if interval == "day":
                    key = dt.strftime("%Y-%m-%d")
                else:
                    key = dt.strftime("%Y-%m-%d %H:00")
                d = buckets[key]
                d["prompt_tokens"] += r.prompt_tokens
                d["completion_tokens"] += r.completion_tokens
                d["total_tokens"] += r.total_tokens
                d["calls"] += 1
            return [{"time": k, **v} for k, v in sorted(buckets.items())]

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
            self._dirty = True
        self.flush()

    def flush(self) -> None:
        """Persist current records to disk."""
        with self._lock:
            if not self._dirty:
                return
            data = [asdict(r) for r in self._records]
            self._dirty = False

        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=None)
        except Exception as e:
            logger.warning("Failed to flush token stats: {}", e)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._file.exists():
            return
        try:
            with open(self._file, encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, list):
                return
            for item in raw:
                if not isinstance(item, dict):
                    continue
                self._records.append(TokenUsageRecord(
                    timestamp=item.get("timestamp", ""),
                    model=item.get("model", ""),
                    provider=item.get("provider", ""),
                    prompt_tokens=item.get("prompt_tokens", 0),
                    completion_tokens=item.get("completion_tokens", 0),
                    total_tokens=item.get("total_tokens", 0),
                    session_key=item.get("session_key", ""),
                    user_message=item.get("user_message", ""),
                    output_content=item.get("output_content", ""),
                    system_prompt_preview=item.get("system_prompt_preview", ""),
                    full_request_payload=item.get("full_request_payload", ""),
                ))
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
            logger.info("Loaded {} token stats records from disk", len(self._records))
        except Exception as e:
            logger.warning("Failed to load token stats: {}", e)
