"""Replace nanobot.config.schema with ava fork before any other import.

The fork adds or extends:
  - AgentDefaults: vision_model, mini_model, image_gen_model, memory_tier,
    memory_window, context_compression, in_loop_truncation, history_summarizer
  - ConsoleConfig
  - ClaudeCodeConfig
  - TokenStatsConfig
  - ApiConfig
  - Channel config classes (TelegramConfig, FeishuConfig, etc.)
  - GatewayConfig.console field

This patch must run FIRST (alphabetically before other patches).
Keep the `a_` prefix so it runs before the remaining patches.
Since this completely replaces the module, config_patch.py becomes a
no-op fallback when the fork file is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

from loguru import logger

from ava.launcher import register_patch


def _fork_module_is_healthy(module: ModuleType) -> bool:
    """复用已有 fork 前做最小健康检查，避免沿用被污染或旧版本的类图。"""
    try:
        if "claude_code_model" in getattr(module.AgentDefaults, "model_fields", {}):
            return False

        dumped = module.Config().model_dump(mode="json", by_alias=True)
        defaults = dumped["agents"]["defaults"]
        if "visionModel" not in defaults:
            return False

        validated = module.Config.model_validate({"gateway": {"console": {"enabled": False}}})
        console = getattr(validated.gateway, "console", None)
        return console is not None
    except Exception:
        return False


def apply_schema_patch() -> str:
    fork_path = (Path(__file__).parent.parent / "forks" / "config" / "schema.py").resolve()
    current_schema = sys.modules.get("nanobot.config.schema")

    # Only inject if not already replaced
    if getattr(current_schema, "_ava_fork", False):
        current_path = getattr(current_schema, "__file__", None)
        if current_path and Path(current_path).resolve() == fork_path and _fork_module_is_healthy(current_schema):
            return "schema already patched (skipped)"

    if isinstance(current_schema, ModuleType):
        current_path = getattr(current_schema, "__file__", None)
        if current_path and Path(current_path).resolve() == fork_path and _fork_module_is_healthy(current_schema):
            current_schema._ava_fork = True
            import nanobot.config as config_pkg

            config_pkg.schema = current_schema

            try:
                import nanobot.config.loader as loader_mod

                loader_mod.Config = current_schema.Config
            except Exception:
                pass

            logger.info("Reused existing ava fork for nanobot.config.schema")
            return "nanobot.config.schema already points to ava fork (reused existing module)"

    try:
        import importlib
        import importlib.util

        if not fork_path.exists():
            return f"Fork schema not found at {fork_path} — skipped"

        spec = importlib.util.spec_from_file_location("nanobot.config.schema", fork_path)
        fork_mod = importlib.util.module_from_spec(spec)
        fork_mod._ava_fork = True  # marker
        original_schema = sys.modules.get("nanobot.config.schema")
        fork_mod._ava_upstream_schema = original_schema

        # 先注册 fork 模块，再执行文件；这样 Pydantic 在解析前向引用时会绑定当前 fork，
        # 不会把同名类型错误解析回上游 schema。
        sys.modules["nanobot.config.schema"] = fork_mod

        try:
            spec.loader.exec_module(fork_mod)
        except Exception:
            if original_schema is not None:
                sys.modules["nanobot.config.schema"] = original_schema
            else:
                sys.modules.pop("nanobot.config.schema", None)
            raise

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
        return "nanobot.config.schema replaced with inherited ava fork (sidecar config extensions enabled)"

    except Exception as exc:
        logger.error("Failed to apply schema_patch: {}", exc)
        return f"schema_patch FAILED: {exc}"


register_patch("config_schema_fork", apply_schema_patch)
