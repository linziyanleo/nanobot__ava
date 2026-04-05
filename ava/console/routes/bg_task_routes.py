"""Background task status API — REST + WebSocket real-time updates."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter(prefix="/api/bg-tasks", tags=["bg-tasks"])


def _get_bg_store():
    from ava.console.app import get_services
    svc = get_services()
    agent_loop = getattr(svc.chat, "_agent", None) if svc.chat else None
    return getattr(agent_loop, "bg_tasks", None) if agent_loop else None


@router.get("")
async def list_tasks(session_key: str | None = None, include_finished: bool = True):
    bg_store = _get_bg_store()
    if not bg_store:
        return {"running": 0, "total": 0, "tasks": []}
    return bg_store.get_status(
        session_key=session_key,
        include_finished=include_finished,
    )


@router.get("/history")
async def list_history(
    page: int = 1,
    page_size: int = 20,
    session_key: str | None = None,
):
    bg_store = _get_bg_store()
    if not bg_store:
        return {"tasks": [], "total": 0, "page": page, "page_size": page_size}
    return bg_store.query_history(page=page, page_size=page_size, session_key=session_key)


@router.get("/{task_id}")
async def get_task(task_id: str):
    bg_store = _get_bg_store()
    if not bg_store:
        return {"error": "BackgroundTaskStore not initialized"}
    status = bg_store.get_status(task_id=task_id)
    if status["total"] == 0:
        return {"error": f"Task {task_id} not found"}
    return status["tasks"][0]


@router.get("/{task_id}/detail")
async def get_task_detail(task_id: str):
    """获取任务的完整 prompt 和 result。"""
    bg_store = _get_bg_store()
    if not bg_store:
        return {"error": "BackgroundTaskStore not initialized"}
    detail = bg_store.get_task_detail(task_id)
    if not detail:
        return {"error": f"Task {task_id} not found"}
    return detail


@router.get("/{task_id}/timeline")
async def get_timeline(task_id: str):
    bg_store = _get_bg_store()
    if not bg_store:
        return {"events": []}
    events = bg_store.get_timeline(task_id)
    return {
        "task_id": task_id,
        "events": [
            {"timestamp": e.timestamp, "event": e.event, "detail": e.detail}
            for e in events
        ],
    }


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    bg_store = _get_bg_store()
    if not bg_store:
        return {"message": "BackgroundTaskStore not initialized"}
    result = await bg_store.cancel(task_id)
    return {"message": result}


@router.websocket("/ws")
async def bg_tasks_ws(websocket: WebSocket):
    """Push task status snapshots at 2 s intervals; skip if unchanged."""
    await websocket.accept()
    bg_store = _get_bg_store()

    if not bg_store:
        await websocket.send_json({"type": "error", "message": "BackgroundTaskStore not initialized"})
        await websocket.close()
        return

    prev_snapshot: str = ""
    try:
        while True:
            status = bg_store.get_status(include_finished=True)
            snapshot_json = json.dumps(status, default=str)
            if snapshot_json != prev_snapshot:
                await websocket.send_json({"type": "update", **status})
                prev_snapshot = snapshot_json
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("bg_tasks_ws closed: {}", exc)
