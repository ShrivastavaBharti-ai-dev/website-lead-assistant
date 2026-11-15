"""Web server: the chat API, the embeddable widget and the demo website.

    uvicorn server.main:app --reload

Environment variables (all optional):
    GOOGLE_API_KEY       Gemini key; without it the assistant uses offline rules
    SHEETS_WEBHOOK_URL   Apps Script web app URL (integrations/google_apps_script.gs)
    SHEETS_TOKEN         the TOKEN set in that script
    ALLOWED_ORIGINS      comma-separated sites allowed to embed the widget (default: any)
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from leaddesk import build_service  # noqa: E402  (after .env is loaded)
from leaddesk.profiles import interior  # noqa: E402

service = build_service(interior)
app = FastAPI(title="LeadDesk", description="Website assistant that answers questions and captures leads.",
              version="1.0")
origins = [o.strip() for o in (os.getenv("ALLOWED_ORIGINS") or "*").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"])


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    session_id: str | None = Field(default=None, max_length=64)
    page: str | None = Field(default=None, max_length=300)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.post("/api/chat")
def chat(body: ChatIn, request: Request) -> JSONResponse:
    status, payload = service.chat(body.model_dump(), client_ip(request))
    return JSONResponse(payload, status_code=status)


@app.get("/api/greeting")
def greeting() -> dict:
    return service.greeting()


@app.get("/api/health")
def health() -> dict:
    return service.health()


@app.get("/widget.js", include_in_schema=False)
def widget() -> FileResponse:
    return FileResponse(STATIC / "widget.js", media_type="application/javascript",
                        headers={"Cache-Control": "public, max-age=300"})


@app.get("/", include_in_schema=False)
def demo_site() -> FileResponse:
    return FileResponse(STATIC / "index.html", media_type="text/html")
