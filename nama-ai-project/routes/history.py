"""History Q&A route — searches previous conversations for relevant context."""

from fastapi import APIRouter, HTTPException
from routes import (
    get_db,
    HistoryQueryRequest,
    generate_answer_with_context,
)

router = APIRouter(prefix="/api", tags=["History"])


@router.post("/query-history")
async def query_history(req: HistoryQueryRequest):
    """Ask a question that may reference previous conversations.

    Searches all past messages (across all sessions) for content relevant to
    the user's question, then answers using that context.
    """
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    question = req.question.strip()

    # --- 1. Extract keywords from the question ---
    # Split into words, filter out common stop words, keep meaningful terms
    stop_words = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "out", "off", "over", "under", "again",
        "further", "then", "once", "here", "there", "when", "where",
        "why", "how", "all", "each", "every", "both", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only",
        "own", "same", "so", "than", "too", "very", "just", "because",
        "but", "and", "or", "if", "what", "which", "who", "whom",
        "this", "that", "these", "those", "it", "its", "i", "me",
        "my", "we", "our", "you", "your", "he", "him", "his", "she",
        "her", "they", "them", "their", "please", "about", "tell",
        "about", "remember", "previous", "chat", "earlier", "before",
        "did", "last", "said", "say", "asked", "talked", "discuss",
    }
    keywords = [
        w for w in question.lower().split()
        if w not in stop_words and len(w) > 2
    ]

    # --- 2. Search for relevant messages ---
    context_chunks = []
    if keywords:
        with get_db() as conn:
            # Build a LIKE query for each keyword
            conditions = " OR ".join("m.content LIKE ?" for _ in keywords)
            params = [f"%{kw}%" for kw in keywords]
            sql = f"""
                SELECT m.content, m.role, s.title AS session_title
                FROM messages m
                JOIN sessions s ON s.id = m.session_id
                WHERE {conditions}
                ORDER BY m.id DESC
                LIMIT 20
            """
            rows = conn.execute(sql, params).fetchall()
            for r in rows:
                context_chunks.append(
                    f"[{r['role']} in \"{r['session_title']}\"] {r['content']}"
                )

    # --- 3. Build context string ---
    context_str = "\n\n".join(context_chunks) if context_chunks else ""

    # --- 4. Generate answer with context ---
    try:
        answer = generate_answer_with_context(question, context_str)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI service error: {exc}",
        )

    return {
        "answer": answer,
        "context_used": bool(context_chunks),
        "matches_found": len(context_chunks),
    }
