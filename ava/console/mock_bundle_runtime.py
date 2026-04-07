"""Repo-backed mock bundle bootstrap for console mock_tester."""

from __future__ import annotations

import base64
import json
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ava.storage.database import Database

LOCAL_ADMIN_USERNAME = "nanobot"
MOCK_TESTER_USERNAME = "mock_tester"
LOCAL_ADMIN_PASSWORD_FILE = "nanobot_password"
MOCK_TESTER_PASSWORD_FILE = "mock_tester_password"
LOCAL_SECRETS_DIRNAME = "local-secrets"
MOCK_DATA_DIRNAME = "mock_data"
MOCK_DB_FILENAME = "mock.nanobot.db"
DEFAULT_CONSOLE_SECRET = "change-me-in-production-use-a-longer-key!"


@dataclass
class LocalAccountInfo:
    username: str
    role: str
    password_file: Path


@dataclass
class MockBundleRuntime:
    root: Path
    workspace: Path
    media_dir: Path
    db_path: Path
    template_dir: Path


class MockGatewayService:
    """Static gateway state for mock_tester."""

    def __init__(self, console_port: int) -> None:
        self._console_port = console_port

    def get_status(self) -> dict[str, Any]:
        return {
            "running": True,
            "pid": 4242,
            "uptime_seconds": 7322,
            "gateway_port": 18790,
            "console_port": self._console_port,
            "supervised": True,
            "supervisor": "mock-runtime",
            "restart_pending": False,
            "boot_generation": 7,
            "last_exit_reason": None,
        }

    def health(self) -> dict[str, Any]:
        return {"ok": True, "mode": "mock"}


def bundle_template_dir() -> Path:
    return Path(__file__).parent / "mock_bundle"


def local_secrets_dir(console_dir: Path) -> Path:
    return console_dir / LOCAL_SECRETS_DIRNAME


def mock_runtime_dir(console_dir: Path) -> Path:
    return console_dir / MOCK_DATA_DIRNAME


def ensure_local_accounts(users, console_dir: Path) -> dict[str, LocalAccountInfo]:
    secrets_dir = local_secrets_dir(console_dir)
    secrets_dir.mkdir(parents=True, exist_ok=True)
    _best_effort_private_dir(secrets_dir)

    admin = _ensure_local_account(
        users=users,
        secrets_dir=secrets_dir,
        username=LOCAL_ADMIN_USERNAME,
        role="admin",
        password_filename=LOCAL_ADMIN_PASSWORD_FILE,
    )
    mock = _ensure_local_account(
        users=users,
        secrets_dir=secrets_dir,
        username=MOCK_TESTER_USERNAME,
        role="mock_tester",
        password_filename=MOCK_TESTER_PASSWORD_FILE,
    )
    return {
        admin.username: admin,
        mock.username: mock,
    }


def validate_console_security(console_cfg: Any, console_host: str) -> None:
    if not bool(getattr(console_cfg, "public_dev", False)):
        return

    secret_key = str(getattr(console_cfg, "secret_key", "") or "")
    if secret_key == DEFAULT_CONSOLE_SECRET or len(secret_key) < 32:
        raise RuntimeError("gateway.console.public_dev=true requires a strong secretKey")

    expire_minutes = int(getattr(console_cfg, "token_expire_minutes", 0) or 0)
    if expire_minutes <= 0 or expire_minutes > 60:
        raise RuntimeError("gateway.console.public_dev=true requires tokenExpireMinutes <= 60")

    if console_host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("gateway.console.public_dev=true only allows localhost origin binding")

    if not bool(getattr(console_cfg, "session_cookie_secure", False)):
        raise RuntimeError("gateway.console.public_dev=true requires secure session cookie")

    if not str(getattr(console_cfg, "cloudflare_access_team_domain", "") or "").strip():
        raise RuntimeError("gateway.console.public_dev=true requires cloudflareAccessTeamDomain")

    if not str(getattr(console_cfg, "cloudflare_access_audience", "") or "").strip():
        raise RuntimeError("gateway.console.public_dev=true requires cloudflareAccessAudience")


def prepare_mock_runtime(console_dir: Path, console_port: int) -> MockBundleRuntime:
    template_dir = bundle_template_dir()
    runtime_root = mock_runtime_dir(console_dir)
    runtime_root.mkdir(parents=True, exist_ok=True)
    _sync_template_tree(template_dir, runtime_root)

    media_dir = runtime_root / "media" / "generated"
    media_dir.mkdir(parents=True, exist_ok=True)
    db_path = runtime_root / MOCK_DB_FILENAME

    _seed_media_assets(media_dir)
    db = Database(db_path)
    _seed_mock_db(db, console_port=console_port, media_dir=media_dir)

    return MockBundleRuntime(
        root=runtime_root,
        workspace=runtime_root / "workspace",
        media_dir=media_dir,
        db_path=db_path,
        template_dir=template_dir,
    )


def _ensure_local_account(
    *,
    users,
    secrets_dir: Path,
    username: str,
    role: str,
    password_filename: str,
) -> LocalAccountInfo:
    password_file = secrets_dir / password_filename
    password = _ensure_password_file(password_file)

    existing = users.get_user(username)
    if existing is None:
        users.create_user(username, password, role)
    else:
        password_matches = users.verify_password(username, password) is not None
        needs_role = existing.role != role
        if not password_matches or needs_role:
            users.update_user(
                username,
                password=password if not password_matches else None,
                role=role if needs_role else None,
            )

    return LocalAccountInfo(username=username, role=role, password_file=password_file)


def _ensure_password_file(path: Path) -> str:
    if path.exists():
        password = path.read_text("utf-8").strip()
        if password:
            return password

    password = secrets.token_urlsafe(24)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(password + "\n", "utf-8")
    _best_effort_private_file(path)
    return password


def _best_effort_private_dir(path: Path) -> None:
    try:
        path.chmod(0o700)
    except OSError:
        pass


def _best_effort_private_file(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _sync_template_tree(template_dir: Path, runtime_root: Path) -> None:
    if not template_dir.is_dir():
        raise RuntimeError(f"Mock bundle template not found: {template_dir}")

    for source in template_dir.rglob("*"):
        relative = source.relative_to(template_dir)
        target = runtime_root / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)


def _seed_media_assets(media_dir: Path) -> None:
    seed = _load_mock_seed()
    for asset in seed.get("media_assets", []):
        name = str(asset.get("name", "")).strip()
        encoded = str(asset.get("content_base64", "")).strip()
        if not name or not encoded:
            continue
        path = media_dir / name
        if path.exists():
            continue
        path.write_bytes(base64.b64decode(encoded))


def _seed_mock_db(db: Database, *, console_port: int, media_dir: Path) -> None:
    seed = _load_mock_seed()
    media_rows = seed.get("media_records", [])
    if _table_count(db, "media_records") == 0:
        for row in media_rows:
            db.execute(
                """INSERT INTO media_records
                   (id, timestamp, prompt, reference_image, output_images, output_text, model, status, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["id"],
                    row["timestamp"],
                    row["prompt"],
                    row.get("reference_image"),
                    json.dumps(row.get("output_images", []), ensure_ascii=False),
                    row.get("output_text", ""),
                    row.get("model", ""),
                    row.get("status", "success"),
                    row.get("error"),
                ),
            )

    if _table_count(db, "audit_entries") == 0:
        for row in seed.get("audit_entries", []):
            db.execute(
                """INSERT INTO audit_entries
                   (timestamp, user, role, action, target, detail, ip)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["timestamp"],
                    row["user"],
                    row["role"],
                    row["action"],
                    row["target"],
                    json.dumps(row.get("detail"), ensure_ascii=False) if row.get("detail") else None,
                    row.get("ip", ""),
                ),
            )

    if _table_count(db, "sessions") == 0:
        for session in seed.get("sessions", []):
            db.execute(
                """INSERT INTO sessions
                   (key, created_at, updated_at, metadata, last_consolidated, last_completed, token_stats)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session["key"],
                    session["created_at"],
                    session["updated_at"],
                    json.dumps(session.get("metadata", {}), ensure_ascii=False),
                    session.get("last_consolidated", 0),
                    session.get("last_completed"),
                    json.dumps(session.get("token_stats", {}), ensure_ascii=False),
                ),
            )
        db.commit()
        for msg in seed.get("session_messages", []):
            session_row = db.fetchone("SELECT id FROM sessions WHERE key = ?", (msg["session_key"],))
            if not session_row:
                continue
            db.execute(
                """INSERT INTO session_messages
                   (session_id, seq, conversation_id, role, content, tool_calls, tool_call_id, name, reasoning_content, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_row["id"],
                    msg["seq"],
                    msg.get("conversation_id", ""),
                    msg["role"],
                    msg.get("content", ""),
                    json.dumps(msg.get("tool_calls"), ensure_ascii=False) if msg.get("tool_calls") else None,
                    msg.get("tool_call_id"),
                    msg.get("name"),
                    msg.get("reasoning_content"),
                    msg.get("timestamp"),
                ),
            )

    if _table_count(db, "token_usage") == 0:
        for row in seed.get("token_usage", []):
            db.execute(
                """INSERT INTO token_usage
                   (timestamp, model, provider, prompt_tokens, completion_tokens, total_tokens,
                    session_key, conversation_id, turn_seq, iteration, user_message, output_content,
                    system_prompt_preview, conversation_history, full_request_payload, finish_reason,
                    model_role, cached_tokens, cache_creation_tokens, cost_usd, current_turn_tokens, tool_names)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["timestamp"],
                    row["model"],
                    row["provider"],
                    row["prompt_tokens"],
                    row["completion_tokens"],
                    row["total_tokens"],
                    row.get("session_key", ""),
                    row.get("conversation_id", ""),
                    row.get("turn_seq"),
                    row.get("iteration", 0),
                    row.get("user_message", ""),
                    row.get("output_content", ""),
                    row.get("system_prompt_preview", ""),
                    row.get("conversation_history", ""),
                    row.get("full_request_payload", ""),
                    row.get("finish_reason", ""),
                    row.get("model_role", "default"),
                    row.get("cached_tokens", 0),
                    row.get("cache_creation_tokens", 0),
                    row.get("cost_usd", 0.0),
                    row.get("current_turn_tokens", 0),
                    row.get("tool_names", ""),
                ),
            )

    if _table_count(db, "skill_config") == 0:
        for row in seed.get("skill_config", []):
            db.execute(
                """INSERT INTO skill_config
                   (name, source, enabled, installed_at, install_method, git_url, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["name"],
                    row.get("source", "ava"),
                    int(row.get("enabled", 1)),
                    row.get("installed_at"),
                    row.get("install_method"),
                    row.get("git_url"),
                    row.get("updated_at"),
                ),
            )

    db.commit()

    version_row = db.fetchone("SELECT version FROM schema_version LIMIT 1")
    if version_row is None:
        db.execute("INSERT INTO schema_version (version) VALUES (?)", (1,))
        db.commit()

    status_file = media_dir.parent.parent / "gateway_status.json"
    if not status_file.exists():
        status_file.write_text(
            json.dumps(
                {
                    "running": True,
                    "consolePort": console_port,
                    "supervisor": "mock-runtime",
                },
                indent=2,
                ensure_ascii=False,
            ),
            "utf-8",
        )


def _table_count(db: Database, table: str) -> int:
    row = db.fetchone(f"SELECT COUNT(*) as cnt FROM {table}")
    return int(row["cnt"]) if row else 0


def _load_mock_seed() -> dict[str, Any]:
    path = bundle_template_dir() / "mock_seed.json"
    return json.loads(path.read_text("utf-8"))
