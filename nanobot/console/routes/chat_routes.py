"""Chat routes: WebSocket conversations + session management."""

from __future__ import annotations

import asyncio
import json

from loguru import logger
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from nanobot.console import auth
from nanobot.console.models import ChatSessionCreateRequest, UserInfo

router = APIRouter(prefix="/api/chat", tags=["chat"])

def _get_chat_service():
    from nanobot.console.app import get_services
    svc = get_services().chat
    if svc is None:
        raise HTTPException(status_code=503, detail="Chat service unavailable (gateway offline)")
    return svc

@router.get("/sessions")
async def list_sessions(user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer"))):
    return _get_chat_service().list_sessions(user.username)

@router.post("/sessions")
async def create_session(
    body: ChatSessionCreateRequest,
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    sid = _get_chat_service().create_session(user.username, body.title)
    return {"session_id": sid}

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    if not _get_chat_service().delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}

@router.get("/sessions/{session_id}/history")
async def get_history(
    session_id: str,
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    return _get_chat_service().get_history(session_id)

@router.get("/messages")
async def get_messages(
    session_key: str = Query(..., description="Session key (e.g. telegram:12345)"),
    user: UserInfo = Depends(auth.require_role("admin", "editor", "viewer")),
):
    """Full message history for any session, including tool_calls and reasoning."""
    return _get_chat_service().get_messages(session_key)

@router.websocket("/ws/{session_id}")
async def chat_ws(websocket: WebSocket, session_id: str):
    user = await auth.get_ws_user(websocket)
    await websocket.accept()

    svc_chat = _get_chat_service()
    from nanobot.console.app import get_services
    svc = get_services()

    # Register a console listener so async results (e.g. claude_code completion)
    # can be pushed to this WebSocket even when no user message is in-flight.
    session_key = f"console:{session_id}"
    bus = svc_chat._agent.bus
    listener_queue = bus.register_console_listener(session_key)

    async def _push_async_results():
        """Background task: forward outbound messages from the listener queue."""
        try:
            while True:
                msg = await listener_queue.get()
                if not msg.content or msg.content in ("(empty)", "[empty message]"):
                    continue
                try:
                    await websocket.send_json({
                        "type": "async_result",
                        "content": msg.content,
                    })
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    push_task = asyncio.create_task(_push_async_results())

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

            async def on_progress(chunk: str, *, tool_hint: bool = False, is_thinking: bool = False):
                msg_type = "thinking" if is_thinking else "progress"
                await websocket.send_json({"type": msg_type, "content": chunk, "tool_hint": tool_hint})

            response = await svc_chat.send_message(
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
    finally:
        push_task.cancel()
        bus.unregister_console_listener(session_key)
        logger.debug("Console WS listener cleaned up for {}", session_key)