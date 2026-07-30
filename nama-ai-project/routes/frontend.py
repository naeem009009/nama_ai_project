"""Route for serving public frontend pages (landing, auth)."""

from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["Frontend"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def serve_landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


@router.get("/auth", response_class=HTMLResponse)
async def serve_auth(request: Request):
    return templates.TemplateResponse("auth.html", {"request": request})
