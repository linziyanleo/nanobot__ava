"""Replace nanobot.config.schema with ava fork before any other import.

The fork adds or extends:
  - AgentDefaults: vision_model, mini_model, image_gen_model, memory_tier,
    memory_window, context_compression, in_loop_truncation, history_summarizer
  - ConsoleConfig
  - ClaudeCodeConfig
  - TokenStatsConfig
  - Channel config classes (TelegramConfig, FeishuConfig, etc.)
  - GatewayConfig.console field

This patch must run FIRST (alphabetically before other patches).
Rename to schema_patch.py so 's' < 't' (tools) but after 'c' (config_patch).
Since this completely replaces the module, config_patch.py is superseded
and can be removed or will be a no-op.
"""

from __future__ import annotations

import sys

from loguru import logger

from ava.launcher import register_patch


def apply_schema_patch() -> str:
    # Only inject if not already replaced
    if getattr(sys.modules.get("nanobot.config.schema"), "_ava_fork", False):
        return "schema already patched (skipped)"

    try:
        import importlib
        import importlib.util
        from pathlib import Path

        fork_path = Path(__file__).parent.parent / "forks" / "config" / "schema.py"
        if not fork_path.exists():
            return f"Fork schema not found at {fork_path} — skipped"

        spec = importlib.util.spec_from_file_location("nanobot.config.schema", fork_path)
        fork_mod = importlib.util.module_from_spec(spec)
        fork_mod._ava_fork = True  # marker

        # Execute the fork module
        spec.loader.exec_module(fork_mod)

        # Replace in sys.modules
        sys.modules["nanobot.config.schema"] = fork_mod

        # Also patch the nanobot.config package's schema attribute
        import nanobot.config as config_pkg
        config_pkg.schema = fork_mod

        # Update Config reference in loader (it uses `from ... import Config`)
        try:
            import nanobot.config.loader as loader_mod
            loader_mod.Config = fork_mod.Config
        except Exception:
            pass

        logger.info("Replaced nanobot.config.schema with ava fork")
        return "nanobot.config.schema replaced with ava fork (ConsoleConfig, multi-model, channel configs)"

    except Exception as exc:
        logger.error("Failed to apply schema_patch: {}", exc)
        return f"schema_patch FAILED: {exc}"


register_patch("config_schema_fork", apply_schema_patch)
