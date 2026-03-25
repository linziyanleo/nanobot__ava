"""Monkey patch to inject cafeext capabilities into AgentLoop.

Injected attributes (after __init__):
  - self.db             — shared Database instance (from storage_patch)
  - self.token_stats    — TokenStatsCollector instance
  - self.media_service  — MediaService instance (for image_gen tool)

Also patches _process_message to record token usage after each turn.

Execution order note:
  storage_patch runs after this (s > l alphabetically).
  We handle _shared_db being None by constructing a fallback Database.
  storage_patch later calls set_shared_db() which will be used by
  newly created AgentLoop instances.
"""

from __future__ import annotations

from loguru import logger

from cafeext.launcher import register_patch


# Module-level shared db reference (set by storage_patch after us)
_shared_db = None


def set_shared_db(db) -> None:
    """Called by storage_patch to share the Database instance."""
    global _shared_db
    _shared_db = db


def _get_or_create_db(workspace_path) -> object | None:
    """Return _shared_db if available, otherwise create a fresh Database."""
    if _shared_db is not None:
        return _shared_db
    try:
        from cafeext.storage import Database
        from pathlib import Path
        db_path = Path(workspace_path) / "data" / "nanobot.db"
        return Database(db_path)
    except Exception as exc:
        logger.warning("Failed to create fallback Database: {}", exc)
        return None


def apply_loop_patch() -> str:
    from nanobot.agent.loop import AgentLoop

    # ------------------------------------------------------------------
    # 1. Patch __init__ to inject extra attributes
    # ------------------------------------------------------------------
    original_init = AgentLoop.__init__

    def patched_init(self: AgentLoop, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)

        db = _get_or_create_db(self.workspace)
        self.db = db

        # TokenStatsCollector
        try:
            from cafeext.console.services.token_stats_service import TokenStatsCollector
            data_dir = self.workspace / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.token_stats = TokenStatsCollector(data_dir=data_dir, db=db)
        except Exception as exc:
            logger.warning("Failed to init TokenStatsCollector: {}", exc)
            self.token_stats = None

        # MediaService
        try:
            from cafeext.console.services.media_service import MediaService
            self.media_service = MediaService(workspace=self.workspace, db=db)
        except Exception as exc:
            logger.warning("Failed to init MediaService: {}", exc)
            self.media_service = None

    AgentLoop.__init__ = patched_init

    # ------------------------------------------------------------------
    # 2. Patch _process_message to record token usage per turn
    # ------------------------------------------------------------------
    original_process_message = AgentLoop._process_message

    async def patched_process_message(
        self: AgentLoop,
        msg,
        session_key=None,
        on_progress=None,
        on_stream=None,
        on_stream_end=None,
    ):
        # Snapshot usage before to detect delta
        usage_before = dict(getattr(self, "_last_usage", {}))

        result = await original_process_message(
            self, msg,
            session_key=session_key,
            on_progress=on_progress,
            on_stream=on_stream,
            on_stream_end=on_stream_end,
        )

        token_stats = getattr(self, "token_stats", None)
        if token_stats is not None:
            last_usage = getattr(self, "_last_usage", {})
            # Only record if usage changed (new LLM call happened)
            if last_usage and last_usage != usage_before:
                try:
                    # Derive session key for recording
                    sk = session_key or getattr(msg, "session_key", "")
                    provider_name = type(self.provider).__name__.lower().replace("provider", "")
                    token_stats.record(
                        model=self.model,
                        provider=provider_name,
                        usage=last_usage,
                        session_key=sk,
                        model_role="chat",
                    )
                except Exception as exc:
                    logger.warning("Failed to record token stats in loop_patch: {}", exc)

        return result

    AgentLoop._process_message = patched_process_message

    return "AgentLoop patched: injected db/token_stats/media_service; _process_message records token usage"


register_patch("agent_loop", apply_loop_patch)
