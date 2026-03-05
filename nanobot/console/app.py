"""FastAPI application factory and service container."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from nanobot.console import auth
from nanobot.console.middleware import setup_cors
from nanobot.console.services.audit_service import AuditService
from nanobot.console.services.chat_service import ChatService
from nanobot.console.services.config_service import ConfigService
from nanobot.console.services.file_service import FileService
from nanobot.console.services.gateway_service import GatewayService
from nanobot.console.services.token_stats_service import TokenStatsCollector
from nanobot.console.services.user_service import UserService


@dataclass
class Services:
    users: UserService
    audit: AuditService
    config: ConfigService
    files: FileService
    gateway: GatewayService
    chat: ChatService
    token_stats: TokenStatsCollector | None = None


_services: Services | None = None


def get_services() -> Services:
    if _services is None:
        raise RuntimeError("Console services not initialized")
    return _services


def create_console_app(
    nanobot_dir: Path,
    workspace: Path,
    agent_loop,
    config,
    token_stats_collector: TokenStatsCollector | None = None,
) -> FastAPI:
    global _services

    console_dir = nanobot_dir / "console"
    console_dir.mkdir(parents=True, exist_ok=True)

    console_cfg = config.gateway.console
    auth.configure(
        secret_key=console_cfg.secret_key,
        expire_minutes=console_cfg.token_expire_minutes,
    )

    skill_dir = Path(__file__).parent.parent / "skills"

    users = UserService(console_dir)
    users.ensure_default_admin()

    _services = Services(
        users=users,
        audit=AuditService(console_dir),
        config=ConfigService(nanobot_dir),
        files=FileService(workspace, nanobot_dir),
        gateway=GatewayService(skill_dir),
        chat=ChatService(agent_loop, workspace),
        token_stats=token_stats_collector,
    )

    app = FastAPI(
        title="Nanobot Console",
        description="Web management console for Nanobot",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    setup_cors(app)

    from nanobot.console.routes import (
        auth_routes,
        config_routes,
        file_routes,
        gateway_routes,
        chat_routes,
        user_routes,
        audit_routes,
        token_routes,
    )

    app.include_router(auth_routes.router)
    app.include_router(config_routes.router)
    app.include_router(file_routes.router)
    app.include_router(gateway_routes.router)
    app.include_router(chat_routes.router)
    app.include_router(user_routes.router)
    app.include_router(audit_routes.router)
    app.include_router(token_routes.router)

    static_dir = Path(__file__).parent.parent / "console-ui" / "dist"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="static-assets")

        index_html = static_dir / "index.html"

        @app.get("/{full_path:path}")
        async def spa_fallback(request: Request, full_path: str):
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(index_html)

    return app
