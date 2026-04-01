"""Tests for bus_patch — MessageBus Console listener injection."""

import asyncio

import pytest

from nanobot.bus.queue import MessageBus


@pytest.fixture
def bus():
    return MessageBus()


@pytest.fixture(autouse=True)
def _apply_bus_patch():
    from ava.patches.bus_patch import apply_bus_patch
    apply_bus_patch()


class TestBusPatch:
    def test_register_listener(self, bus):
        """T8.1: register returns and stores a queue listener."""
        queue = bus.register_console_listener("sess1")
        assert isinstance(queue, asyncio.Queue)
        assert bus._console_listeners["sess1"] is queue

    def test_unregister_listener(self, bus):
        """T8.2: unregistered listener is removed."""
        bus.register_console_listener("sess1")
        bus.unregister_console_listener("sess1")
        assert "sess1" not in getattr(bus, "_console_listeners", {})

    async def test_dispatch_event(self, bus):
        """T8.3: dispatch enqueues the event for the registered session."""
        queue = bus.register_console_listener("sess1")
        event = {"type": "test"}
        await bus.dispatch_to_console_listener("sess1", event)
        received = await asyncio.wait_for(queue.get(), timeout=0.1)
        assert received == event

    def test_re_register_listener_replaces_queue(self, bus):
        """T8.4: repeated register replaces the previous queue for the same session."""
        old_queue = bus.register_console_listener("sess1")
        new_queue = bus.register_console_listener("sess1")
        assert old_queue is not new_queue
        assert bus._console_listeners["sess1"] is new_queue

    async def test_dispatch_no_listener(self, bus):
        """T8.5: dispatch to unregistered session is a no-op."""
        # Should not raise
        await bus.dispatch_to_console_listener("nonexistent", {"type": "test"})

    def test_lazy_init(self):
        """T8.6: _console_listeners doesn't exist until first register."""
        fresh_bus = MessageBus()
        assert not hasattr(fresh_bus, "_console_listeners")
