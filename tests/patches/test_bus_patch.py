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
        """T8.1: registered listener is stored."""
        cb = lambda event: None
        bus.register_console_listener("sess1", cb)
        assert "sess1" in bus._console_listeners

    def test_unregister_listener(self, bus):
        """T8.2: unregistered listener is removed."""
        bus.register_console_listener("sess1", lambda e: None)
        bus.unregister_console_listener("sess1")
        assert "sess1" not in getattr(bus, "_console_listeners", {})

    async def test_dispatch_event(self, bus):
        """T8.3: dispatch calls the registered callback."""
        received = []

        async def cb(event):
            received.append(event)

        bus.register_console_listener("sess1", cb)
        await bus.dispatch_to_console_listener("sess1", {"type": "test"})
        assert len(received) == 1
        assert received[0]["type"] == "test"

    async def test_broken_listener_auto_removed(self, bus):
        """T8.4: broken callback is auto-removed after exception."""
        async def bad_cb(event):
            raise RuntimeError("boom")

        bus.register_console_listener("sess1", bad_cb)
        await bus.dispatch_to_console_listener("sess1", {"type": "test"})
        assert "sess1" not in bus._console_listeners

    async def test_dispatch_no_listener(self, bus):
        """T8.5: dispatch to unregistered session is a no-op."""
        # Should not raise
        await bus.dispatch_to_console_listener("nonexistent", {"type": "test"})

    def test_lazy_init(self):
        """T8.6: _console_listeners doesn't exist until first register."""
        fresh_bus = MessageBus()
        assert not hasattr(fresh_bus, "_console_listeners")
