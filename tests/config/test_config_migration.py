import json
import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

from nanobot.config.loader import load_config, save_config


def _restore_upstream_schema() -> None:
    upstream_path = Path(__file__).parents[2] / "nanobot" / "config" / "schema.py"
    spec = importlib.util.spec_from_file_location("nanobot.config.schema", upstream_path)
    assert spec is not None and spec.loader is not None

    upstream_mod = importlib.util.module_from_spec(spec)
    sys.modules["nanobot.config.schema"] = upstream_mod
    spec.loader.exec_module(upstream_mod)

    import nanobot.config as config_pkg
    import nanobot.config.loader as loader_mod

    config_pkg.schema = upstream_mod
    loader_mod.Config = upstream_mod.Config

    sys.modules.pop("nanobot.cli.commands", None)
    sys.modules.pop("nanobot.cli.onboard", None)


@pytest.fixture(autouse=True)
def _reset_schema_runtime():
    _restore_upstream_schema()
    yield
    _restore_upstream_schema()


def test_load_config_keeps_max_tokens_and_ignores_legacy_memory_window(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "maxTokens": 1234,
                        "memoryWindow": 42,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.agents.defaults.max_tokens == 1234
    assert config.agents.defaults.context_window_tokens == 65_536
    assert not hasattr(config.agents.defaults, "memory_window")


def test_save_config_writes_context_window_tokens_but_not_memory_window(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "maxTokens": 2222,
                        "memoryWindow": 30,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    save_config(config, config_path)
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    defaults = saved["agents"]["defaults"]

    assert defaults["maxTokens"] == 2222
    assert defaults["contextWindowTokens"] == 65_536
    assert "memoryWindow" not in defaults


def test_onboard_does_not_crash_with_legacy_memory_window(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"
    config_path.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "maxTokens": 3333,
                        "memoryWindow": 50,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("nanobot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("nanobot.cli.commands.get_workspace_path", lambda _workspace=None: workspace)

    from typer.testing import CliRunner
    from nanobot.cli.commands import app
    runner = CliRunner()
    result = runner.invoke(app, ["onboard"], input="n\n")

    assert result.exit_code == 0


def test_onboard_refresh_backfills_missing_channel_fields(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"
    config_path.write_text(
        json.dumps(
            {
                "channels": {
                    "qq": {
                        "enabled": False,
                        "appId": "",
                        "secret": "",
                        "allowFrom": [],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("nanobot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("nanobot.cli.commands.get_workspace_path", lambda _workspace=None: workspace)
    monkeypatch.setattr(
        "nanobot.channels.registry.discover_all",
        lambda: {
            "qq": SimpleNamespace(
                default_config=lambda: {
                    "enabled": False,
                    "appId": "",
                    "secret": "",
                    "allowFrom": [],
                    "msgFormat": "plain",
                }
            )
        },
    )

    from typer.testing import CliRunner
    from nanobot.cli.commands import app
    runner = CliRunner()
    result = runner.invoke(app, ["onboard"], input="n\n")

    assert result.exit_code == 0
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["channels"]["qq"]["msgFormat"] == "plain"


def _apply_sidecar_schema_patch() -> None:
    from ava.patches.a_schema_patch import apply_schema_patch

    apply_schema_patch()


def test_sidecar_save_config_preserves_inherited_schema_fields(tmp_path) -> None:
    _apply_sidecar_schema_patch()

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "channels": {
                    "myplugin": {
                        "enabled": True,
                        "token": "abc",
                    }
                },
                "providers": {
                    "mistral": {
                        "apiKey": "mistral-key",
                    }
                },
                "tools": {
                    "web": {
                        "search": {
                            "provider": "searxng",
                            "baseUrl": "https://search.example",
                        }
                    },
                    "mcpServers": {
                        "demo": {
                            "type": "streamableHttp",
                            "url": "https://mcp.example",
                            "enabledTools": ["tool_a"],
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    save_config(config, config_path)
    saved = json.loads(config_path.read_text(encoding="utf-8"))

    assert saved["channels"]["myplugin"]["token"] == "abc"
    assert saved["providers"]["mistral"]["apiKey"] == "mistral-key"
    assert saved["tools"]["web"]["search"]["provider"] == "searxng"
    assert saved["tools"]["web"]["search"]["baseUrl"] == "https://search.example"
    assert saved["tools"]["mcpServers"]["demo"]["type"] == "streamableHttp"
    assert saved["tools"]["mcpServers"]["demo"]["enabledTools"] == ["tool_a"]


def test_sidecar_onboard_refresh_preserves_plugin_channels_and_inherited_fields(tmp_path, monkeypatch) -> None:
    _apply_sidecar_schema_patch()

    import nanobot.cli.commands as commands_mod

    commands_mod = importlib.reload(commands_mod)

    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"
    config_path.write_text(
        json.dumps(
            {
                "channels": {
                    "myplugin": {
                        "enabled": True,
                        "token": "abc",
                    }
                },
                "providers": {
                    "mistral": {
                        "apiKey": "mistral-key",
                    }
                },
                "tools": {
                    "web": {
                        "search": {
                            "provider": "searxng",
                            "baseUrl": "https://search.example",
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("nanobot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("nanobot.cli.commands.get_workspace_path", lambda _workspace=None: workspace)
    monkeypatch.setattr("nanobot.cli.commands.sync_workspace_templates", lambda _workspace: None)
    monkeypatch.setattr("nanobot.channels.registry.discover_all", lambda: {})

    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(commands_mod.app, ["onboard"], input="n\n")

    assert result.exit_code == 0

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["channels"]["myplugin"]["token"] == "abc"
    assert saved["providers"]["mistral"]["apiKey"] == "mistral-key"
    assert saved["tools"]["web"]["search"]["provider"] == "searxng"
    assert saved["tools"]["web"]["search"]["baseUrl"] == "https://search.example"
