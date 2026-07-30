"""Main chat endpoint — sends message with full conversation history to Groq."""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from routes import (
    get_db,
    ChatRequest,
    chat_with_history,
    truncate_title,
    logger,
)

router = APIRouter(tags=["Chat"])


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    now = datetime.now(timezone.utc).isoformat()
    user_msg = req.message.strip()

    # Verify session exists
    with get_db() as conn:
        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?", (req.session_id,)
        ).fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")

    # Invoke LLM with full message history from SQLite
    try:
        ai_response = chat_with_history(req.session_id, user_msg)
    except Exception as exc:
        logger.error("Chat error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"response": f"Something went wrong: {exc}"},
        )

    # Persist to SQLite (both messages)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (req.session_id, "user", user_msg, now),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (req.session_id, "assistant", ai_response, now),
        )
        # Auto-title on first exchange
        msg_count = conn.execute(
            "SELECT COUNT(*) as c FROM messages WHERE session_id = ?",
            (req.session_id,),
        ).fetchone()["c"]
        if msg_count == 2:
            title = truncate_title(user_msg)
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, req.session_id),
            )
        else:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, req.session_id),
            )

    return {"response": ai_response}
