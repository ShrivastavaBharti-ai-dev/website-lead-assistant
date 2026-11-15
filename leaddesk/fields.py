"""Parsers every business profile shares: email addresses, names and
tap-to-answer choices. Anything specific to one business (phone formats,
budgets, areas, questions) lives in its profile under leaddesk/profiles/."""
from __future__ import annotations

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def parse_email(text: str) -> str | None:
    match = _EMAIL.search(text or "")
    return match.group(0).lower() if match else None


def choice_by_label(text: str, choices: dict[str, str]) -> str | None:
    clean = (text or "").strip().lower()
    for key, label in choices.items():
        if clean == label.lower() or clean == key:
            return key
    return None


_NAME_PATTERNS = [r"\bmy name is ([a-z][a-z .'-]{1,40})", r"\bthis is ([a-z][a-z .'-]{1,40})",
                  r"\bname\s*[:\-]\s*([a-z][a-z .'-]{1,40})", r"\bi am ([a-z][a-z.'-]{1,20})\s*$",
                  r"\b(?:i am|i'm|im) ([a-z][a-z'-]{1,20})(?=\s*[.,!])"]
_NOT_NAMES = {"looking", "interested", "planning", "from", "in", "not", "here", "just", "a", "the", "fine", "ok",
              "okay", "i", "i'm", "im", "we", "we're", "yes", "no", "hi", "hello", "hey", "thanks", "sure", "need",
              "want", "kitchen", "home", "flat", "house", "price", "cost", "what", "how", "is", "do", "can"}


def clean_name(raw: str) -> str | None:
    words = [w for w in re.split(r"\s+", raw.strip(" .,!")) if w]
    if not 1 <= len(words) <= 4 or any(w.lower() in _NOT_NAMES for w in words):
        return None
    if not all(re.fullmatch(r"[A-Za-z.'-]+", w) for w in words):
        return None
    return " ".join(w[:1].upper() + w[1:] for w in words)


def parse_name(text: str, was_asked: bool) -> str | None:
    lower = (text or "").strip().lower()
    for pattern in _NAME_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            # Stop at words that start a new clause: "this is Rahul and I need a kitchen".
            candidate = re.split(r"\b(and|i|i'm|we|my|from|in|,)\b", match.group(1))[0]
            return clean_name(candidate)
    if was_asked:
        return clean_name(text)
    return None
