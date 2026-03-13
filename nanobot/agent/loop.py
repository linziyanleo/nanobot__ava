"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import re
import weakref
from contextlib import AsyncExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from nanobot.agent.categorized_memory import CategorizedMemoryStore
from nanobot.agent.commands import CommandRegistry, register_builtin_commands
from nanobot.agent.context import ContextBuilder
from nanobot.agent.history_compressor import HistoryCompressor
from nanobot.agent.history_summarizer import HistorySummarizer
from nanobot.agent.memory import MemoryStore
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.memory_tool import MemoryTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.image_gen import ImageGenTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.vision import VisionTool
from nanobot.agent.tools.sticker import StickerTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.session.manager import Session, SessionManager

if TYPE_CHECKING:
    from nanobot.config.schema import ChannelsConfig, ContextCompressionConfig, ExecToolConfig, InLoopTruncationConfig
    from nanobot.cron.service import CronService


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    _TOOL_RESULT_MAX_CHARS = 500

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        vision_model: str | None = None,
        mini_model: str | None = None,
        voice_model: str | None = None,
        max_iterations: int = 40,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        memory_window: int = 100,
        reasoning_effort: str | None = None,
        brave_api_key: str | None = None,
        web_proxy: str | None = None,
        exec_config: ExecToolConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        restrict_config_file: bool = True,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
        context_compression: ContextCompressionConfig | None = None,
        history_summarizer: Any | None = None,
        memory_tier: str | None = "default",
        in_loop_truncation: InLoopTruncationConfig | None = None,
        token_stats: Any | None = None,
        record_full_request_payload: bool = False,
        db: Any | None = None,
    ):
        from nanobot.config.schema import ContextCompressionConfig, ExecToolConfig, InLoopTruncationConfig as _ILT
        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.vision_model = vision_model or self.model
        self.mini_model = mini_model or self.model
        self.voice_model = voice_model
        self.memory_tier = memory_tier or "default"
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory_window = memory_window
        self.reasoning_effort = reasoning_effort
        self.brave_api_key = brave_api_key
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.restrict_config_file = restrict_config_file
        compression_cfg = context_compression or ContextCompressionConfig()
        self._compression_enabled = compression_cfg.enabled
        self._history_lookup_hint_enabled = compression_cfg.enable_history_lookup_hint
        self._in_loop_truncation = in_loop_truncation or _ILT()
        self._token_stats = token_stats
        self._record_full_request_payload = record_full_request_payload
        self._db = db

        self.categorized_memory = CategorizedMemoryStore(workspace)
        self.context = ContextBuilder(
            workspace,
            categorized_memory=self.categorized_memory,
            in_loop_truncation=self._in_loop_truncation,
            bootstrap_max_chars=compression_cfg.bootstrap_max_chars,
        )
        self.history_compressor = HistoryCompressor(
            max_chars=compression_cfg.max_chars,
            recent_turns=compression_cfg.recent_turns,
            min_recent_turns=compression_cfg.min_recent_turns,
            max_old_turns=compression_cfg.max_old_turns,
            protected_recent_messages=compression_cfg.protected_recent_messages,
        )
        from nanobot.config.schema import HistorySummarizerConfig as _HSC
        _hs_cfg = history_summarizer if isinstance(history_summarizer, _HSC) else _HSC()
        self._summarizer = HistorySummarizer(
            enabled=_hs_cfg.enabled,
            protect_recent=_hs_cfg.protect_recent,
            tool_result_max_chars=_hs_cfg.tool_result_max_chars,
        )
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            mini_model=self.mini_model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            reasoning_effort=reasoning_effort,
            brave_api_key=brave_api_key,
            web_proxy=web_proxy,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
            restrict_config_file=restrict_config_file,
            in_loop_truncation=self._in_loop_truncation,
        )

        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._consolidating: set[str] = set()  # Session keys with consolidation in progress
        self._consolidation_tasks: set[asyncio.Task] = set()  # Strong refs to in-flight tasks
        self._consolidation_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_key -> tasks
        self._processing_lock = asyncio.Lock()
        self._commands = CommandRegistry()
        register_builtin_commands(self._commands, self)
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        blocked_paths: list[Path] | None = None
        if self.restrict_config_file:
            from nanobot.config.loader import get_config_path
            blocked_paths = [get_config_path()]
        for cls in (ReadFileTool, WriteFileTool, EditFileTool, ListDirTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir, blocked_paths=blocked_paths))
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
            path_append=self.exec_config.path_append,
            auto_venv=self.exec_config.auto_venv,
        ))
        self.tools.register(WebSearchTool(proxy=self.web_proxy))
        self.tools.register(WebFetchTool(proxy=self.web_proxy))
        self.tools.register(MessageTool(send_callback=self.bus.publish_outbound))
        self.tools.register(SpawnTool(manager=self.subagents))
        self.tools.register(MemoryTool(store=self.categorized_memory, db=self._db))
        self.tools.register(VisionTool(provider=self.provider, model=self.vision_model, token_stats=self._token_stats))
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))
        self.tools.register(StickerTool())
        try:
            from nanobot.console.services.media_service import MediaService as _MS
            _media_svc = _MS(db=self._db) if self._db else None
            self.tools.register(ImageGenTool(token_stats=self._token_stats, media_service=_media_svc))
        except ValueError as e:
            logger.debug("ImageGenTool not registered: {}", e)

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from nanobot.agent.tools.mcp import connect_mcp_servers
        try:
            self._mcp_stack = AsyncExitStack()
            await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except Exception as e:
            logger.error("Failed to connect MCP servers (will retry next message): {}", e)
            if self._mcp_stack:
                try:
                    await self._mcp_stack.aclose()
                except Exception:
                    pass
                self._mcp_stack = None
        finally:
            self._mcp_connecting = False

    def _set_tool_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """Update context for all tools that need routing info."""
        for name in ("message", "spawn", "cron", "send_sticker"):
            if tool := self.tools.get(name):
                if hasattr(tool, "set_context"):
                    tool.set_context(channel, chat_id, *([message_id] if name == "message" else []))

        if memory_tool := self.tools.get("memory"):
            if isinstance(memory_tool, MemoryTool):
                memory_tool.set_context(channel, chat_id)

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>…</think> blocks that some models embed in content."""
        if not text:
            return None
        return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hint, e.g. 'web_search("query")'."""
        def _fmt(tc):
            args = (tc.arguments[0] if isinstance(tc.arguments, list) else tc.arguments) or {}
            val = next(iter(args.values()), None) if isinstance(args, dict) else None
            if not isinstance(val, str):
                return tc.name
            return f'{tc.name}("{val[:40]}…")' if len(val) > 40 else f'{tc.name}("{val}")'
        return ", ".join(_fmt(tc) for tc in tool_calls)

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        session: Session | None = None,
        on_progress: Callable[..., Awaitable[None]] | None = None,
        turn_seq: int | None = None,
        model: str | None = None,
        model_role: str = "default",
    ) -> tuple[str | None, list[str], list[dict]]:
        """Run the agent iteration loop. Returns (final_content, tools_used, messages)."""
        _effective_model = model or self.model
        messages = initial_messages
        iteration = 0
        final_content = None
        tools_used: list[str] = []
        total_tokens = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0

        conv_history_snapshot = initial_messages[1:-1] if len(initial_messages) > 2 else []

        while iteration < self.max_iterations:
            iteration += 1

            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=_effective_model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                reasoning_effort=self.reasoning_effort,
            )

            # 记录 token 消耗
            if response.usage:
                prompt_tokens = response.usage.get('prompt_tokens', 0)
                completion_tokens = response.usage.get('completion_tokens', 0)
                call_tokens = response.usage.get('total_tokens', 0)
                total_tokens += call_tokens
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += completion_tokens
                logger.debug("💰 LLM 调用 Token 消耗：{} (prompt: {} + completion: {})",
                           call_tokens, prompt_tokens, completion_tokens)

                if self._token_stats:
                    last_user_msg = ""
                    sys_prompt = ""
                    for m in reversed(messages):
                        if m.get("role") == "user" and not last_user_msg:
                            c = m.get("content", "")
                            last_user_msg = c if isinstance(c, str) else str(c)
                    for m in messages:
                        if m.get("role") == "system":
                            c = m.get("content", "")
                            sys_prompt = c if isinstance(c, str) else str(c)
                            break
                    full_payload = ""
                    if self._record_full_request_payload:
                        try:
                            full_payload = json.dumps(messages, ensure_ascii=False)
                        except (TypeError, ValueError):
                            pass
                    try:
                        conv_history_str = json.dumps(conv_history_snapshot, ensure_ascii=False) if conv_history_snapshot else ""
                    except (TypeError, ValueError):
                        conv_history_str = ""
                    _effective_provider = (
                        _effective_model.split("/", 1)[0]
                        if "/" in _effective_model
                        else self.provider.provider_name
                    )
                    self._token_stats.record(
                        model=_effective_model,
                        provider=_effective_provider,
                        usage=response.usage,
                        session_key=session.key if session else "",
                        turn_seq=turn_seq,
                        iteration=iteration,
                        user_message=last_user_msg,
                        output_content=response.content or "",
                        system_prompt=sys_prompt,
                        conversation_history=conv_history_str,
                        full_request_payload=full_payload,
                        finish_reason=response.finish_reason or "",
                        model_role=model_role,
                    )

            if response.has_tool_calls:
                if on_progress:
                    if response.reasoning_content:
                        await on_progress(response.reasoning_content, is_thinking=True)

                    thoughts = [
                        self._strip_think(response.content),
                        *(
                            f"Thinking [{b.get('signature', '...')}]:\n{b.get('thought', '...')}"
                            for b in (response.thinking_blocks or [])
                            if isinstance(b, dict) and "signature" in b
                        ),
                    ]
                    combined_thoughts = "\n\n".join(filter(None, thoughts))
                    if combined_thoughts:
                        await on_progress(combined_thoughts)
                    await on_progress(self._tool_hint(response.tool_calls), tool_hint=True)

                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )

                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info("Tool call: {}({})", tool_call.name, args_str[:200])
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                clean = self._strip_think(response.content)
                # Don't persist error responses to session history — they can
                # poison the context and cause permanent 400 loops (#1303).
                if response.finish_reason == "error":
                    logger.error("LLM returned error: {}", (clean or "")[:200])
                    final_content = clean or "Sorry, I encountered an error calling the AI model."
                    break
                messages = self.context.add_assistant_message(
                    messages, clean, reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )
                final_content = clean
                break

        if final_content is None and iteration >= self.max_iterations:
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            final_content = (
                f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
                "without completing the task. You can try breaking the task into smaller steps."
            )
            messages = self.context.add_assistant_message(messages, final_content)

        # 记录本轮对话总 token 消耗
        if total_tokens > 0:
            logger.info("📊 本轮对话总 Token 消耗：{} (prompt: {} + completion: {}, LLM 调用 {} 次)",
                       total_tokens, total_prompt_tokens, total_completion_tokens, iteration)

        # 更新 session 的 token 统计
        if session is not None and total_tokens > 0:
            session.token_stats["total_tokens"] += total_tokens
            session.token_stats["total_prompt_tokens"] += total_prompt_tokens
            session.token_stats["total_completion_tokens"] += total_completion_tokens
            session.token_stats["llm_calls"] += iteration

        return final_content, tools_used, messages

    async def run(self) -> None:
        """Run the agent loop, dispatching messages as tasks to stay responsive to /stop."""
        self._running = True
        await self._connect_mcp()
        logger.info("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            cmd = self._commands.match(msg.content)
            if cmd and cmd.pre_dispatch:
                result = await cmd.handler(msg, self)
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id, content=result,
                ))
            else:
                task = asyncio.create_task(self._dispatch(msg))
                self._active_tasks.setdefault(msg.session_key, []).append(task)
                task.add_done_callback(lambda t, k=msg.session_key: self._active_tasks.get(k, []) and self._active_tasks[k].remove(t) if t in self._active_tasks.get(k, []) else None)

    async def _dispatch(self, msg: InboundMessage) -> None:
        """Process a message under the global lock."""
        async with self._processing_lock:
            try:
                response = await self._process_message(msg)
                if response is not None:
                    await self.bus.publish_outbound(response)
                else:
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id,
                        content="", metadata=msg.metadata or {},
                    ))
            except asyncio.CancelledError:
                logger.info("Task cancelled for session {}", msg.session_key)
                raise
            except Exception:
                logger.exception("Error processing message for session {}", msg.session_key)
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Sorry, I encountered an error.",
                ))

    async def close_mcp(self) -> None:
        """Close MCP connections."""
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # MCP SDK cancel scope cleanup is noisy but harmless
            self._mcp_stack = None

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        model_override: str | None = None,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""
        # System messages: parse origin from chat_id ("channel:chat_id")
        if msg.channel == "system":
            channel, chat_id = (msg.chat_id.split(":", 1) if ":" in msg.chat_id
                                else ("cli", msg.chat_id))
            logger.info("Processing system message from {}", msg.sender_id)
            key = f"{channel}:{chat_id}"
            session = self.sessions.get_or_create(key)
            self._set_tool_context(channel, chat_id, msg.metadata.get("message_id"))
            if message_tool := self.tools.get("message"):
                if isinstance(message_tool, MessageTool):
                    message_tool.start_turn()

            _sys_model_tier = msg.metadata.get("model_tier")
            _sys_model: str | None = model_override
            if not _sys_model and _sys_model_tier:
                _sys_model = self.get_model_for_tier(_sys_model_tier)

            history = session.get_history(max_messages=self.memory_window)
            history = self._summarizer.summarize(history)
            if self._compression_enabled:
                history = self.history_compressor.compress(history, msg.content)
            messages = self.context.build_messages(
                history=history,
                current_message=msg.content, channel=channel, chat_id=chat_id,
            )

            async def _sys_progress(content: str, *, tool_hint: bool = False, is_thinking: bool = False) -> None:
                if is_thinking:
                    return
                meta = {"_progress": True, "_tool_hint": tool_hint}
                await self.bus.publish_outbound(OutboundMessage(
                    channel=channel, chat_id=chat_id, content=content, metadata=meta,
                ))

            _turn_seq = sum(1 for m in session.messages if m.get("role") == "user")

            _sys_model_role = "mini" if _sys_model_tier == "mini" else "default"
            final_content, _, all_msgs = await self._run_agent_loop(
                messages, session, on_progress=_sys_progress, turn_seq=_turn_seq,
                model=_sys_model, model_role=_sys_model_role,
            )

            # Check if delivery tools already sent content
            _sticker_sent = False
            if (st := self.tools.get("send_sticker")):
                from nanobot.agent.tools.sticker import StickerTool
                if isinstance(st, StickerTool) and st._sent_in_turn:
                    _sticker_sent = True
                    st._sent_in_turn = False

            _message_sent = False
            if (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
                _message_sent = True

            self._save_turn(session, all_msgs, 1 + len(history))
            self.sessions.save(session)

            _content_is_empty = (
                final_content is None
                or not final_content.strip()
                or final_content.strip().lower() in ("(empty)", "empty", "…", "...")
            )
            if _message_sent or (_sticker_sent and _content_is_empty):
                return None

            return OutboundMessage(channel=channel, chat_id=chat_id,
                                  content=final_content or "Background task completed.")

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session = self.sessions.get_or_create(key)

        slash_cmd = self._commands.match(msg.content)
        if slash_cmd and not slash_cmd.pre_dispatch:
            result = await slash_cmd.handler(msg, self)
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=result)

        unconsolidated = len(session.messages) - session.last_consolidated
        if (unconsolidated >= self.memory_window and session.key not in self._consolidating):
            self._consolidating.add(session.key)
            lock = self._consolidation_locks.setdefault(session.key, asyncio.Lock())

            async def _consolidate_and_unlock():
                try:
                    async with lock:
                        await self._consolidate_memory(session)
                finally:
                    self._consolidating.discard(session.key)
                    _task = asyncio.current_task()
                    if _task is not None:
                        self._consolidation_tasks.discard(_task)

            _task = asyncio.create_task(_consolidate_and_unlock())
            self._consolidation_tasks.add(_task)

        self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"))
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        history = session.get_history(max_messages=self.memory_window)
        history = self._summarizer.summarize(history)
        if self._compression_enabled:
            history = self.history_compressor.compress(history, msg.content)
        current_message = self._augment_history_lookup_hint(
            history, msg.content, channel=msg.channel, chat_id=msg.chat_id
        )

        _turn_seq = sum(1 for m in session.messages if m.get("role") == "user")

        _chat_model = model_override or self.model

        # Pre-process media: transcribe audio with voice_model, describe images with vision_model
        _effective_media = list(msg.media) if msg.media else None
        if msg.media:
            _audio_exts = {"ogg", "mp3", "m4a", "wav", "aac", "flac", "opus"}
            _has_audio = any(p.rsplit(".", 1)[-1].lower() in _audio_exts for p in msg.media if "." in p)

            # Step 1: Transcribe audio → inject text, strip raw audio from media
            if _has_audio and self.voice_model and self.voice_model != _chat_model:
                _audio_paths = [
                    p for p in msg.media
                    if "." in p and p.rsplit(".", 1)[-1].lower() in _audio_exts
                ]
                _transcription = await self._transcribe_audio(_audio_paths, session, turn_seq=_turn_seq)
                _effective_media = [
                    p for p in (_effective_media or [])
                    if "." not in p or p.rsplit(".", 1)[-1].lower() not in _audio_exts
                ]
                if not _effective_media:
                    _effective_media = None
                current_message = (
                    f"{current_message}\n\n[语音转录: {_transcription}]"
                    if current_message.strip() else f"[语音转录: {_transcription}]"
                )

            # Step 2: Describe images with vision_model → inject text, strip raw images
            import mimetypes as _mt
            _image_paths = [
                p for p in (_effective_media or [])
                if _mt.guess_type(p)[0] and _mt.guess_type(p)[0].startswith("image/")
            ]
            if _image_paths and self.vision_model != _chat_model:
                _description = await self._describe_images(_image_paths, session, turn_seq=_turn_seq)
                _effective_media = [
                    p for p in (_effective_media or [])
                    if not (_mt.guess_type(p)[0] and _mt.guess_type(p)[0].startswith("image/"))
                ]
                if not _effective_media:
                    _effective_media = None
                current_message = (
                    f"{current_message}\n\n[图片识别: {_description}]"
                    if current_message.strip() else f"[图片识别: {_description}]"
                )

        initial_messages = self.context.build_messages(
            history=history,
            current_message=current_message,
            media=_effective_media,
            channel=msg.channel, chat_id=msg.chat_id,
        )

        async def _bus_progress(content: str, *, tool_hint: bool = False, is_thinking: bool = False) -> None:
            if is_thinking:
                return
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
            ))

        final_content, _, all_msgs = await self._run_agent_loop(
            initial_messages, session, on_progress=on_progress or _bus_progress,
            turn_seq=_turn_seq, model=model_override,
        )

        # Check if any "delivery" tool already sent content to the user
        _sticker_sent = False
        if (st := self.tools.get("send_sticker")):
            from nanobot.agent.tools.sticker import StickerTool
            if isinstance(st, StickerTool) and st._sent_in_turn:
                _sticker_sent = True
                st._sent_in_turn = False  # reset for next turn

        _message_sent = False
        if (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
            _message_sent = True

        if final_content is None:
            if _sticker_sent or _message_sent:
                # Already delivered content via tool, no need for fallback
                final_content = None
            else:
                final_content = "I've completed processing but have no response to give."

        self._save_turn(session, all_msgs, 1 + len(history))
        self.sessions.save(session)

        _content_is_empty = (
            final_content is None
            or not final_content.strip()
            or final_content.strip().lower() in ("(empty)", "empty", "…", "...")
        )
        if _message_sent or (_sticker_sent and _content_is_empty):
            return None

        if final_content is None:
            # Shouldn't reach here, but just in case
            final_content = "I've completed processing but have no response to give."

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)
        return OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=final_content,
            metadata=msg.metadata or {},
        )

    _HISTORY_LOOKUP_RE = re.compile(r"(之前|上次|历史|记得|曾经|以前|聊过|记录|还记得)")

    async def _transcribe_audio(
        self, audio_paths: list[str], session: Session | None = None,
        turn_seq: int | None = None,
    ) -> str:
        """Use voice_model to transcribe audio files.

        Returns transcription text on success, or an error description on failure.
        Raw audio is never forwarded to the default model.
        """
        import base64 as _b64

        content: list[dict] = []
        for path in audio_paths:
            p = Path(path)
            if not p.is_file():
                continue
            ext = p.suffix.lstrip(".").lower()
            fmt = ContextBuilder._AUDIO_FORMAT_MAP.get(ext, "wav")
            b64 = _b64.b64encode(p.read_bytes()).decode()
            content.append({"type": "input_audio", "input_audio": {"data": b64, "format": fmt}})

        if not content:
            return "[语音转录失败: 未找到有效的音频文件]"

        content.append({
            "type": "text",
            "text": "请转录这段语音的内容，输出转录文本，以及对应的语气。格式为：[语音转录: 转录文本 (语气)]",
        })

        messages = [{"role": "user", "content": content}]
        try:
            response = await self.provider.chat(
                messages=messages,
                model=self.voice_model,
                max_tokens=2048,
                temperature=0.1,
            )

            if response.usage:
                if self._token_stats:
                    _effective_provider = (
                        self.voice_model.split("/", 1)[0]
                        if "/" in self.voice_model
                        else self.provider.provider_name
                    )
                    self._token_stats.record(
                        model=self.voice_model,
                        provider=_effective_provider,
                        usage=response.usage,
                        session_key=session.key if session else "",
                        turn_seq=turn_seq,
                        user_message="[audio transcription]",
                        output_content=response.content or "",
                        system_prompt="",
                        conversation_history="",
                        full_request_payload="",
                        finish_reason=response.finish_reason or "",
                        model_role="voice",
                    )
                logger.debug(
                    "🎙️ Voice transcription tokens: {} (prompt: {} + completion: {})",
                    response.usage.get("total_tokens", 0),
                    response.usage.get("prompt_tokens", 0),
                    response.usage.get("completion_tokens", 0),
                )

            result = response.content
            if not result or not result.strip():
                return "[语音转录失败: 模型返回空内容]"
            return result.strip()
        except Exception as e:
            logger.error("Voice transcription failed: {}", e)
            return f"[语音转录失败: {e}]"

    async def _describe_images(
        self, image_paths: list[str], session: Session | None = None,
        turn_seq: int | None = None,
    ) -> str:
        """Use vision_model to describe images as text.

        Returns image description on success, or an error description on failure.
        Raw image data is never forwarded to the default model.
        """
        import base64 as _b64
        import mimetypes as _mt

        content: list[dict] = []
        for path in image_paths:
            p = Path(path)
            if not p.is_file():
                continue
            mime, _ = _mt.guess_type(path)
            if not mime or not mime.startswith("image/"):
                continue
            b64 = _b64.b64encode(p.read_bytes()).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

        if not content:
            return "[图片识别失败: 未找到有效的图片文件]"

        content.append({
            "type": "text",
            "text": "请详细描述这些图片的内容。如果图片中包含文字，请完整提取。",
        })

        messages = [{"role": "user", "content": content}]
        try:
            response = await self.provider.chat(
                messages=messages,
                model=self.vision_model,
                max_tokens=4096,
                temperature=0.3,
            )

            if response.usage:
                if self._token_stats:
                    _effective_provider = (
                        self.vision_model.split("/", 1)[0]
                        if "/" in self.vision_model
                        else self.provider.provider_name
                    )
                    self._token_stats.record(
                        model=self.vision_model,
                        provider=_effective_provider,
                        usage=response.usage,
                        session_key=session.key if session else "",
                        turn_seq=turn_seq,
                        user_message="[image description]",
                        output_content=response.content or "",
                        system_prompt="",
                        conversation_history="",
                        full_request_payload="",
                        finish_reason=response.finish_reason or "",
                        model_role="vision",
                    )
                logger.debug(
                    "👁️ Vision description tokens: {} (prompt: {} + completion: {})",
                    response.usage.get("total_tokens", 0),
                    response.usage.get("prompt_tokens", 0),
                    response.usage.get("completion_tokens", 0),
                )

            result = response.content
            if not result or not result.strip():
                return "[图片识别失败: 模型返回空内容]"
            return result.strip()
        except Exception as e:
            logger.error("Image description failed: {}", e)
            return f"[图片识别失败: {e}]"

    def _save_turn(self, session: Session, messages: list[dict], skip: int) -> None:
        """Save new-turn messages into session, truncating large tool results."""
        from datetime import datetime
        new_msgs = messages[skip:]
        for idx, m in enumerate(new_msgs):
            entry = dict(m)
            role, content = entry.get("role"), entry.get("content")
            if role == "assistant" and not content and not entry.get("tool_calls"):
                prev_role = new_msgs[idx - 1].get("role") if idx > 0 else None
                if prev_role == "tool" or (session.messages and session.messages[-1].get("role") == "tool"):
                    entry["content"] = ""
                else:
                    continue
            if role == "tool" and isinstance(content, str) and len(content) > self._TOOL_RESULT_MAX_CHARS:
                entry["content"] = content[:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
            elif role == "user":
                if isinstance(content, str) and content.startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                    # Strip the runtime-context prefix, keep only the user text.
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        entry["content"] = parts[1]
                    else:
                        continue
                if isinstance(content, list):
                    filtered = []
                    for c in content:
                        if c.get("type") == "text" and isinstance(c.get("text"), str) and c["text"].startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                            continue  # Strip runtime context from multimodal messages
                        if (c.get("type") == "image_url"
                                and c.get("image_url", {}).get("url", "").startswith("data:image/")):
                            filtered.append({"type": "text", "text": "[image]"})
                        elif c.get("type") == "input_audio":
                            filtered.append({"type": "text", "text": "[audio]"})
                        else:
                            filtered.append(c)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
        session.last_completed = Session.compute_last_completed(session.messages)
        if session.messages and session.messages[-1].get("role") != "assistant":
            logger.warning(
                "Session {} saved an incomplete turn: tail role={}",
                session.key, session.messages[-1].get("role"),
            )
        session.updated_at = datetime.now()

    def _needs_history_lookup(self, history: list[dict[str, Any]], current_message: str) -> bool:
        """Heuristic: trigger memory search hint when query asks past context not in compressed history."""
        if not self._history_lookup_hint_enabled:
            return False
        if not current_message or not self._HISTORY_LOOKUP_RE.search(current_message):
            return False

        query_terms = self.history_compressor.extract_terms(current_message)
        if not query_terms:
            return False

        chunks: list[str] = []
        for msg in history:
            if msg.get("role") not in ("user", "assistant"):
                continue
            content = msg.get("content")
            if isinstance(content, str):
                chunks.append(content.lower())
        history_blob = "\n".join(chunks)
        if not history_blob:
            return True

        return not any(term.lower() in history_blob for term in query_terms)

    def _augment_history_lookup_hint(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        *,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> str:
        """Append a deterministic hint to nudge memory.search_history when compressed context is missing."""
        if not self._needs_history_lookup(history, current_message):
            return current_message
        payload = json.dumps(
            {"action": "search_history", "content": current_message},
            ensure_ascii=False,
        )
        session_hint = ""
        if channel and chat_id:
            session_hint = f"\n(当前会话: {channel}_{chat_id}，搜索将优先在当前会话中查找)"
        hint = (
            "\n\n[History Lookup Hint]\n"
            "当前压缩上下文里可能缺少相关历史信息。"
            "请调用 memory 工具检索后再回答：\n"
            f"{payload}{session_hint}"
        )
        return f"{current_message}{hint}"

    async def _consolidate_memory(self, session, archive_all: bool = False) -> bool:
        """Delegate to MemoryStore.consolidate(). Returns True on success."""
        consolidation_model = self.get_model_for_tier(self.memory_tier)
        return await MemoryStore(self.workspace).consolidate(
            session, self.provider, consolidation_model,
            archive_all=archive_all, memory_window=self.memory_window,
            categorized_store=self.categorized_memory,
        )

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        model_override: str | None = None,
    ) -> str:
        """Process a message directly (for CLI or cron usage).

        Args:
            model_override: If provided, use this model instead of self.model for the request.
        """
        await self._connect_mcp()
        session = self.sessions.get_or_create(session_key)
        msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content)

        response = await self._process_message(
            msg, session_key=session_key, on_progress=on_progress,
            model_override=model_override,
        )
        return response.content if response else ""

    def get_model_for_tier(self, tier: str | None) -> str:
        """Get model name for a given tier.

        Args:
            tier: "mini" for lightweight model, "default"/None for main model.

        Returns:
            The appropriate model name.
        """
        if tier == "mini":
            return self.mini_model
        return self.model
