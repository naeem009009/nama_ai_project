"""Message retrieval routes."""

from fastapi import APIRouter

from routes import get_db

router = APIRouter(prefix="/api/sessions", tags=["Messages"])


@router.get("/{session_id}/messages")
async def get_messages(session_id: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]
