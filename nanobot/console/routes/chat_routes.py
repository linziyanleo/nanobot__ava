"""Chat routes: WebSocket conversations + session management."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from nanobot.console import auth
from nanobot.console.models import ChatSessionCreateRequest, UserInfo

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/sessions")
async def list_sessions(user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer"))):
    from nanobot.console.app import get_services
    return get_services().chat.list_sessions(user.username)


@router.post("/sessions")
async def create_session(
    body: ChatSessionCreateRequest,
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    from nanobot.console.app import get_services
    sid = get_services().chat.create_session(user.username, body.title)
    return {"session_id": sid}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    from nanobot.console.app import get_services
    if not get_services().chat.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@router.get("/sessions/{session_id}/history")
async def get_history(
    session_id: str,
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    from nanobot.console.app import get_services
    return get_services().chat.get_history(session_id)


@router.websocket("/ws/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str):
    user = await auth.get_ws_user(websocket)
    await websocket.accept()

    from nanobot.console.app import get_services
    svc = get_services()

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                content = msg.get("content", "")
            except json.JSONDecodeError:
                content = data

            if not content:
                continue

            svc.audit.log(
                user=user.username, role=user.role, action="chat.send",
                target=session_id, detail={"preview": content[:100]},
            )

            async def on_progress(chunk: str):
                await websocket.send_json({"type": "progress", "content": chunk})

            response = await svc.chat.send_message(
                session_id=session_id,
                message=content,
                user_id=user.username,
                on_progress=on_progress,
            )
            await websocket.send_json({"type": "complete", "content": response})

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
