"""FastAPI application factory and service container."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from ava.console import auth
from ava.console.middleware import setup_cors
from ava.console.services.audit_service import AuditService
from ava.console.services.chat_service import ChatService
from ava.console.services.config_service import ConfigService
from ava.console.services.file_service import FileService
from ava.console.services.gateway_service import GatewayService
from ava.console.services.media_service import MediaService
from ava.console.services.skills_service import SkillsService
from ava.console.services.token_stats_service import TokenStatsCollector
from ava.console.services.user_service import UserService


@dataclass
class Services:
    users: UserService
    audit: AuditService
    config: ConfigService
    files: FileService
    gateway: GatewayService
    media: MediaService
    skills: SkillsService
    chat: ChatService | None = None
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
    db=None,
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
        audit=AuditService(console_dir, db=db),
        config=ConfigService(nanobot_dir),
        files=FileService(workspace, nanobot_dir),
        gateway=GatewayService(
            skill_dir,
            gateway_port=config.gateway.port,
            console_port=console_cfg.port,
        ),
        media=MediaService(db=db),
        skills=SkillsService(workspace, skill_dir, nanobot_dir, db=db),
        chat=ChatService(agent_loop, workspace, db=db),
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

    from ava.console.routes import (
        auth_routes,
        config_routes,
        file_routes,
        gateway_routes,
        chat_routes,
        media_routes,
        user_routes,
        audit_routes,
        token_routes,
        skills_routes,
        page_agent_routes,
    )

    app.include_router(auth_routes.router)
    app.include_router(config_routes.router)
    app.include_router(file_routes.router)
    app.include_router(gateway_routes.router)
    app.include_router(chat_routes.router)
    app.include_router(media_routes.router)
    app.include_router(user_routes.router)
    app.include_router(audit_routes.router)
    app.include_router(token_routes.router)
    app.include_router(skills_routes.router)
    app.include_router(page_agent_routes.router)

    static_dir = Path(__file__).parent.parent.parent / "console-ui" / "dist"
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


def create_console_app_standalone(
    nanobot_dir: Path,
    workspace: Path,
    gateway_port: int = 18790,
    console_port: int = 6688,
    secret_key: str = "change-me-in-production",
    expire_minutes: int = 480,
    token_stats_dir: str = "",
) -> FastAPI:
    """Create a console app that runs independently from the gateway process.

    This variant does not require a live AgentLoop — ChatService is set to None,
    and TokenStatsCollector reads from the shared SQLite DB (or JSON file fallback).
    """
    global _services

    console_dir = nanobot_dir / "console"
    console_dir.mkdir(parents=True, exist_ok=True)

    auth.configure(secret_key=secret_key, expire_minutes=expire_minutes)

    skill_dir = Path(__file__).parent.parent / "skills"

    users = UserService(console_dir)
    users.ensure_default_admin()

    db_path = nanobot_dir / "nanobot.db"
    from ava.storage import Database
    db = Database(db_path)

    token_stats = None
    if token_stats_dir:
        token_stats = TokenStatsCollector(data_dir=Path(token_stats_dir), db=db)

    _services = Services(
        users=users,
        audit=AuditService(console_dir, db=db),
        config=ConfigService(nanobot_dir),
        files=FileService(workspace, nanobot_dir),
        gateway=GatewayService(
            skill_dir,
            gateway_port=gateway_port,
            console_port=console_port,
        ),
        media=MediaService(db=db),
        skills=SkillsService(workspace, skill_dir, nanobot_dir, db=db),
        chat=None,  # type: ignore[arg-type]
        token_stats=token_stats,
    )

    app = FastAPI(
        title="Nanobot Console",
        description="Web management console for Nanobot (standalone)",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    setup_cors(app)

    from ava.console.routes import (
        auth_routes,
        config_routes,
        file_routes,
        gateway_routes,
        media_routes,
        user_routes,
        audit_routes,
        token_routes,
        skills_routes,
    )

    app.include_router(auth_routes.router)
    app.include_router(config_routes.router)
    app.include_router(file_routes.router)
    app.include_router(gateway_routes.router)
    app.include_router(media_routes.router)
    app.include_router(user_routes.router)
    app.include_router(audit_routes.router)
    app.include_router(token_routes.router)
    app.include_router(skills_routes.router)

    # --- Chat reverse proxy to gateway ----------------------------------
    gateway_base = f"http://127.0.0.1:{gateway_port}"

    @app.api_route(
        "/api/chat/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    )
    async def proxy_chat_http(request: Request, path: str):
        import httpx
        target = f"{gateway_base}/api/chat/{path}"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        body = await request.body()
        try:
            # trust_env=False to ignore system proxy settings (e.g. Clash on port 7897)
            async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
                resp = await client.request(
                    method=request.method,
                    url=target,
                    headers={
                        k: v for k, v in request.headers.items()
                        if k.lower() not in ("host", "content-length")
                    },
                    content=body,
                )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
            )
        except httpx.ConnectError:
            return Response(
                content='{"detail":"Gateway offline — chat unavailable"}',
                status_code=503,
                media_type="application/json",
            )

    @app.websocket("/api/chat/ws/{session_id}")
    async def proxy_chat_ws(websocket: WebSocket, session_id: str):
        import websockets.asyncio.client as ws_client

        await websocket.accept()
        token = websocket.query_params.get("token", "")
        gw_ws_url = (
            f"ws://127.0.0.1:{gateway_port}"
            f"/api/chat/ws/{session_id}?token={token}"
        )
        try:
            async with ws_client.connect(gw_ws_url) as upstream:

                async def client_to_upstream():
                    try:
                        while True:
                            data = await websocket.receive_text()
                            await upstream.send(data)
                    except WebSocketDisconnect:
                        await upstream.close()

                async def upstream_to_client():
                    try:
                        async for msg in upstream:
                            await websocket.send_text(msg if isinstance(msg, str) else msg.decode())
                    except Exception:
                        pass

                await asyncio.gather(client_to_upstream(), upstream_to_client())
        except Exception:
            try:
                await websocket.close(code=1011, reason="Gateway unreachable")
            except Exception:
                pass

    # --- End chat proxy -------------------------------------------------

    static_dir = Path(__file__).parent.parent.parent / "console-ui" / "dist"
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
