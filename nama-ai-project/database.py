"""Database connection and helper functions for Nama AI.

Handles SQLite connection management, user table creation, and
user CRUD operations. Passwords are hashed via bcrypt.
"""

import os
import sqlite3
from datetime import datetime, timezone

import bcrypt

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nama_ai.db")


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
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
        """)
    return conn


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def create_user(username: str, email: str, password: str) -> dict:
    """Insert a new user. Raises sqlite3.IntegrityError on duplicate."""
    now = datetime.now(timezone.utc).isoformat()
    pw_hash = hash_password(password)
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (username, email, pw_hash, now),
        )
        return {
            "id": cur.lastrowid,
            "username": username,
            "email": email,
            "created_at": now,
        }


def get_user_by_username(username: str):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()


def get_user_by_email(email: str):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()


def get_user_by_id(user_id: int):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
