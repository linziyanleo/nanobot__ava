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
            self.history_summarizer = HistorySummarizer(enabled=True, protect_recent=0)
        except Exception as exc:
            logger.warning("Failed to init HistorySummarizer: {}", exc)
            self.history_summarizer = None

        # HistoryCompressor — 基于字符预算的历史裁剪
        try:
            from ava.agent.history_compressor import HistoryCompressor
            self.history_compressor = HistoryCompressor(max_chars=12000, recent_turns=10)
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
    # 3. Patch _run_agent_loop to capture full LLM response metadata
    #    (finish_reason, cached_tokens, cache_creation_tokens, cost_usd)
    #    that upstream only stores partially in _last_usage.
    # ------------------------------------------------------------------
    original_run_agent_loop = AgentLoop._run_agent_loop

    async def patched_run_agent_loop(self: AgentLoop, initial_messages, **kwargs):
        # Intercept provider.chat_with_retry and chat_stream_with_retry to
        # capture full usage on each LLM call.
        original_chat = self.provider.chat_with_retry
        original_chat_stream = self.provider.chat_stream_with_retry

        async def intercepted_chat(*args, **kw):
            response = await original_chat(*args, **kw)
            _store_full_usage(self, response)
            return response

        async def intercepted_chat_stream(*args, **kw):
            response = await original_chat_stream(*args, **kw)
            _store_full_usage(self, response)
            return response

        self.provider.chat_with_retry = intercepted_chat
        self.provider.chat_stream_with_retry = intercepted_chat_stream
        try:
            return await original_run_agent_loop(self, initial_messages, **kwargs)
        finally:
            self.provider.chat_with_retry = original_chat
            self.provider.chat_stream_with_retry = original_chat_stream

    def _store_full_usage(loop, response) -> None:
        """Copy full usage + finish_reason from response onto loop._full_last_usage.

        Stores pre-parsed token counts alongside the raw usage dict so that
        token_stats_service.record() can use them directly without re-parsing.
        """
        usage = response.usage or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", 0) or 0) or (prompt_tokens + completion_tokens)

        # Cached tokens: OpenAI stores in prompt_tokens_details.cached_tokens,
        # Anthropic stores in cache_read_input_tokens
        prompt_details = usage.get("prompt_tokens_details") or {}
        cached_tokens = int(
            prompt_details.get("cached_tokens", 0)
            or usage.get("cache_read_input_tokens", 0)
            or 0
        )
        # Cache creation tokens: Anthropic uses cache_creation_input_tokens
        cache_creation_tokens = int(usage.get("cache_creation_input_tokens", 0) or 0)

        loop._full_last_usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            # Pre-parsed fields passed directly to record() to avoid double-parsing
            "_cached_tokens": cached_tokens,
            "_cache_creation_tokens": cache_creation_tokens,
            "finish_reason": response.finish_reason or "",
        }

    AgentLoop._run_agent_loop = patched_run_agent_loop

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
        if token_stats is not None:
            last_usage = dict(getattr(self, "_last_usage", {}))
            full_usage = dict(getattr(self, "_full_last_usage", {}))
            # Only record if usage changed (new LLM call happened)
            if last_usage and last_usage != usage_before:
                try:
                    # Prefer full_usage (from intercepted provider calls) for richer data
                    usage_to_record = full_usage if full_usage else last_usage

                    # Extract pre-parsed token fields (prefixed with _) before passing usage
                    cached_tokens = usage_to_record.pop("_cached_tokens", None)
                    cache_creation_tokens = usage_to_record.pop("_cache_creation_tokens", None)
                    finish_reason = usage_to_record.pop("finish_reason", "")

                    sk = session_key or getattr(msg, "session_key", "")
                    user_msg = getattr(msg, "content", "") or ""
                    output_content = getattr(result, "content", "") or ""
                    system_prompt = getattr(self, "_last_system_prompt", "") or ""
                    provider_name = type(self.provider).__name__.lower().replace("provider", "")

                    # Estimate current-turn user message tokens via tiktoken
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
                                    [{"role": m.get("role", ""), "content": str(m.get("content", ""))[:500]}
                                     for m in hist],
                                    ensure_ascii=False,
                                )
                    except Exception:
                        pass

                    token_stats.record(
                        model=self.model,
                        provider=provider_name,
                        usage=usage_to_record,
                        session_key=sk,
                        user_message=user_msg[:1000],
                        output_content=output_content[:4000],
                        system_prompt=system_prompt[:2000],
                        conversation_history=conversation_history,
                        finish_reason=finish_reason,
                        model_role="chat",
                        cached_tokens=cached_tokens,
                        cache_creation_tokens=cache_creation_tokens,
                        current_turn_tokens=current_turn_tokens,
                    )
                except Exception as exc:
                    logger.warning("Failed to record token stats in loop_patch: {}", exc)

        return result

    AgentLoop._process_message = patched_process_message

    return "AgentLoop patched: injected db/token_stats/media_service/categorized_memory/summarizer/compressor; _process_message records rich token usage"


register_patch("agent_loop", apply_loop_patch)
