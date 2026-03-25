"""Config management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from cafeext.console import auth
from cafeext.console.models import ConfigUpdateRequest, RevealRequest, UserInfo
from cafeext.console.middleware import get_client_ip

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/list")
async def list_configs(user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer"))):
    from cafeext.console.app import get_services
    return get_services().config.list_configs()


@router.get("/{name:path}")
async def read_config(
    name: str,
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    from cafeext.console.app import get_services

    try:
        return get_services().config.read_config(name, mask=(user.role != "admin"))
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{name:path}")
async def update_config(
    name: str,
    body: ConfigUpdateRequest,
    request: Request,
    user: UserInfo = Depends(auth.require_role("admin", "editor")),
):
    from cafeext.console.app import get_services

    svc = get_services()
    try:
        result = svc.config.update_config(name, body.content, body.mtime)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    svc.audit.log(
        user=user.username, role=user.role, action="config.update",
        target=name, ip=get_client_ip(request),
    )
    return result


@router.post("/{name:path}/reveal")
async def reveal_secret(
    name: str,
    body: RevealRequest,
    request: Request,
    user: UserInfo = Depends(auth.require_role("admin")),
):
    from cafeext.console.app import get_services

    svc = get_services()
    value = svc.config.reveal_secret(name, body.field_path)
    if value is None:
        raise HTTPException(status_code=404, detail="Field not found")

    svc.audit.log(
        user=user.username, role=user.role, action="secret.reveal",
        target=name, detail={"field_path": body.field_path},
        ip=get_client_ip(request),
    )
    return {"value": value}
