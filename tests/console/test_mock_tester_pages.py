from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from ava.console.app import create_console_app
from ava.console.mock_bundle_runtime import MOCK_TESTER_PASSWORD_FILE


def _build_config() -> SimpleNamespace:
    return SimpleNamespace(
        gateway=SimpleNamespace(
            port=18790,
            console=SimpleNamespace(
                port=6688,
                secret_key="x" * 48,
                token_expire_minutes=60,
                session_cookie_name="ava_console_session",
                session_cookie_secure=False,
                session_cookie_samesite="lax",
            ),
        ),
    )


def _create_client(tmp_path, monkeypatch) -> tuple[TestClient, object]:
    monkeypatch.setattr("ava.console.app.prepare_console_ui_dist", lambda: None)

    nanobot_dir = tmp_path / "nanobot-home"
    workspace = tmp_path / "workspace"
    nanobot_dir.mkdir()
    workspace.mkdir()

    agent_loop = SimpleNamespace(lifecycle_manager=None)
    app = create_console_app(
        nanobot_dir=nanobot_dir,
        workspace=workspace,
        agent_loop=agent_loop,
        config=_build_config(),
        token_stats_collector=None,
        db=None,
    )
    return TestClient(app), nanobot_dir


def _login_mock_tester(client: TestClient, nanobot_dir) -> None:
    password = (nanobot_dir / "console" / "local-secrets" / MOCK_TESTER_PASSWORD_FILE).read_text("utf-8").strip()
    response = client.post(
        "/api/auth/login",
        json={"username": "mock_tester", "password": password},
    )
    assert response.status_code == 200


def test_mock_tester_can_open_mock_safe_console_pages(tmp_path, monkeypatch):
    client, nanobot_dir = _create_client(tmp_path, monkeypatch)
    _login_mock_tester(client, nanobot_dir)

    sessions = client.get("/api/chat/sessions")
    assert sessions.status_code == 200
    assert any(item["key"] == "console:mock-session-1" for item in sessions.json())

    conversations = client.get(
        "/api/chat/conversations",
        params={"session_key": "console:mock-session-1"},
    )
    assert conversations.status_code == 200
    assert conversations.json()[0]["conversation_id"] == "mock-conv-1"

    messages = client.get(
        "/api/chat/messages",
        params={"session_key": "console:mock-session-1"},
    )
    assert messages.status_code == 200
    assert messages.json()[0]["content"] == "Please review the mock dashboard layout."

    bg_tasks = client.get("/api/bg-tasks", params={"include_finished": "false"})
    assert bg_tasks.status_code == 200
    assert bg_tasks.json()["tasks"] == []

    skills = client.get("/api/skills/list")
    assert skills.status_code == 200
    assert isinstance(skills.json()["skills"], list)

    tools = client.get("/api/skills/tools")
    assert tools.status_code == 200
    assert isinstance(tools.json()["tools"], list)

    persona = client.get("/api/files/read", params={"path": "workspace/AGENTS.md"})
    assert persona.status_code == 200
    assert persona.json()["path"] == "workspace/AGENTS.md"


def test_mock_tester_can_manage_mock_chat_sessions_but_not_mutate_real_skill_registry(tmp_path, monkeypatch):
    client, nanobot_dir = _create_client(tmp_path, monkeypatch)
    _login_mock_tester(client, nanobot_dir)

    created = client.post("/api/chat/sessions", json={"title": "Mock smoke"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    sessions = client.get("/api/chat/sessions")
    assert any(item["key"] == f"console:{session_id}" for item in sessions.json())

    deleted = client.delete(f"/api/chat/sessions/{session_id}")
    assert deleted.status_code == 200

    toggle = client.put(
        "/api/skills/toggle",
        json={"name": "console_ui_regression", "enabled": False},
    )
    assert toggle.status_code == 403
