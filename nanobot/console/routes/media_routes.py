"""Media gallery routes: image generation records and file serving."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from nanobot.console import auth
from nanobot.console.models import UserInfo

router = APIRouter(prefix="/api/media", tags=["media"])


def _get_media_service():
    from nanobot.console.app import get_services
    return get_services().media


@router.get("/records")
async def list_records(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    return _get_media_service().query(page=page, size=size, search=search)


@router.get("/images/{filename}")
async def get_image(
    filename: str,
    token: str | None = Query(None),
    user: UserInfo | None = Depends(auth.optional_user),
):
    """Serve generated image files. Accepts auth via header or ?token= query param."""
    if user is None and token:
        auth.verify_token(token)
    elif user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    path = _get_media_service().get_image_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(path), media_type="image/png")
