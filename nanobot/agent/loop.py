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
from nanobot.agent.context import ContextBuilder
from nanobot.agent.history_compressor import HistoryCompressor
from nanobot.agent.memory import MemoryStore
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.memory_tool import MemoryTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.registry import ToolRegistry
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
        exec_config: ExecToolConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
        context_compression: ContextCompressionConfig | None = None,
        memory_tier: str | None = "default",
        in_loop_truncation: InLoopTruncationConfig | None = None,
        token_stats: Any | None = None,
        record_full_request_payload: bool = False,
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
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        compression_cfg = context_compression or ContextCompressionConfig()
        self._compression_enabled = compression_cfg.enabled
        self._history_lookup_hint_enabled = compression_cfg.enable_history_lookup_hint
        self._in_loop_truncation = in_loop_truncation or _ILT()
        self._token_stats = token_stats
        self._record_full_request_payload = record_full_request_payload

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
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
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
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        for cls in (ReadFileTool, WriteFileTool, EditFileTool, ListDirTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.restrict_to_workspace,
            path_append=self.exec_config.path_append,
        ))
        self.tools.register(WebSearchTool())
        self.tools.register(WebFetchTool())
        self.tools.register(MessageTool(send_callback=self.bus.publish_outbound))
        self.tools.register(SpawnTool(manager=self.subagents))
        self.tools.register(MemoryTool(store=self.categorized_memory))
        self.tools.register(VisionTool(provider=self.provider, model=self.vision_model))
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))
        self.tools.register(StickerTool())

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
    ) -> tuple[str | None, list[str], list[dict]]:
        """Run the agent iteration loop. Returns (final_content, tools_used, messages)."""
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
                model=self.model,
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
                        self.model.split("/", 1)[0]
                        if "/" in self.model
                        else self.provider.provider_name
                    )
                    self._token_stats.record(
                        model=self.model,
                        provider=_effective_provider,
                        usage=response.usage,
                        session_key=session.key if session else "",
                        user_message=last_user_msg,
                        output_content=response.content or "",
                        system_prompt=sys_prompt,
                        conversation_history=conv_history_str,
                        full_request_payload=full_payload,
                        finish_reason=response.finish_reason or "",
                    )

            if response.has_tool_calls:
                if on_progress:
                    thoughts = [
                        self._strip_think(response.content),
                        response.reasoning_content,
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

            if msg.content.strip().lower() == "/stop":
                await self._handle_stop(msg)
            else:
                task = asyncio.create_task(self._dispatch(msg))
                self._active_tasks.setdefault(msg.session_key, []).append(task)
                task.add_done_callback(lambda t, k=msg.session_key: self._active_tasks.get(k, []) and self._active_tasks[k].remove(t) if t in self._active_tasks.get(k, []) else None)

    async def _handle_stop(self, msg: InboundMessage) -> None:
        """Cancel all active tasks and subagents for the session."""
        tasks = self._active_tasks.pop(msg.session_key, [])
        cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        sub_cancelled = await self.subagents.cancel_by_session(msg.session_key)
        total = cancelled + sub_cancelled
        content = f"⏹ Stopped {total} task(s)." if total else "No active task to stop."
        await self.bus.publish_outbound(OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=content,
        ))

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
            history = session.get_history(max_messages=self.memory_window)
            if self._compression_enabled:
                history = self.history_compressor.compress(history, msg.content)
            messages = self.context.build_messages(
                history=history,
                current_message=msg.content, channel=channel, chat_id=chat_id,
            )
            final_content, _, all_msgs = await self._run_agent_loop(messages, session)
            self._save_turn(session, all_msgs, 1 + len(history))
            self.sessions.save(session)
            return OutboundMessage(channel=channel, chat_id=chat_id,
                                  content=final_content or "Background task completed.")

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session = self.sessions.get_or_create(key)

        # Slash commands
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            lock = self._consolidation_locks.setdefault(session.key, asyncio.Lock())
            self._consolidating.add(session.key)
            try:
                async with lock:
                    snapshot = session.messages[session.last_consolidated:]
                    if snapshot:
                        temp = Session(key=session.key)
                        temp.messages = list(snapshot)
                        if not await self._consolidate_memory(temp, archive_all=True):
                            return OutboundMessage(
                                channel=msg.channel, chat_id=msg.chat_id,
                                content="Memory archival failed, session not cleared. Please try again.",
                            )
            except Exception:
                logger.exception("/new archival failed for {}", session.key)
                return OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Memory archival failed, session not cleared. Please try again.",
                )
            finally:
                self._consolidating.discard(session.key)

            session.clear()
            self.sessions.save(session)
            self.sessions.invalidate(session.key)
            # Clean up lock entry for fully invalidated session
            self._consolidation_locks.pop(session.key, None)
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="New session started.")
        if cmd == "/help":
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="🐈 Nanobot commands:\n/new — Start a new conversation\n/stop — Stop the current task\n/help — Show available commands")

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
        if self._compression_enabled:
            history = self.history_compressor.compress(history, msg.content)
        current_message = self._augment_history_lookup_hint(
            history, msg.content, channel=msg.channel, chat_id=msg.chat_id
        )
        initial_messages = self.context.build_messages(
            history=history,
            current_message=current_message,
            media=msg.media if msg.media else None,
            channel=msg.channel, chat_id=msg.chat_id,
        )

        # Use vision/voice model when user message contains images/audio
        _model_swap = None
        if msg.media and msg.media:
            import mimetypes as _mt
            _has_image = any(_mt.guess_type(p)[0] and _mt.guess_type(p)[0].startswith("image/") for p in msg.media)
            _audio_exts = {"ogg", "mp3", "m4a", "wav", "aac", "flac", "opus"}
            _has_audio = any(p.rsplit(".", 1)[-1].lower() in _audio_exts for p in msg.media if "." in p)
            if _has_audio and self.voice_model and self.voice_model != self.model:
                _model_swap = self.model
                self.model = self.voice_model
            elif _has_image and self.vision_model != self.model:
                _model_swap = self.model
                self.model = self.vision_model

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
            ))

        try:
            final_content, _, all_msgs = await self._run_agent_loop(
                initial_messages, session, on_progress=on_progress or _bus_progress,
            )
        finally:
            if _model_swap is not None:
                self.model = _model_swap

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
            model_override: If provided, temporarily use this model for the request.
        """
        await self._connect_mcp()
        session = self.sessions.get_or_create(session_key)
        msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content)

        # Temporarily swap model if override provided
        original_model = None
        if model_override:
            original_model = self.model
            self.model = model_override

        try:
            response = await self._process_message(msg, session_key=session_key, on_progress=on_progress)
            return response.content if response else ""
        finally:
            if original_model:
                self.model = original_model

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
