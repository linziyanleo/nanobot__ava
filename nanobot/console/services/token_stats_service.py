"""Token usage statistics collector — records per-call LLM usage to SQLite (or legacy JSON file)."""

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
    turn_seq: int | None = None
    iteration: int = 0
    user_message: str = ""
    output_content: str = ""
    system_prompt_preview: str = ""
    conversation_history: str = ""
    full_request_payload: str = ""
    finish_reason: str = ""


class TokenStatsCollector:
    """Collects per-call LLM token usage.

    Primary backend: SQLite (via Database instance).
    Fallback: legacy JSON file for backward compatibility.
    """

    def __init__(
        self,
        data_dir: Path,
        max_records: int = 10000,
        db: Any | None = None,
    ):
        self._data_dir = data_dir
        self._max_records = max_records
        self._db = db

        # Legacy JSON fallback fields
        self._records: list[TokenUsageRecord] = []
        self._lock = threading.Lock()
        self._dirty = False
        self._file = data_dir / "token_stats.json"
        self._last_mtime: float = 0.0
        if not self._use_db:
            self._load()

    @property
    def _use_db(self) -> bool:
        return self._db is not None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        model: str,
        provider: str,
        usage: dict[str, int],
        session_key: str = "",
        turn_seq: int | None = None,
        iteration: int = 0,
        user_message: str = "",
        output_content: str = "",
        system_prompt: str = "",
        conversation_history: str = "",
        full_request_payload: str = "",
        finish_reason: str = "",
    ) -> None:
        """Append a single LLM call record."""
        ts = datetime.now().isoformat()
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        if self._use_db:
            self._db.execute(
                """INSERT INTO token_usage
                   (timestamp, model, provider, prompt_tokens, completion_tokens, total_tokens,
                    session_key, turn_seq, iteration, user_message, output_content,
                    system_prompt_preview, conversation_history, full_request_payload, finish_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ts, model, provider, prompt_tokens, completion_tokens, total_tokens,
                    session_key, turn_seq, iteration, user_message, output_content,
                    system_prompt, conversation_history, full_request_payload, finish_reason,
                ),
            )
            self._db.commit()
            return

        rec = TokenUsageRecord(
            timestamp=ts,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            session_key=session_key,
            turn_seq=turn_seq,
            iteration=iteration,
            user_message=user_message,
            output_content=output_content,
            system_prompt_preview=system_prompt,
            conversation_history=conversation_history,
            full_request_payload=full_request_payload,
            finish_reason=finish_reason,
        )
        with self._lock:
            self._records.append(rec)
            self._dirty = True
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
        self.flush()

    def get_records(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        if self._use_db:
            rows = self._db.fetchall(
                "SELECT * FROM token_usage ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            return [dict(r) for r in rows]

        self._reload_if_changed()
        with self._lock:
            reversed_records = list(reversed(self._records))
            sliced = reversed_records[offset: offset + limit]
            return [asdict(r) for r in sliced]

    def get_total_count(self) -> int:
        if self._use_db:
            row = self._db.fetchone("SELECT COUNT(*) as cnt FROM token_usage")
            return row["cnt"] if row else 0

        self._reload_if_changed()
        with self._lock:
            return len(self._records)

    def get_summary(self) -> dict[str, Any]:
        return {
            "totals": self.get_totals(),
            "by_model": self.get_by_model(),
            "by_provider": self.get_by_provider(),
        }

    def get_totals(self) -> dict[str, int]:
        if self._use_db:
            row = self._db.fetchone(
                """SELECT COALESCE(SUM(prompt_tokens),0) as prompt_tokens,
                          COALESCE(SUM(completion_tokens),0) as completion_tokens,
                          COALESCE(SUM(total_tokens),0) as total_tokens,
                          COUNT(*) as total_calls
                   FROM token_usage"""
            )
            return dict(row) if row else {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "total_calls": 0}

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
        if self._use_db:
            rows = self._db.fetchall(
                """SELECT model,
                          SUM(prompt_tokens) as prompt_tokens,
                          SUM(completion_tokens) as completion_tokens,
                          SUM(total_tokens) as total_tokens,
                          COUNT(*) as calls
                   FROM token_usage GROUP BY model
                   ORDER BY total_tokens DESC"""
            )
            return [dict(r) for r in rows]

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
        if self._use_db:
            rows = self._db.fetchall(
                """SELECT provider,
                          SUM(prompt_tokens) as prompt_tokens,
                          SUM(completion_tokens) as completion_tokens,
                          SUM(total_tokens) as total_tokens,
                          COUNT(*) as calls
                   FROM token_usage GROUP BY provider
                   ORDER BY total_tokens DESC"""
            )
            return [dict(r) for r in rows]

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
        if self._use_db:
            fmt = "%Y-%m-%d %H:00" if interval != "day" else "%Y-%m-%d"
            rows = self._db.fetchall(
                f"""SELECT strftime('{fmt}', timestamp) as time,
                           SUM(prompt_tokens) as prompt_tokens,
                           SUM(completion_tokens) as completion_tokens,
                           SUM(total_tokens) as total_tokens,
                           COUNT(*) as calls
                    FROM token_usage
                    GROUP BY 1 ORDER BY 1"""
            )
            return [dict(r) for r in rows]

        self._reload_if_changed()
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

    def get_by_session(self, session_key: str) -> list[dict[str, Any]]:
        """Per-turn token aggregation for a given session."""
        if self._use_db:
            rows = self._db.fetchall(
                """SELECT turn_seq,
                          SUM(prompt_tokens) as prompt_tokens,
                          SUM(completion_tokens) as completion_tokens,
                          SUM(total_tokens) as total_tokens,
                          COUNT(*) as llm_calls,
                          GROUP_CONCAT(DISTINCT model) as models
                   FROM token_usage
                   WHERE session_key = ?
                   GROUP BY turn_seq
                   ORDER BY turn_seq""",
                (session_key,),
            )
            return [dict(r) for r in rows]

        self._reload_if_changed()
        with self._lock:
            buckets: dict[int | None, dict[str, Any]] = defaultdict(
                lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "llm_calls": 0, "models": set()}
            )
            for r in self._records:
                if r.session_key != session_key:
                    continue
                d = buckets[r.turn_seq]
                d["prompt_tokens"] += r.prompt_tokens
                d["completion_tokens"] += r.completion_tokens
                d["total_tokens"] += r.total_tokens
                d["llm_calls"] += 1
                d["models"].add(r.model)
            return [
                {"turn_seq": k, **{kk: (", ".join(sorted(vv)) if kk == "models" else vv) for kk, vv in v.items()}}
                for k, v in sorted(buckets.items(), key=lambda x: (x[0] is None, x[0]))
            ]

    def reset(self) -> None:
        if self._use_db:
            self._db.execute("DELETE FROM token_usage")
            self._db.commit()
            return

        with self._lock:
            self._records.clear()
            self._dirty = True
        self.flush()

    def flush(self) -> None:
        """Persist current records to disk (legacy JSON mode only)."""
        if self._use_db:
            return
        with self._lock:
            if not self._dirty:
                return
            data = [asdict(r) for r in self._records]
            self._dirty = False

        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=None)
            self._last_mtime = self._file.stat().st_mtime
        except Exception as e:
            logger.warning("Failed to flush token stats: {}", e)

    # ------------------------------------------------------------------
    # Internal (legacy JSON)
    # ------------------------------------------------------------------

    def _reload_if_changed(self) -> None:
        if self._use_db:
            return
        try:
            if not self._file.exists():
                return
            mtime = self._file.stat().st_mtime
            if mtime <= self._last_mtime:
                return
        except OSError:
            return
        with self._lock:
            if not self._dirty:
                self._records.clear()
                self._load_inner()

    def _load(self) -> None:
        self._load_inner()

    def _load_inner(self) -> None:
        if not self._file.exists():
            return
        try:
            self._last_mtime = self._file.stat().st_mtime
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
                    turn_seq=item.get("turn_seq"),
                    iteration=item.get("iteration", 0),
                    user_message=item.get("user_message", ""),
                    output_content=item.get("output_content", ""),
                    system_prompt_preview=item.get("system_prompt_preview", ""),
                    conversation_history=item.get("conversation_history", ""),
                    full_request_payload=item.get("full_request_payload", ""),
                    finish_reason=item.get("finish_reason", ""),
                ))
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
            logger.info("Loaded {} token stats records from disk", len(self._records))
        except Exception as e:
            logger.warning("Failed to load token stats: {}", e)
