"""Gateway control routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ava.console import auth
from ava.console.models import GatewayRestartRequest, UserInfo
from ava.console.middleware import get_client_ip

router = APIRouter(prefix="/api/gateway", tags=["gateway"])


@router.get("/status")
async def gateway_status(user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer"))):
    from ava.console.app import get_services
    return get_services().gateway.get_status()


@router.post("/restart")
async def gateway_restart(
    body: GatewayRestartRequest,
    request: Request,
    user: UserInfo = Depends(auth.require_role("admin")),
):
    from ava.console.app import get_services

    svc = get_services()
    svc.audit.log(
        user=user.username, role=user.role, action="gateway.restart",
        target="gateway", detail={"delay_ms": body.delay_ms, "force": body.force},
        ip=get_client_ip(request),
    )
    return await svc.gateway.restart(delay_ms=body.delay_ms, force=body.force)
