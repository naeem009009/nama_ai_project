"""Session CRUD routes."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter

from routes import get_db

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


@router.get("")
async def list_sessions():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("")
async def create_session():
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, "New Chat", now, now),
        )
    return {"session_id": session_id, "title": "New Chat", "created_at": now}


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    return {"ok": True}
