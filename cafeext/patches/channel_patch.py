"""Channel extensions patch for TelegramChannel and SessionManager."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from cafeext.channels.batcher import MessageBatcher
from cafeext.launcher import register_patch
from cafeext.session.backfill_turns import backfill_workspace_sessions


def apply_channel_patch() -> str:
    """
    Patch TelegramChannel to add message batching and SessionManager to add backfill.

    Returns:
        Description of what was patched.
    """
    from nanobot.channels.telegram import TelegramChannel
    from nanobot.config.paths import get_workspace_path
    from nanobot.session.manager import SessionManager

    workspace = get_workspace_path()

    original_send = TelegramChannel.send
    original_load = SessionManager._load

    batcher: MessageBatcher | None = None

    async def batched_send_callback(
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str],
        metadata: dict[str, Any],
        session_key: str | None = None,
    ) -> None:
        """Batch callback that sends merged messages via original send."""
        from nanobot.bus.events import OutboundMessage

        msg = OutboundMessage(
            channel="telegram",
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            media=media,
            metadata=metadata,
        )
        # We need a TelegramChannel instance — store it when first patched send is called
        instance = _channel_instance.get("ref")
        if instance is not None:
            await original_send(instance, msg)

    _channel_instance: dict = {}

    async def patched_send(self: TelegramChannel, msg: Any) -> None:
        """Intercept send to add batching logic."""
        nonlocal batcher

        _channel_instance["ref"] = self

        if batcher is None:
            batcher = MessageBatcher(
                timeout_s=1.0,
                flush_callback=batched_send_callback,
            )

        await batcher.add(
            key=str(msg.chat_id),
            content=msg.content,
            media=getattr(msg, "media", None) or [],
            sender_id=getattr(msg, "sender_id", ""),
            chat_id=msg.chat_id,
            metadata=getattr(msg, "metadata", None) or {},
            session_key=None,
        )

    def patched_load(self: SessionManager, key: str) -> Any:
        """Load session and apply backfill if needed."""
        session = original_load(self, key)

        if session is not None:
            from cafeext.session.backfill_turns import _backfill_messages

            messages = session.messages
            fixed_messages, inserted, normalized = _backfill_messages(messages)

            if inserted > 0 or normalized > 0:
                session.messages = fixed_messages
                logger.info(
                    "Backfilled session {}: {} placeholders added, {} normalized",
                    key, inserted, normalized
                )

        return session

    TelegramChannel.send = patched_send
    SessionManager._load = patched_load

    return "TelegramChannel.send patched with batching, SessionManager patched with backfill"


register_patch("channel_extensions", apply_channel_patch)
