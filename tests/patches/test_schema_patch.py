"""Tests for a_schema_patch — Config Schema Fork injection."""

import sys
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _clean_schema_module():
    """Remove fork marker before each test so patches can re-apply."""
    mod = sys.modules.get("nanobot.config.schema")
    if mod and getattr(mod, "_ava_fork", False):
        mod._ava_fork = False
    yield


class TestSchemaPatch:
    def test_fork_replaces_module(self):
        """T1.1: fork replaces sys.modules entry and sets _ava_fork marker."""
        from ava.patches.a_schema_patch import apply_schema_patch

        result = apply_schema_patch()
        mod = sys.modules["nanobot.config.schema"]
        assert getattr(mod, "_ava_fork", False) is True
        assert "replaced" in result.lower() or "fork" in result.lower()

    def test_extended_fields_exist(self):
        """T1.2: AgentDefaults instance has vision_model, mini_model etc."""
        from ava.patches.a_schema_patch import apply_schema_patch

        apply_schema_patch()
        from nanobot.config.schema import AgentDefaults

        inst = AgentDefaults()
        for field in ("vision_model", "mini_model", "image_gen_model"):
            assert hasattr(inst, field), f"Missing field: {field}"

    def test_console_config_exists(self):
        """T1.3: GatewayConfig has console field after fork."""
        from ava.patches.a_schema_patch import apply_schema_patch

        apply_schema_patch()
        from nanobot.config.schema import GatewayConfig

        assert "console" in GatewayConfig.model_fields

    def test_idempotent(self):
        """T1.4: calling apply twice does not error."""
        from ava.patches.a_schema_patch import apply_schema_patch

        r1 = apply_schema_patch()
        r2 = apply_schema_patch()
        assert "skipped" in r2.lower()

    def test_fork_file_missing(self):
        """T1.5: returns skip message when fork file doesn't exist."""
        from ava.patches.a_schema_patch import apply_schema_patch
        from pathlib import Path as RealPath

        # Remove _ava_fork marker so it attempts to apply
        mod = sys.modules.get("nanobot.config.schema")
        if mod:
            mod._ava_fork = False

        original_exists = RealPath.exists

        def fake_exists(self):
            if "forks/config/schema.py" in str(self):
                return False
            return original_exists(self)

        try:
            with patch.object(RealPath, "exists", fake_exists):
                result = apply_schema_patch()
            assert "not found" in result.lower() or "skipped" in result.lower()
        finally:
            # Restore fork so subsequent tests aren't polluted
            if mod:
                mod._ava_fork = False
            apply_schema_patch()
