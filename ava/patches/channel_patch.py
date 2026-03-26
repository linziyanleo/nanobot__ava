"""Channel extensions patch for TelegramChannel message batching.

Intercept: TelegramChannel.send
Behavior: Messages are queued in a MessageBatcher; within a 1-second window,
multiple messages to the same chat_id are merged into a single send.

Note: Session backfill is handled by storage_patch (after SQLite load),
not here — avoids the _load ordering conflict between channel/storage patches.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from ava.channels.batcher import MessageBatcher
from ava.launcher import register_patch


def apply_channel_patch() -> str:
    """
    Patch TelegramChannel to add message batching.

    Returns:
        Description of what was patched.
    """
    from nanobot.channels.telegram import TelegramChannel

    original_send = TelegramChannel.send

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

    TelegramChannel.send = patched_send

    return "TelegramChannel.send patched with message batching"


register_patch("channel_extensions", apply_channel_patch)
