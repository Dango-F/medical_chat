"""Session API endpoints - allow clients to persist/load sessions by user_id"""

from fastapi import APIRouter, HTTPException
from loguru import logger
from typing import Any

from app.services.session_service import session_service

router = APIRouter()


@router.post("")
async def save_session(payload: Any):
    """Save or update a session. Payload must include `user_id` and `session` (object)"""
    user_id = payload.get("user_id")
    session = payload.get("session")
    if not user_id or not session:
        raise HTTPException(
            status_code=400, detail="Missing user_id or session")

    sid = await session_service.save_session(user_id, session)
    return {"status": "ok", "session_id": sid}


@router.get("/{user_id}")
async def list_sessions(user_id: str):
    try:
        sessions = await session_service.list_sessions(user_id)
        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"Failed list sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/{session_id}")
async def get_session(user_id: str, session_id: str):
    session = await session_service.get_session(user_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session}


@router.delete("/{user_id}/{session_id}")
async def delete_session(user_id: str, session_id: str):
    await session_service.delete_session(user_id, session_id)
    return {"status": "ok"}
