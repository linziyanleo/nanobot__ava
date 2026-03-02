"""File management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Query

from nanobot.console import auth
from nanobot.console.models import FileWriteRequest, UserInfo
from nanobot.console.middleware import get_client_ip

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/tree")
async def get_tree(
    root: str = Query("workspace", description="Root: 'workspace' or 'nanobot'"),
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    from nanobot.console.app import get_services
    try:
        return get_services().files.get_file_tree(root)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/read")
async def read_file(
    path: str = Query(..., description="File path"),
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    from nanobot.console.app import get_services
    try:
        return get_services().files.read_file(path)
    except (FileNotFoundError, PermissionError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/write")
async def write_file(
    body: FileWriteRequest,
    request: Request,
    user: UserInfo = Depends(auth.require_role("admin", "editor")),
):
    from nanobot.console.app import get_services

    svc = get_services()
    try:
        result = svc.files.write_file(body.path, body.content, body.expected_mtime)
    except (PermissionError, ValueError) as e:
        raise HTTPException(status_code=409 if "modified" in str(e).lower() else 403, detail=str(e))

    svc.audit.log(
        user=user.username, role=user.role, action="file.update",
        target=body.path, ip=get_client_ip(request),
    )
    return result
