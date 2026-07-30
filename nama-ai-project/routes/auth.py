"""Auth routes — register, login, logout, and protected chat page.

Uses JWT stored in an HttpOnly cookie named ``nama_token``.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from routes import logger
from database import (
    create_user,
    get_user_by_username,
    get_user_by_email,
    get_user_by_id,
    verify_password,
)

# ---------------------------------------------------------------------------
# Jinja2 templates (shared)
# ---------------------------------------------------------------------------
TEMPLATE_DIR = str(Path(__file__).resolve().parent.parent / "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# ---------------------------------------------------------------------------
# JWT config
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ["NAMA_JWT_SECRET"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 168  # 7 days
COOKIE_NAME = "nama_token"

# ---------------------------------------------------------------------------
# API key (for downstream chat API calls from the rendered page)
# ---------------------------------------------------------------------------
API_KEY = os.environ["NAMA_API_KEY"]

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def create_token(user_id: int, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str):
    """Return the decoded payload or None."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(tags=["Auth"])


# ---------------------------------------------------------------------------
# API — Register
# ---------------------------------------------------------------------------

@router.post("/api/register")
async def register(request: Request):
    data = await request.json()
    username = (data.get("username") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm  = data.get("confirm_password") or ""

    # --- validation ---
    if not username or not email or not password:
        return JSONResponse(status_code=400, content={"detail": "All fields are required."})
    if len(username) < 3:
        return JSONResponse(status_code=400, content={"detail": "Username must be at least 3 characters."})
    if "@" not in email or "." not in email:
        return JSONResponse(status_code=400, content={"detail": "Please enter a valid email address."})
    if len(password) < 6:
        return JSONResponse(status_code=400, content={"detail": "Password must be at least 6 characters."})
    if password != confirm:
        return JSONResponse(status_code=400, content={"detail": "Passwords do not match."})

    # --- uniqueness ---
    if get_user_by_username(username):
        return JSONResponse(status_code=409, content={"detail": "Username already taken."})
    if get_user_by_email(email):
        return JSONResponse(status_code=409, content={"detail": "Email already registered."})

    # --- create ---
    try:
        user = create_user(username, email, password)
    except Exception as exc:
        logger.exception("Registration error")
        return JSONResponse(status_code=500, content={"detail": f"Registration failed: {exc}"})

    # Auto-login: issue token
    token = create_token(user["id"], user["username"])
    resp = JSONResponse({"ok": True, "username": user["username"]})
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,       # Set True in production behind HTTPS
        samesite="lax",
        max_age=JWT_EXPIRY_HOURS * 3600,
        path="/",
    )
    return resp


# ---------------------------------------------------------------------------
# API — Login
# ---------------------------------------------------------------------------

@router.post("/api/login")
async def login(request: Request):
    data = await request.json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return JSONResponse(status_code=400, content={"detail": "Username and password are required."})

    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        return JSONResponse(status_code=401, content={"detail": "Invalid username or password."})

    token = create_token(user["id"], user["username"])
    resp = JSONResponse({"ok": True, "username": user["username"]})
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=JWT_EXPIRY_HOURS * 3600,
        path="/",
    )
    return resp


# ---------------------------------------------------------------------------
# API — Logout
# ---------------------------------------------------------------------------

@router.post("/api/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(key=COOKIE_NAME, path="/")
    return resp


# ---------------------------------------------------------------------------
# Protected page — Chat
# ---------------------------------------------------------------------------

@router.get("/chat", response_class=HTMLResponse)
async def serve_chat(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return RedirectResponse(url="/auth", status_code=303)

    payload = verify_token(token)
    if not payload:
        resp = RedirectResponse(url="/auth", status_code=303)
        resp.delete_cookie(key=COOKIE_NAME, path="/")
        return resp

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "api_key": API_KEY,
        "username": payload["username"],
    })
