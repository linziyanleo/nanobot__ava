"""Pydantic models for Console API requests and responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class UserInfo(BaseModel):
    username: str
    role: Literal["admin", "editor", "viewer"]
    created_at: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: Literal["admin", "editor", "viewer"] = "viewer"


class UserUpdateRequest(BaseModel):
    password: str | None = None
    role: Literal["admin", "editor", "viewer"] | None = None


class FileNode(BaseModel):
    name: str
    path: str
    type: Literal["file", "directory"]
    children: list[FileNode] | None = None


class FileContent(BaseModel):
    path: str
    content: str
    mtime: float


class FileWriteRequest(BaseModel):
    path: str
    content: str
    expected_mtime: float


class ConfigUpdateRequest(BaseModel):
    content: str
    mtime: float


class RevealRequest(BaseModel):
    field_path: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: str


class ChatSessionInfo(BaseModel):
    session_id: str
    title: str
    created_at: str
    message_count: int


class ChatSessionCreateRequest(BaseModel):
    title: str = ""


class AuditEntry(BaseModel):
    ts: str
    user: str
    role: str
    action: str
    target: str
    detail: dict | None = None
    ip: str = ""


class AuditQueryResponse(BaseModel):
    entries: list[AuditEntry]
    total: int
    page: int
    size: int


class MediaRecord(BaseModel):
    id: str
    timestamp: str
    prompt: str
    reference_image: str | None = None
    output_images: list[str] = Field(default_factory=list)
    output_text: str = ""
    model: str = ""
    status: str = "success"
    error: str | None = None


class MediaListResponse(BaseModel):
    records: list[MediaRecord]
    total: int
    page: int
    size: int


class GatewayStatus(BaseModel):
    running: bool
    pid: int | None = None
    uptime_seconds: float | None = None
    gateway_port: int | None = None
    console_port: int | None = None


class GatewayRestartRequest(BaseModel):
    delay_ms: int = 5000
    force: bool = False
