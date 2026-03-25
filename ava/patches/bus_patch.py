"""Patch to add Console WebSocket listener support to MessageBus.

Adds three methods to MessageBus:
  - register_console_listener(session_key, callback)
  - unregister_console_listener(session_key)
  - dispatch_to_console_listener(session_key, event)

This allows the Console WebSocket route to receive real-time
agent progress/result events for a given session.
"""

from __future__ import annotations

from loguru import logger

from ava.launcher import register_patch


def apply_bus_patch() -> str:
    from nanobot.bus.queue import MessageBus

    # --- register_console_listener ---
    def register_console_listener(self: MessageBus, session_key: str, callback) -> None:
        """Register an async callback for console WebSocket events on a session."""
        if not hasattr(self, "_console_listeners"):
            self._console_listeners: dict = {}
        self._console_listeners[session_key] = callback

    # --- unregister_console_listener ---
    def unregister_console_listener(self: MessageBus, session_key: str) -> None:
        """Remove the console listener for a session."""
        listeners = getattr(self, "_console_listeners", {})
        listeners.pop(session_key, None)

    # --- dispatch_to_console_listener ---
    async def dispatch_to_console_listener(
        self: MessageBus, session_key: str, event: dict
    ) -> None:
        """Dispatch an event dict to the registered console listener (fire-and-forget)."""
        listeners = getattr(self, "_console_listeners", {})
        callback = listeners.get(session_key)
        if callback is None:
            return
        try:
            await callback(event)
        except Exception as exc:
            logger.warning(
                "Console listener dispatch error for session {}: {}", session_key, exc
            )
            # Auto-remove broken listener
            listeners.pop(session_key, None)

    MessageBus.register_console_listener = register_console_listener
    MessageBus.unregister_console_listener = unregister_console_listener
    MessageBus.dispatch_to_console_listener = dispatch_to_console_listener

    return "MessageBus patched with register/unregister/dispatch_to_console_listener"


register_patch("bus_console_listener", apply_bus_patch)
