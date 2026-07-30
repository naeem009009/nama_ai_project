"""Shared dependencies for route modules — db, Groq client, schemas, helpers."""

import os
import uuid
import sqlite3
import logging
import traceback
import time
from datetime import datetime, timezone
from fastapi import HTTPException, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from groq import Groq, APIConnectionError

logger = logging.getLogger("nama-ai")

# ---------------------------------------------------------------------------
# API Key auth
# ---------------------------------------------------------------------------
API_KEY = os.environ["NAMA_API_KEY"]
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Dependency that rejects requests with a missing/invalid API key."""
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key.")
    return api_key

# ---------------------------------------------------------------------------
# Groq client (raw SDK — kept for history query route)
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
raw_client = Groq(api_key=GROQ_API_KEY)
MODEL_NAME = "llama-3.3-70b-versatile"


def _groq_with_retry(messages, model, max_retries=3, **kwargs):
    """Call Groq API with exponential backoff on connection errors."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            return raw_client.chat.completions.create(
                messages=messages, model=model, **kwargs
            )
        except APIConnectionError as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(
                    "Groq connection error (attempt %d/%d), retrying in %ds ...",
                    attempt + 1, max_retries, wait,
                )
                time.sleep(wait)
    raise last_exc

# ---------------------------------------------------------------------------
# Chat with history (raw Groq SDK — no LangChain)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are Nama AI, an intelligent and helpful assistant. "
    "Respond conversationally, clearly, and concisely. "
    "Use markdown formatting where appropriate (code blocks, lists, bold)."
)


def chat_with_history(session_id: str, user_input: str) -> str:
    """Invoke the Groq API with the full conversation history for the session.

    Builds the messages array directly from SQLite so the model sees all
    prior user and assistant exchanges, exactly like the notebook's
    ``RunnableWithMessageHistory`` pattern.
    """
    # 1. Load prior conversation from SQLite
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()

    # 2. Build raw messages list for Groq API
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for r in rows:
        messages.append({"role": r["role"], "content": r["content"]})
    messages.append({"role": "user", "content": user_input})

    # 3. Call Groq SDK directly — same as notebook
    try:
        response = _groq_with_retry(
            messages=messages,
            model=MODEL_NAME,
            temperature=0.7,
            max_tokens=1024,
            top_p=0.9,
            stream=False,
        )
        answer = response.choices[0].message.content
        return answer.strip() if answer else "I wasn't able to generate a response. Please try again."
    except Exception as exc:
        logger.error("Chat error: %s", traceback.format_exc())
        raise

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nama_ai.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
    logger.info("Database initialised.")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    session_id: str
    message: str


class HistoryQueryRequest(BaseModel):
    question: str


# ---------------------------------------------------------------------------
# Generation (raw Groq — used only by the history route)
# ---------------------------------------------------------------------------
def generate_answer_with_context(prompt: str, context: str) -> str:
    """Generate an answer enriched with historical context from past chats."""
    try:
        chat_completion = _groq_with_retry(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Nama AI, an intelligent and helpful assistant. "
                        "You have access to the user's previous conversation history below. "
                        "Use this context to answer the user's question whenever relevant. "
                        "If the context doesn't contain useful information, answer normally.\n\n"
                        "--- Previous conversation history ---\n"
                        f"{context}\n"
                        "--- End of history ---"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            model=MODEL_NAME,
            temperature=0.7,
            max_tokens=1024,
            top_p=0.9,
            stream=False,
        )
        response = chat_completion.choices[0].message.content
        return response.strip() if response else "I wasn't able to generate a response. Please try again."
    except Exception as exc:
        logger.error("Groq API error: %s", traceback.format_exc())
        raise


def truncate_title(text: str, max_words: int = 8) -> str:
    words = text.split()[:max_words]
    title = " ".join(words)
    return title if len(title) <= 60 else title[:57] + "..."
