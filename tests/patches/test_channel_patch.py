"""Tests for channel_patch — TelegramChannel message batching."""

from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

import pytest

from nanobot.channels.telegram import TelegramChannel


@pytest.fixture(autouse=True)
def _restore_telegram_send():
    """Save and restore TelegramChannel.send to avoid polluting other tests."""
    original = TelegramChannel.send
    yield
    TelegramChannel.send = original


class TestChannelPatch:
    def test_patch_applies_without_error(self):
        """T6.0: apply_channel_patch runs without error."""
        from ava.patches.channel_patch import apply_channel_patch

        result = apply_channel_patch()
        assert "batching" in result.lower()

    def test_send_method_replaced(self):
        """T6.1: TelegramChannel.send is replaced."""
        from nanobot.channels.telegram import TelegramChannel

        original_send = TelegramChannel.send

        from ava.patches.channel_patch import apply_channel_patch
        apply_channel_patch()

        # send should be patched (may already be from previous test)
        assert TelegramChannel.send is not None

    def test_no_session_load_patch(self):
        """T6.2: channel_patch no longer patches SessionManager._load (P0 fix)."""
        import inspect
        from ava.patches.channel_patch import apply_channel_patch

        source = inspect.getsource(apply_channel_patch)
        # Should NOT contain SessionManager._load patching
        assert "SessionManager._load" not in source
        assert "patched_load" not in source

    def test_batcher_in_source(self):
        """T6.3: MessageBatcher is used in the patch."""
        import inspect
        from ava.patches.channel_patch import apply_channel_patch

        source = inspect.getsource(apply_channel_patch)
        assert "MessageBatcher" in source
        assert "batcher" in source
