"""Configuration loading utilities."""

import json
import os
import re
from pathlib import Path

import pydantic
from loguru import logger

from nanobot.config.schema import Config

# Global variable to store current config path (for multi-instance support)
_current_config_path: Path | None = None

EXTRA_CONFIG_FILENAME = "extra_config.json"


def set_config_path(path: Path) -> None:
    """Set the current config path (used to derive data directory)."""
    global _current_config_path
    _current_config_path = path


def get_config_path() -> Path:
    """Get the configuration file path."""
    if _current_config_path:
        return _current_config_path
    return Path.home() / ".nanobot" / "config.json"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override values take precedence.

    - Dicts are merged recursively
    - Non-dict values in override replace base values
    - Keys only in base are preserved
    """
    merged = base.copy()
    for key, val in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file or create default.

    Loads config.json as the base config, then deep-merges extra_config.json
    (if it exists in the same directory) on top. extra_config.json values
    take precedence over config.json values.

    Args:
        config_path: Optional path to config file. Uses default if not provided.

    Returns:
        Loaded configuration object.
    """
    path = config_path or get_config_path()

    config = Config()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            data = _migrate_config(data)

            extra_path = path.parent / EXTRA_CONFIG_FILENAME
            if extra_path.exists():
                try:
                    with open(extra_path, encoding="utf-8") as f:
                        extra_data = json.load(f)
                    data = _deep_merge(data, extra_data)
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"Warning: Failed to load extra config from {extra_path}: {e}")

            config = Config.model_validate(data)
        except (json.JSONDecodeError, ValueError, pydantic.ValidationError) as e:
            logger.warning(f"Failed to load config from {path}: {e}")
            logger.warning("Using default configuration.")

    _apply_ssrf_whitelist(config)
    return config


def _apply_ssrf_whitelist(config: Config) -> None:
    """Apply SSRF whitelist from config to the network security module."""
    from nanobot.security.network import configure_ssrf_whitelist

    configure_ssrf_whitelist(config.tools.ssrf_whitelist)


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    Save configuration to file.

    Args:
        config: Configuration to save.
        config_path: Optional path to save to. Uses default if not provided.
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(mode="json", by_alias=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def resolve_config_env_vars(config: Config) -> Config:
    """Return a copy of *config* with ``${VAR}`` env-var references resolved.

    Only string values are affected; other types pass through unchanged.
    Raises :class:`ValueError` if a referenced variable is not set.
    """
    data = config.model_dump(mode="json", by_alias=True)
    data = _resolve_env_vars(data)
    return Config.model_validate(data)


def _resolve_env_vars(obj: object) -> object:
    """Recursively resolve ``${VAR}`` patterns in string values."""
    if isinstance(obj, str):
        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", _env_replace, obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars(v) for v in obj]
    return obj


def _env_replace(match: re.Match[str]) -> str:
    name = match.group(1)
    value = os.environ.get(name)
    if value is None:
        raise ValueError(
            f"Environment variable '{name}' referenced in config is not set"
        )
    return value


def _migrate_config(data: dict) -> dict:
    """Migrate old config formats to current."""
    # Move tools.exec.restrictToWorkspace → tools.restrictToWorkspace
    tools = data.get("tools", {})
    exec_cfg = tools.get("exec", {})
    if "restrictToWorkspace" in exec_cfg and "restrictToWorkspace" not in tools:
        tools["restrictToWorkspace"] = exec_cfg.pop("restrictToWorkspace")

    # Move gateway.heartbeat → agents.defaults.heartbeat
    gateway = data.get("gateway", {})
    if "heartbeat" in gateway:
        agents = data.setdefault("agents", {})
        defaults = agents.setdefault("defaults", {})
        if "heartbeat" not in defaults:
            defaults["heartbeat"] = gateway.pop("heartbeat")
        else:
            gateway.pop("heartbeat")

    return data
