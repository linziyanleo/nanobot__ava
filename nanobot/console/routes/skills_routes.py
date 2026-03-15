"""Skills and tools management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from nanobot.console import auth
from nanobot.console.models import UserInfo
from nanobot.console.middleware import get_client_ip

router = APIRouter(prefix="/api/skills", tags=["skills"])


class InstallGitRequest(BaseModel):
    git_url: str
    name: str | None = None


class InstallPathRequest(BaseModel):
    source_path: str
    name: str | None = None


class DeleteSkillRequest(BaseModel):
    name: str


@router.get("/tools")
async def list_tools(
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    """List all built-in tools."""
    from nanobot.console.app import get_services
    return {"tools": get_services().skills.list_tools()}


@router.get("/list")
async def list_skills(
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    """List all skills (builtin + workspace)."""
    from nanobot.console.app import get_services
    return {"skills": get_services().skills.list_skills()}


@router.get("/detail/{name}")
async def get_skill(
    name: str,
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    """Get skill details."""
    from nanobot.console.app import get_services
    skill = get_services().skills.get_skill(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return skill


@router.post("/install/git")
async def install_from_git(
    body: InstallGitRequest,
    request: Request,
    user: UserInfo = Depends(auth.require_role("admin", "editor")),
):
    """Install a skill from a Git repository."""
    from nanobot.console.app import get_services
    svc = get_services()
    
    try:
        result = svc.skills.install_skill_from_git(body.git_url, body.name)
        svc.audit.log(
            user=user.username, role=user.role, action="skill.install",
            target=f"git:{body.git_url}", ip=get_client_ip(request),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/install/path")
async def install_from_path(
    body: InstallPathRequest,
    request: Request,
    user: UserInfo = Depends(auth.require_role("admin", "editor")),
):
    """Install a skill from a local path."""
    from nanobot.console.app import get_services
    svc = get_services()
    
    try:
        result = svc.skills.install_skill_from_path(body.source_path, body.name)
        svc.audit.log(
            user=user.username, role=user.role, action="skill.install",
            target=f"path:{body.source_path}", ip=get_client_ip(request),
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete")
async def delete_skill(
    body: DeleteSkillRequest,
    request: Request,
    user: UserInfo = Depends(auth.require_role("admin")),
):
    """Delete a workspace skill."""
    from nanobot.console.app import get_services
    svc = get_services()
    
    try:
        result = svc.skills.delete_skill(body.name)
        svc.audit.log(
            user=user.username, role=user.role, action="skill.delete",
            target=body.name, ip=get_client_ip(request),
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
