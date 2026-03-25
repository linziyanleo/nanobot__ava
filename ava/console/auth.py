"""JWT authentication and role-based access control."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, status, WebSocket, WebSocketException
from fastapi.security import OAuth2PasswordBearer

from ava.console.models import UserInfo

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=True)

_secret_key: str = "change-me"
_algorithm: str = "HS256"
_expire_minutes: int = 480


def configure(secret_key: str, expire_minutes: int = 480) -> None:
    global _secret_key, _expire_minutes
    _secret_key = secret_key
    _expire_minutes = expire_minutes


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=_expire_minutes))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, _secret_key, algorithm=_algorithm)


def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret_key, algorithms=[_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInfo:
    payload = verify_token(token)
    username = payload.get("sub")
    role = payload.get("role")
    created_at = payload.get("created_at", "")
    if not username or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return UserInfo(username=username, role=role, created_at=created_at)


async def get_ws_user(websocket: WebSocket) -> UserInfo:
    """Extract user from WebSocket query parameter `token`."""
    token = websocket.query_params.get("token")
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    payload = verify_token(token)
    username = payload.get("sub")
    role = payload.get("role")
    created_at = payload.get("created_at", "")
    if not username or not role:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return UserInfo(username=username, role=role, created_at=created_at)


async def optional_user(token: str = Depends(OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False))) -> UserInfo | None:
    """Return user if valid token is present, None otherwise."""
    if not token:
        return None
    try:
        payload = verify_token(token)
        username = payload.get("sub")
        role = payload.get("role")
        created_at = payload.get("created_at", "")
        if not username or not role:
            return None
        return UserInfo(username=username, role=role, created_at=created_at)
    except HTTPException:
        return None


def require_role(*allowed_roles: str) -> Callable:
    """Dependency that checks if current user has one of the allowed roles."""

    async def checker(user: UserInfo = Depends(get_current_user)) -> UserInfo:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not allowed. Required: {', '.join(allowed_roles)}",
            )
        return user

    return checker
