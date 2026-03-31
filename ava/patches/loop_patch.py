"""Monkey patch to inject ava capabilities into AgentLoop.

Injected attributes (after __init__):
  - self.db                  — shared Database instance (from storage_patch)
  - self.token_stats         — TokenStatsCollector instance
  - self.media_service       — MediaService instance (for image_gen tool)
  - self.categorized_memory  — CategorizedMemoryStore instance
  - self.history_summarizer  — HistorySummarizer instance
  - self.history_compressor  — HistoryCompressor instance
  - self.context._agent_loop — back-reference for context_patch to access loop

Also patches _process_message to record token usage after each turn.

Execution order note:
  storage_patch runs after this (s > l alphabetically).
  We handle _shared_db being None by constructing a fallback Database.
  storage_patch later calls set_shared_db() which will be used by
  newly created AgentLoop instances.
"""

from __future__ import annotations

from loguru import logger

from ava.launcher import register_patch


# Module-level shared db reference (set by storage_patch after us)
_shared_db = None
# Module-level reference to the most recently created AgentLoop (for console_patch)
_agent_loop_ref = None


def set_shared_db(db) -> None:
    """Called by storage_patch to share the Database instance."""
    global _shared_db
    _shared_db = db


def get_agent_loop():
    """Return the most recently created AgentLoop instance (or None)."""
    return _agent_loop_ref


def _get_or_create_db(workspace_path) -> object | None:
    """Return _shared_db if available, otherwise create a fresh Database."""
    if _shared_db is not None:
        return _shared_db
    try:
        from ava.storage import Database
        from nanobot.config.paths import get_data_dir
        db_path = get_data_dir() / "nanobot.db"
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

        # Save ref for console_patch to access the AgentLoop instance
        global _agent_loop_ref
        _agent_loop_ref = self

        db = _get_or_create_db(self.workspace)
        self.db = db

        # TokenStatsCollector
        try:
            from ava.console.services.token_stats_service import TokenStatsCollector
            from nanobot.config.paths import get_data_dir as _get_data_dir
            stats_data_dir = _get_data_dir()
            stats_data_dir.mkdir(parents=True, exist_ok=True)
            self.token_stats = TokenStatsCollector(data_dir=stats_data_dir, db=db)
        except Exception as exc:
            logger.warning("Failed to init TokenStatsCollector: {}", exc)
            self.token_stats = None

        # MediaService
        try:
            from ava.console.services.media_service import MediaService
            from nanobot.config.paths import get_media_dir as _get_media_dir
            media_dir = _get_media_dir() / "generated"
            self.media_service = MediaService(media_dir=media_dir, db=db)
        except Exception as exc:
            logger.warning("Failed to init MediaService: {}", exc)
            self.media_service = None

        # CategorizedMemoryStore — 基于身份的分类记忆
        try:
            from ava.agent.categorized_memory import CategorizedMemoryStore
            self.categorized_memory = CategorizedMemoryStore(workspace=self.workspace)
        except Exception as exc:
            logger.warning("Failed to init CategorizedMemoryStore: {}", exc)
            self.categorized_memory = None

        # HistorySummarizer — 旧轮次摘要压缩
        try:
            from ava.agent.history_summarizer import HistorySummarizer
            _protect_recent = (
                getattr(self.config, "get", lambda *a, **kw: None)("history_compressor.protect_recent")
                if hasattr(self, "config") and self.config is not None
                else None
            )
            if _protect_recent is None:
                try:
                    _protect_recent = self.config.history_compressor.protect_recent
                except Exception:
                    _protect_recent = None
            if not isinstance(_protect_recent, int) or _protect_recent < 0:
                _protect_recent = 6
            self.history_summarizer = HistorySummarizer(enabled=True, protect_recent=_protect_recent)
        except Exception as exc:
            logger.warning("Failed to init HistorySummarizer: {}", exc)
            self.history_summarizer = None

        # HistoryCompressor — 基于字符预算的历史裁剪
        try:
            from ava.agent.history_compressor import HistoryCompressor
            _max_chars = (
                getattr(self.config, "get", lambda *a, **kw: None)("history_compressor.max_chars")
                if hasattr(self, "config") and self.config is not None
                else None
            )
            if _max_chars is None:
                try:
                    _max_chars = self.config.history_compressor.max_chars
                except Exception:
                    _max_chars = None
            if not isinstance(_max_chars, int) or _max_chars <= 0:
                _max_chars = 20000
            self.history_compressor = HistoryCompressor(max_chars=_max_chars, recent_turns=10)
        except Exception as exc:
            logger.warning("Failed to init HistoryCompressor: {}", exc)
            self.history_compressor = None

        # Back-reference for context_patch to access loop attributes
        if hasattr(self, "context"):
            self.context._agent_loop = self

        # tools_patch registers tools during original_init (before token_stats/media_service
        # are set), so update those references now that everything is initialized.
        try:
            token_stats = getattr(self, "token_stats", None)
            media_service = getattr(self, "media_service", None)
            if hasattr(self, "tools"):
                if vision_tool := self.tools.get("vision"):
                    if hasattr(vision_tool, "_token_stats"):
                        vision_tool._token_stats = token_stats
                if image_gen_tool := self.tools.get("image_gen"):
                    if hasattr(image_gen_tool, "_token_stats"):
                        image_gen_tool._token_stats = token_stats
                    if hasattr(image_gen_tool, "_media_service"):
                        image_gen_tool._media_service = media_service
                if cc_tool := self.tools.get("claude_code"):
                    if hasattr(cc_tool, "_token_stats"):
                        cc_tool._token_stats = token_stats
        except Exception as exc:
            logger.warning("Failed to update tool refs after init: {}", exc)

    AgentLoop.__init__ = patched_init

    # ------------------------------------------------------------------
    # 2. Patch _set_tool_context to also update StickerTool chat context
    # ------------------------------------------------------------------
    original_set_tool_context = AgentLoop._set_tool_context

    def patched_set_tool_context(self: AgentLoop, channel: str, chat_id: str, message_id: str | None = None) -> None:
        original_set_tool_context(self, channel, chat_id, message_id)
        if tool := self.tools.get("send_sticker"):
            if hasattr(tool, "set_context"):
                tool.set_context(channel, chat_id)

    AgentLoop._set_tool_context = patched_set_tool_context

    # ------------------------------------------------------------------
    # 3. Patch _run_agent_loop to capture ALL per-iteration LLM usage.
    #    Each LLM call (tool_call or stop) is recorded as a separate entry
    #    in loop._llm_call_usages so patched_process_message can log them all.
    # ------------------------------------------------------------------
    original_run_agent_loop = AgentLoop._run_agent_loop

    async def patched_run_agent_loop(self: AgentLoop, initial_messages, **kwargs):
        original_chat = self.provider.chat_with_retry
        original_chat_stream = self.provider.chat_stream_with_retry
        # Reset per-turn call list
        self._llm_call_usages = []

        async def intercepted_chat(*args, **kw):
            response = await original_chat(*args, **kw)
            self._llm_call_usages.append(_extract_usage(response))
            return response

        async def intercepted_chat_stream(*args, **kw):
            response = await original_chat_stream(*args, **kw)
            self._llm_call_usages.append(_extract_usage(response))
            return response

        self.provider.chat_with_retry = intercepted_chat
        self.provider.chat_stream_with_retry = intercepted_chat_stream
        try:
            return await original_run_agent_loop(self, initial_messages, **kwargs)
        finally:
            self.provider.chat_with_retry = original_chat
            self.provider.chat_stream_with_retry = original_chat_stream

    def _extract_usage(response) -> dict:
        """Extract and pre-parse all token fields from an LLM response."""
        usage = response.usage or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", 0) or 0) or (prompt_tokens + completion_tokens)
        prompt_details = usage.get("prompt_tokens_details") or {}
        cached_tokens = int(
            prompt_details.get("cached_tokens", 0)
            or usage.get("cache_read_input_tokens", 0)
            or 0
        )
        cache_creation_tokens = int(usage.get("cache_creation_input_tokens", 0) or 0)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "cache_creation_tokens": cache_creation_tokens,
            "finish_reason": response.finish_reason or "",
        }

    AgentLoop._run_agent_loop = patched_run_agent_loop

    # ------------------------------------------------------------------
    # 3b. Patch _save_turn to fix skip mismatch with compressed history.
    #     context_patch's HistorySummarizer/Compressor reduce history size,
    #     but upstream skip = 1 + len(original_history), which overshoots
    #     all_msgs length and causes new messages to be silently dropped.
    #     Fix: use _last_build_msg_count (set by context_patch) as the
    #     actual number of non-system messages in build_messages output.
    # ------------------------------------------------------------------
    original_save_turn = AgentLoop._save_turn

    def fixed_save_turn(self_loop, session, messages, skip):
        corrected = getattr(self_loop, "_last_build_msg_count", None)
        if corrected is not None:
            skip = 1 + corrected  # 1 for system + compressed history (excl. user)
        original_save_turn(self_loop, session, messages, skip)

    AgentLoop._save_turn = fixed_save_turn

    # ------------------------------------------------------------------
    # 4. Patch _process_message to record rich token usage per turn
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
        # Snapshot before to detect new LLM call
        usage_before = dict(getattr(self, "_last_usage", {}))
        # Clear full usage capture so we can detect whether a new call happened
        self._full_last_usage = {}

        result = await original_process_message(
            self, msg,
            session_key=session_key,
            on_progress=on_progress,
            on_stream=on_stream,
            on_stream_end=on_stream_end,
        )

        token_stats = getattr(self, "token_stats", None)
        llm_calls = getattr(self, "_llm_call_usages", [])
        if token_stats is not None and llm_calls:
            try:
                sk = session_key or getattr(msg, "session_key", "")
                user_msg = getattr(msg, "content", "") or ""
                output_content = getattr(result, "content", "") or ""
                system_prompt = getattr(self, "_last_system_prompt", "") or ""
                # Deduplicate: only store system_prompt when it changes from last recorded value
                prev_sys = getattr(self, "_prev_recorded_system_prompt", "")
                if system_prompt == prev_sys:
                    system_prompt_to_store = ""
                else:
                    system_prompt_to_store = system_prompt
                    self._prev_recorded_system_prompt = system_prompt
                provider_name = type(self.provider).__name__.lower().replace("provider", "")

                # Estimate current-turn user message tokens via tiktoken (only for first call)
                current_turn_tokens = 0
                try:
                    from nanobot.utils.helpers import estimate_prompt_tokens
                    if user_msg:
                        current_turn_tokens = estimate_prompt_tokens(
                            [{"role": "user", "content": user_msg}]
                        )
                except Exception:
                    pass

                # Build conversation_history from session (last 10 turns, JSON)
                conversation_history = ""
                try:
                    import json as _json
                    key = sk or getattr(msg, "session_key", "")
                    session = self.sessions.get_or_create(key) if key else None
                    if session:
                        hist = session.get_history(max_messages=10)
                        if hist:
                            conversation_history = _json.dumps(
                                [{"role": m.get("role", ""), "content": str(m.get("content", ""))[:200]}
                                 for m in hist],
                                ensure_ascii=False,
                            )
                except Exception:
                    pass

                # Record every LLM call in this turn (tool_call iterations + final stop)
                for i, call_usage in enumerate(llm_calls):
                    finish_reason = call_usage.get("finish_reason", "")
                    is_tool_call = finish_reason in ("tool_calls", "tool_use")
                    token_stats.record(
                        model=self.model,
                        provider=provider_name,
                        usage=call_usage,
                        session_key=sk,
                        # Only attach user message / output on first and last calls
                        user_message=(user_msg[:1000] if i == 0 else ""),
                        output_content=(output_content[:4000] if i == len(llm_calls) - 1 else ""),
                        system_prompt=system_prompt_to_store,
                        conversation_history=(conversation_history if i == 0 else ""),
                        finish_reason=finish_reason,
                        model_role="tool_call" if is_tool_call else "chat",
                        cached_tokens=call_usage.get("cached_tokens"),
                        cache_creation_tokens=call_usage.get("cache_creation_tokens"),
                        current_turn_tokens=(current_turn_tokens if i == 0 else 0),
                    )
            except Exception as exc:
                logger.warning("Failed to record token stats in loop_patch: {}", exc)
        # Clear after recording
        self._llm_call_usages = []

        return result

    AgentLoop._process_message = patched_process_message

    return "AgentLoop patched: injected db/token_stats/media_service/categorized_memory/summarizer/compressor; _process_message records rich token usage"


register_patch("agent_loop", apply_loop_patch)
