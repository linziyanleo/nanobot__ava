"""Authentication routes: login, refresh, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from cafeext.console import auth
from cafeext.console.models import LoginRequest, LoginResponse, UserInfo
from cafeext.console.middleware import get_client_ip

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request):
    from cafeext.console.app import get_services

    svc = get_services()
    user = svc.users.verify_password(body.username, body.password)
    if not user:
        svc.audit.log(
            user=body.username, role="unknown", action="auth.login_failed",
            target="", ip=get_client_ip(request),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = auth.create_access_token({"sub": user.username, "role": user.role, "created_at": user.created_at})
    svc.audit.log(
        user=user.username, role=user.role, action="auth.login",
        target="", ip=get_client_ip(request),
    )
    return LoginResponse(access_token=token, user=user)


@router.post("/refresh", response_model=LoginResponse)
async def refresh(user: UserInfo = Depends(auth.get_current_user)):
    token = auth.create_access_token({"sub": user.username, "role": user.role, "created_at": user.created_at})
    return LoginResponse(access_token=token, user=user)


@router.get("/me", response_model=UserInfo)
async def me(user: UserInfo = Depends(auth.get_current_user)):
    return user
