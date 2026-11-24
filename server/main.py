"""Web server: the chat API, the embeddable widget and one demo website per business.

Pages: / (interior studio), /estate, /dental. Each business has its own API under
/api/<business>/...; the plain /api/... paths are the interior studio, kept for older embeds.

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

from fastapi import FastAPI, HTTPException, Request
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
from leaddesk.profiles import dental, estate, interior  # noqa: E402
from leaddesk.service import RateLimiter  # noqa: E402

# One limiter for all businesses, so a visitor can't triple their allowance by switching demos.
limiter = RateLimiter()
services = {p.KEY: build_service(p, limiter=limiter) for p in (interior, estate, dental)}
service = services[interior.KEY]
PAGES = {interior.KEY: "index.html", estate.KEY: "estate.html", dental.KEY: "dental.html"}
# Pitch pages for business owners, linked from outreach emails.
LANDING = {"estate-agents": "for-estate-agents.html", "dental-practices": "for-dental-practices.html"}

app = FastAPI(title="LeadDesk", description="Website assistant that answers questions and captures leads.",
              version="1.1")
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


def service_for(business: str):
    if business not in services:
        raise HTTPException(404, "Unknown business.")
    return services[business]


@app.post("/api/chat")
@app.post("/api/{business}/chat")
def chat(body: ChatIn, request: Request, business: str = interior.KEY) -> JSONResponse:
    status, payload = service_for(business).chat(body.model_dump(), client_ip(request))
    return JSONResponse(payload, status_code=status)


@app.get("/api/greeting")
@app.get("/api/{business}/greeting")
def greeting(business: str = interior.KEY) -> dict:
    return service_for(business).greeting()


@app.get("/api/health")
@app.get("/api/{business}/health")
def health(business: str = interior.KEY) -> dict:
    return service_for(business).health()


@app.get("/widget.js", include_in_schema=False)
def widget() -> FileResponse:
    return FileResponse(STATIC / "widget.js", media_type="application/javascript",
                        headers={"Cache-Control": "public, max-age=300"})


@app.get("/landing.css", include_in_schema=False)
def landing_css() -> FileResponse:
    return FileResponse(STATIC / "landing.css", media_type="text/css",
                        headers={"Cache-Control": "public, max-age=300"})


@app.get("/for/{niche}", include_in_schema=False)
def landing(niche: str) -> FileResponse:
    if niche not in LANDING:
        raise HTTPException(404, "Page not found.")
    return FileResponse(STATIC / LANDING[niche], media_type="text/html")


@app.get("/", include_in_schema=False)
@app.get("/{business}", include_in_schema=False)
def demo_site(business: str = interior.KEY) -> FileResponse:
    if business not in PAGES:
        raise HTTPException(404, "Page not found.")
    return FileResponse(STATIC / PAGES[business], media_type="text/html")
