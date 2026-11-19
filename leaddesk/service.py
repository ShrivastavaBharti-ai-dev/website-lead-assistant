"""Sessions, limits and the JSON contract used by the web server.
Framework-free, so it can be tested without running a server."""
from __future__ import annotations

import datetime
import os
import threading
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path

from .conversation import Conversation, Session
from .extract import GeminiExtractor, RulesExtractor
from .faq import FaqAnswerer
from .sinks import full_header, make_sink

ROOT = Path(__file__).resolve().parent.parent
MAX_MESSAGE_CHARS = 500
# A global cap on live model calls per day, shared across all visitors and
# businesses, so a public demo can't run the owner's API key past a daily budget.
# Override with the MAX_LLM_CALLS_PER_DAY environment variable.
MAX_LLM_CALLS_PER_DAY = int(os.getenv("MAX_LLM_CALLS_PER_DAY", "500"))


class RateLimiter:
    """At most `limit` messages per `window` seconds per visitor IP."""

    def __init__(self, limit: int = 20, window: float = 60.0):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            if len(self._hits) > 5000:  # forget idle visitors
                for k in [k for k, v in self._hits.items() if not v][:1000]:
                    del self._hits[k]
            return True


class DailyCap:
    """A global per-day limit on live model calls, shared across every visitor and
    business. Thread-safe; the count resets on a new date (server local) and on
    restart. A safety net on top of the per-visitor RateLimiter."""

    def __init__(self, limit: int):
        self.limit = limit
        self._day: datetime.date | None = None
        self._count = 0
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            today = datetime.date.today()
            if self._day != today:
                self._day, self._count = today, 0
            if self._count >= self.limit:
                return False
            self._count += 1
            return True


_daily_cap = DailyCap(MAX_LLM_CALLS_PER_DAY)


class LeadService:
    def __init__(self, conversation: Conversation, mode: str, sink_name: str, max_sessions: int = 500,
                 session_ttl: float = 2 * 3600, max_messages: int = 40, limiter: RateLimiter | None = None,
                 chat_end: str = "We've reached the end of this chat. Please contact the team directly."):
        self.conversation, self.mode, self.sink_name, self.chat_end = conversation, mode, sink_name, chat_end
        self.max_sessions, self.session_ttl, self.max_messages = max_sessions, session_ttl, max_messages
        self.limiter = limiter or RateLimiter()
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def _session(self, session_id: str | None) -> Session:
        now = time.time()
        with self._lock:
            for key in [k for k, s in self._sessions.items() if now - s.updated > self.session_ttl]:
                del self._sessions[key]
            if session_id and session_id in self._sessions:
                return self._sessions[session_id]
            if len(self._sessions) >= self.max_sessions:
                oldest = min(self._sessions.values(), key=lambda s: s.updated)
                del self._sessions[oldest.id]
            session = Session()
            self._sessions[session.id] = session
            return session

    def greeting(self) -> dict:
        reply = self.conversation.greet()
        return {"reply": reply.text, "quick_replies": reply.quick_replies}

    def chat(self, payload: dict, client: str) -> tuple[int, dict]:
        message = str(payload.get("message") or "").strip()
        if not message:
            return 400, {"error": "Please type a message."}
        if len(message) > MAX_MESSAGE_CHARS:
            return 400, {"error": f"Please keep messages under {MAX_MESSAGE_CHARS} characters."}
        if not self.limiter.allow(client):
            return 429, {"error": "You're sending messages very quickly. Please wait a minute."}
        session = self._session(payload.get("session_id"))
        if payload.get("page") and not session.page:
            session.page = str(payload["page"])[:300]
        if session.messages >= self.max_messages:
            return 200, {"session_id": session.id, "reply": self.chat_end, "quick_replies": [],
                         "lead_complete": session.submitted}
        if self.mode.startswith("gemini") and not _daily_cap.allow():
            return 200, {"session_id": session.id, "quick_replies": [], "lead_complete": session.submitted,
                         "reply": "This public demo has paused for today after reaching its daily limit, which "
                                  "keeps it inside its free API budget. Please try again tomorrow, or contact "
                                  "the team directly."}
        try:
            reply = self.conversation.handle(session, message)
        except Exception as error:  # noqa: BLE001
            text = f"{type(error).__name__} {error}".lower()
            busy = any(s in text for s in ("429", "resource_exhausted", "quota", "rate limit"))
            return 503, {"session_id": session.id, "error": "The assistant is busy right now. Please try again in a "
                         "minute." if busy else "Sorry, something went wrong. Please try again."}
        body = asdict(reply)
        body.pop("text")
        return 200, {"session_id": session.id, "reply": reply.text, **body}

    def health(self) -> dict:
        return {"ok": True, "mode": self.mode, "leads_go_to": self.sink_name, "sessions": len(self._sessions)}


def build_service(profile, api_key: str | None = None, limiter: RateLimiter | None = None) -> LeadService:
    """The assistant for one business profile. Gemini when a key is set, otherwise offline rules."""
    from docanswer import make_providers

    key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    embedder, answer_model, live = make_providers(key)
    extractor = GeminiExtractor(profile) if live else RulesExtractor(profile)
    faq = FaqAnswerer(embedder, answer_model, profile.DOCS, profile.BUSINESS,
                      cache_path=ROOT / ".cache" / f"embeddings-{profile.KEY}.json")
    # Each business gets its own CSV file and its own tab in the Google Sheet.
    sink, sink_name = make_sink(os.getenv("SHEETS_WEBHOOK_URL"), os.getenv("SHEETS_TOKEN"),
                                ROOT / "leads" / f"{profile.KEY}.csv", full_header(profile.LEAD_HEADER),
                                tab=f"Leads - {profile.KEY}")
    mode = f"gemini ({extractor.model})" if live else "offline rules"
    return LeadService(Conversation(profile, extractor, faq, sink), mode, sink_name,
                       limiter=limiter, chat_end=profile.CHAT_END)
