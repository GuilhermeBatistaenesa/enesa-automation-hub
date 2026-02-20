from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import SessionLocal, get_db
from app.models.user import User
from app.services.queue_service import get_async_redis, get_run_log_channel
from app.services.run_service import get_run, get_run_logs

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/runs/{run_id}/logs")
async def run_log_stream(websocket: WebSocket, run_id: UUID) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    try:
        current_user = get_current_user(token=token, db=db)
    except Exception:
        db.close()
        await websocket.close(code=4401)
        return

    if not current_user:
        db.close()
        await websocket.close(code=4401)
        return

    run = get_run(db=db, run_id=run_id)
    if not run:
        db.close()
        await websocket.close(code=4404)
        return

    await websocket.accept()

    recent_logs = get_run_logs(db=db, run_id=run_id, limit=200)
    for log_item in recent_logs:
        await websocket.send_json(
            {
                "run_id": str(run_id),
                "timestamp": log_item.timestamp.isoformat(),
                "level": log_item.level,
                "message": log_item.message,
            }
        )
    db.close()

    redis = await get_async_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(get_run_log_channel(str(run_id)))

    async def _watch_disconnect() -> None:
        while True:
            await websocket.receive_text()

    disconnect_task = asyncio.create_task(_watch_disconnect())

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                payload = message.get("data")
                if isinstance(payload, str):
                    await websocket.send_text(payload)
                else:
                    await websocket.send_text(json.dumps(payload))
            if disconnect_task.done():
                break
    except WebSocketDisconnect:
        pass
    finally:
        disconnect_task.cancel()
        await pubsub.unsubscribe(get_run_log_channel(str(run_id)))
        await pubsub.close()
        await websocket.close()

