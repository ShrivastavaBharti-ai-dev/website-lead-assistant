"""Understand one visitor message: which lead details it contains, whether it
asks a question, and whether the visitor wants a consultation.

* GeminiExtractor: Gemini structured output via LangChain (handles messy text).
* RulesExtractor: regular expressions only (no API key needed; also the
  baseline in the evaluation).
What counts as a lead detail comes from the business profile, and both
outputs go through that profile's validators.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Protocol

from .fields import parse_email

DEFAULT_CHAT_MODEL = "gemini-3.5-flash-lite"

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


class RulesExtractor:
    name = "rules"
    live = False

    def __init__(self, profile):
        self.profile = profile

    def extract(self, message: str, asked: str | None, lead: dict) -> dict:
        result = _empty(message)
        result["fields"] = self.profile.rule_fields(message, asked)
        text = message.strip()
        short_answer = asked in result["fields"] and len(text.split()) <= 8
        if ("?" in text or _QUESTION_START.search(text)) and not short_answer:
            result["question"] = text
        result["wants_consultation"] = bool(self.profile.WANTS.search(text))
        return result


class GeminiExtractor:
    live = True

    def __init__(self, profile, model: str | None = None):
        from langchain_google_genai import ChatGoogleGenerativeAI

        self.profile = profile
        # The question without its "Thanks, {name}!" opening, to remind the model what was asked.
        self._question_text = {key: text.split("{name}")[-1] for key, (text, _) in profile.QUESTIONS.items()}
        self.model = model or os.getenv("GEMINI_CHAT_MODEL", DEFAULT_CHAT_MODEL)
        self.name = f"gemini:{self.model}"
        llm = ChatGoogleGenerativeAI(model=self.model, max_retries=2)
        self._chain = llm.with_structured_output(profile.EXTRACT_SCHEMA, method="json_schema")

    def extract(self, message: str, asked: str | None, lead: dict) -> dict:
        human = (f"Assistant's last question: {self._question_text.get(asked, '(none)') if asked else '(none)'}\n"
                 f"Details already known: {json.dumps(lead, ensure_ascii=False)}\n\nVisitor message: {message}")
        raw = _with_backoff(lambda: self._chain.invoke([("system", self.profile.EXTRACT_PROMPT), ("human", human)]))
        raw = raw if isinstance(raw, dict) else {}
        result = _empty(message)
        result["fields"] = self.profile.normalise_fields({k: v for k, v in raw.items() if v not in ("", "none", None)})
        # Phone numbers and emails are checked by code, not trusted from the model.
        for key, parser in (("phone", self.profile.parse_phone), ("email", parse_email)):
            value = parser(message)
            if value:
                result["fields"][key] = value
            else:
                result["fields"].pop(key, None)
        result["question"] = str(raw.get("question") or "").strip()[:300]
        result["wants_consultation"] = bool(raw.get("wants_consultation")) or bool(self.profile.WANTS.search(message))
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
