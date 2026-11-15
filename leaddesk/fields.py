"""Parsers that more than one business profile uses: email addresses, names,
tap-to-answer choices, UK phone numbers and day-and-time preferences.
Anything specific to one business (budgets, areas, questions) lives in its
profile under leaddesk/profiles/."""
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
              "want", "what", "how", "is", "do", "can", "now", "today", "tomorrow", "asap", "please", "help",
              "nothing", "none", "anything", "anytime"}
# Everyday words that are also surnames (Hannah Price, Tom House): not a name on their own or in first place.
_NOT_FIRST_NAMES = {"kitchen", "home", "flat", "house", "price", "cost"}


def clean_name(raw: str) -> str | None:
    words = [w for w in re.split(r"\s+", raw.strip(" .,!")) if w]
    if not 1 <= len(words) <= 4 or any(w.lower() in _NOT_NAMES for w in words):
        return None
    if words[0].lower() in _NOT_FIRST_NAMES:
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


# UK numbers: 0 or +44, then ten digits starting 1, 2, 3 (landlines) or 7 (mobiles).
UK_PHONE = re.compile(r"(?<![\d£,.])(?:\+?44[\s-]?(?:\(0\)[\s-]?)?|0)([1237](?:[\s-]?\d){9})(?!\d)")


def parse_uk_phone(text: str) -> str | None:
    """UK phone number as +44XXXXXXXXXX, or None."""
    match = UK_PHONE.search(text or "")
    return "+44" + re.sub(r"\D", "", match.group(1)) if match else None


def display_uk_phone(phone: str) -> str:
    """+447700900123 -> 07700 900123"""
    return f"0{phone[3:7]} {phone[7:]}" if len(phone) == 13 else phone


def plain(text: str, limit: int = 60) -> str:
    """Free text kept for the team: short, and never starting like a spreadsheet formula."""
    return " ".join(str(text).split())[:limit].lstrip("=+-@ ").strip(" .!")


DAY_OR_TIME = re.compile(r"\b((mon|tues|wednes|thurs|fri|satur|sun)days?|mornings?|afternoons?|evenings?|"
                         r"weekends?|weekdays?)\b", re.IGNORECASE)
_FILLER = re.compile(r"\b(ok|okay|yes|yeah|sure|then|maybe|probably|please|i think|let's say)\b", re.IGNORECASE)


def time_preference(text: str, was_asked: bool, choices: dict[str, str], bands: list[tuple[str, str]],
                    context: str) -> str | None:
    """When a visitor can come in: one of the buttons (`choices`), or, only when we asked, their own words
    such as 'Tuesday after 5'. `bands` maps a pattern to each button; outside our own question a message
    must also match `context` (words like 'viewing' or 'appointment') to count."""
    text = " ".join(_FILLER.sub(" ", text or "").split()).strip(" ,.!")   # "ok saturday then" is just "Saturday"
    label = choice_by_label(text, choices)
    if label:
        return label
    lower = text.lower()
    if not was_asked and not re.search(context, lower):
        return None
    negative = re.search(r"\b(not|except|apart from|can't|cannot|never|no)\b", lower.replace("’", "'"))
    for key, pattern in bands:
        if re.search(pattern, lower) and not (negative and was_asked):
            # A named day and time ("Tuesday after 5") is more useful to the team than the band.
            return plain(text) if was_asked and len(text.split()) <= 8 and "?" not in text and len(text) > 12 else key
    if was_asked and "?" not in text and len(text.split()) <= 8:
        return plain(text) or None
    return None
