"""Understand one visitor message: which lead details it contains, whether it
asks a question, and whether the visitor wants a consultation.

* GeminiExtractor: Gemini structured output via LangChain (handles messy text).
* RulesExtractor: regular expressions only (no API key needed; also the
  baseline in the evaluation).
Both outputs go through the same validators in fields.py.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Protocol

from . import fields as F

DEFAULT_CHAT_MODEL = "gemini-3.5-flash-lite"

_CONSULT = re.compile(r"\b(book|consult|consultation|call me|call back|callback|site visit|visit|quote|quotation|"
                      r"estimate|meet|appointment|get started|start my project|interested)\b", re.IGNORECASE)
_QUESTION_START = re.compile(r"^(what|how|do|does|did|can|could|is|are|which|when|why|where|will|would|should|"
                             r"price|prices|cost|costs|tell me)\b", re.IGNORECASE)
_DECLINE = re.compile(r"^(no|nope|not now|no thanks|maybe later|later|i have another question)\b", re.IGNORECASE)


class Extractor(Protocol):
    name: str
    live: bool

    def extract(self, message: str, asked: str | None, lead: dict) -> dict: ...


def _empty(message: str) -> dict:
    return {"fields": {}, "question": "", "wants_consultation": False,
            "declined": bool(_DECLINE.search(message.strip()))}


def rule_fields(message: str, asked: str | None) -> dict:
    found: dict = {}
    if phone := F.parse_phone(message):
        found["phone"] = phone
    if email := F.parse_email(message):
        found["email"] = email
    if name := F.parse_name(message, asked == "name"):
        found["name"] = name
    if project := F.project_type(message):
        found["project_type"] = project
    if prop := F.property_type(message):
        found["property"] = prop
    if budget := F.budget_band(message):
        found["budget"] = budget
    if timeline := F.timeline_band(message):
        found["timeline"] = timeline
    if area := F.match_area(message):
        found["area"] = area
    elif asked == "area" and "?" not in message and len(message.split()) <= 6 and not found:
        found["area"] = message.strip(" .!")
    return F.normalise_fields(found)


class RulesExtractor:
    name = "rules"
    live = False

    def extract(self, message: str, asked: str | None, lead: dict) -> dict:
        result = _empty(message)
        result["fields"] = rule_fields(message, asked)
        text = message.strip()
        short_answer = asked in result["fields"] and len(text.split()) <= 8
        if ("?" in text or _QUESTION_START.search(text)) and not short_answer:
            result["question"] = text
        result["wants_consultation"] = bool(_CONSULT.search(text))
        return result


EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "phone": {"type": "string"},
        "email": {"type": "string"},
        "project_type": {"type": "string", "enum": [*F.PROJECT_TYPES, "none"]},
        "property": {"type": "string", "enum": [*F.PROPERTIES, "none"]},
        "area": {"type": "string", "description": "Locality or city of the property"},
        "budget": {"type": "string", "enum": [*F.BUDGETS, "none"]},
        "timeline": {"type": "string", "enum": [*F.TIMELINES, "none"]},
        "question": {"type": "string"},
        "wants_consultation": {"type": "boolean"},
    },
    "required": ["name", "phone", "email", "project_type", "property", "area", "budget", "timeline", "question",
                 "wants_consultation"],
}

EXTRACT_PROMPT = """You read one chat message from a visitor on the website of an interior design studio in Pune.
Extract ONLY details stated in this message. Use "" or "none" for anything not stated. Never guess.
- budget bands: under_3l (< ₹3 lakh), 3_6l, 6_10l, 10_15l, above_15l. "8 lakh" -> 6_10l. A range -> use its upper end.
- timeline bands: within_1m, 1_3m, 3_6m, later (6+ months, next year, just exploring).
- project_type: full_home, kitchen, wardrobes, single_room (one or two rooms), office (office, shop, clinic, cafe), other.
- property: 1bhk, 2bhk, 3bhk, 4bhk_plus, villa, office, other.
- A short reply usually answers the assistant's last question (shown below).
- question: if the visitor asks something about the studio (services, prices, timelines, process, areas, warranty),
  rewrite it as one standalone question in English; otherwise "".
- wants_consultation: true if they ask for a consultation, quote, call, site visit or want to start a project."""

QUESTION_TEXT = {key: text.split("{name}")[-1] for key, (text, _) in F.QUESTIONS.items()}


class GeminiExtractor:
    live = True

    def __init__(self, model: str | None = None):
        from langchain_google_genai import ChatGoogleGenerativeAI

        self.model = model or os.getenv("GEMINI_CHAT_MODEL", DEFAULT_CHAT_MODEL)
        self.name = f"gemini:{self.model}"
        llm = ChatGoogleGenerativeAI(model=self.model, max_retries=2)
        self._chain = llm.with_structured_output(EXTRACT_SCHEMA, method="json_schema")

    def extract(self, message: str, asked: str | None, lead: dict) -> dict:
        human = (f"Assistant's last question: {QUESTION_TEXT.get(asked, '(none)') if asked else '(none)'}\n"
                 f"Details already known: {json.dumps(lead, ensure_ascii=False)}\n\nVisitor message: {message}")
        raw = _with_backoff(lambda: self._chain.invoke([("system", EXTRACT_PROMPT), ("human", human)]))
        raw = raw if isinstance(raw, dict) else {}
        result = _empty(message)
        result["fields"] = F.normalise_fields({k: v for k, v in raw.items() if v not in ("", "none", None)})
        # Phone numbers and emails are checked by code, not trusted from the model.
        for key, parser in (("phone", F.parse_phone), ("email", F.parse_email)):
            value = parser(message)
            if value:
                result["fields"][key] = value
            else:
                result["fields"].pop(key, None)
        result["question"] = str(raw.get("question") or "").strip()[:300]
        result["wants_consultation"] = bool(raw.get("wants_consultation")) or bool(_CONSULT.search(message))
        return result


def _with_backoff(call, retries: int = 3, base_delay: float = 2.0):
    for attempt in range(retries + 1):
        try:
            return call()
        except Exception as error:  # noqa: BLE001
            text = f"{type(error).__name__} {error}".lower()
            if attempt == retries or not any(s in text for s in ("429", "resource_exhausted", "quota", "rate limit")):
                raise
            time.sleep(base_delay * (2 ** attempt))
    raise RuntimeError("unreachable")
