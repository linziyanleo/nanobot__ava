"""Async message queue for decoupled channel-agent communication."""

from __future__ import annotations

import asyncio

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.

    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.

    Console listeners allow WebSocket handlers to receive outbound messages
    destined for ``channel="console"`` sessions (e.g. async task results).
    """

    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        # session_key -> per-listener queue for console push notifications
        self._console_listeners: dict[str, asyncio.Queue[OutboundMessage]] = {}

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent."""
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish a response from the agent to channels."""
        await self.outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        return await self.outbound.get()

    # ------------------------------------------------------------------
    # Console listener helpers (for WebSocket push of async results)
    # ------------------------------------------------------------------

    def register_console_listener(self, session_key: str) -> asyncio.Queue[OutboundMessage]:
        """Register a listener queue for a console session.

        Returns the queue that the caller should ``await .get()`` on.
        """
        queue: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._console_listeners[session_key] = queue
        logger.debug("Console listener registered for {}", session_key)
        return queue

    def unregister_console_listener(self, session_key: str) -> None:
        """Remove a previously registered console listener."""
        self._console_listeners.pop(session_key, None)
        logger.debug("Console listener unregistered for {}", session_key)

    def dispatch_to_console_listener(self, msg: OutboundMessage) -> bool:
        """Try to deliver an outbound message to a registered console listener.

        Returns ``True`` if a matching listener was found and the message was
        enqueued, ``False`` otherwise.
        """
        session_key = f"console:{msg.chat_id}"
        listener = self._console_listeners.get(session_key)
        if listener is not None:
            listener.put_nowait(msg)
            return True
        return False

    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()