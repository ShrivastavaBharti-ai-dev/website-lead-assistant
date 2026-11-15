"""Lead fields: the questions we ask, the answer choices, and plain-code parsers.

The parsers handle the common ways people type things in India ("8 lakh",
"98765 43210", "in 2 months") and also back up the AI extractor, whose output
is always re-validated here.
"""
from __future__ import annotations

import re

# ------------------------------------------------------------------ choices
PROJECT_TYPES = {
    "full_home": "Full home",
    "kitchen": "Modular kitchen",
    "wardrobes": "Wardrobes",
    "single_room": "One or two rooms",
    "office": "Office or shop",
    "other": "Something else",
}
PROPERTIES = {"1bhk": "1 BHK", "2bhk": "2 BHK", "3bhk": "3 BHK", "4bhk_plus": "4 BHK or bigger",
              "villa": "Villa", "office": "Office or shop", "other": "Other"}
BUDGETS = {
    "under_3l": "Under ₹3 lakh",
    "3_6l": "₹3–6 lakh",
    "6_10l": "₹6–10 lakh",
    "10_15l": "₹10–15 lakh",
    "above_15l": "Above ₹15 lakh",
}
TIMELINES = {
    "within_1m": "Within a month",
    "1_3m": "1–3 months",
    "3_6m": "3–6 months",
    "later": "Later / just exploring",
}

# Questions in the order we ask them. Quick replies are shown as buttons.
QUESTIONS = {
    "name": ("Happy to help you plan it. May I have your name?", []),
    "phone": ("Thanks, {name}! What's the best mobile number to reach you on? "
              "We'll only use it to talk about your project.", []),
    "project_type": ("What would you like us to design?", list(PROJECT_TYPES.values())),
    "area": ("Which area of Pune is the property in?", []),
    "budget": ("Roughly what budget do you have in mind?", list(BUDGETS.values())),
    "timeline": ("And when would you like the work to start?", list(TIMELINES.values())),
}
REQUIRED = list(QUESTIONS)

SERVICE_AREAS = [
    "Baner", "Balewadi", "Aundh", "Pashan", "Wakad", "Hinjewadi", "Pimple Saudagar", "Kothrud", "Viman Nagar",
    "Kharadi", "Hadapsar", "Magarpatta", "Koregaon Park", "Kalyani Nagar", "Wagholi", "Undri", "NIBM",
    "Pimpri-Chinchwad", "Pimpri", "Chinchwad",
]
_AREA_ALIASES = {"kp": "Koregaon Park", "pcmc": "Pimpri-Chinchwad", "pimpri chinchwad": "Pimpri-Chinchwad"}

# ------------------------------------------------------------------ validators
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?|0)?([6-9]\d{4})[\s-]?(\d{5})(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def parse_phone(text: str) -> str | None:
    """Indian mobile number as +91XXXXXXXXXX, or None."""
    match = _PHONE.search(text or "")
    return f"+91{match.group(1)}{match.group(2)}" if match else None


def display_phone(phone: str) -> str:
    """+919876543210 -> +91 98765 43210"""
    return f"{phone[:3]} {phone[3:8]} {phone[8:]}" if len(phone) == 13 else phone


def parse_email(text: str) -> str | None:
    match = _EMAIL.search(text or "")
    return match.group(0).lower() if match else None


def _choice_by_label(text: str, choices: dict[str, str]) -> str | None:
    clean = (text or "").strip().lower()
    for key, label in choices.items():
        if clean == label.lower() or clean == key:
            return key
    return None


def match_area(text: str) -> str | None:
    lower = f" {(text or '').lower()} "
    for alias, area in _AREA_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            return area
    for area in sorted(SERVICE_AREAS, key=len, reverse=True):
        if area.lower() in lower:
            return "Pimpri-Chinchwad" if area in ("Pimpri", "Chinchwad") else area
    return None


def in_service_area(area: str | None) -> bool:
    return match_area(area or "") is not None


_LAKH = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|–|to)?\s*(\d+(?:\.\d+)?)?\s*(lakh|lakhs|lac|lacs|l\b|cr|crore|crores|k\b)",
                   re.IGNORECASE)
_RUPEES = re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]{5,})", re.IGNORECASE)


def parse_budget_rupees(text: str) -> int | None:
    """'8 lakh' -> 800000, '6-10 lakhs' -> 1000000 (upper end), '₹4,50,000' -> 450000."""
    text = text or ""
    match = _LAKH.search(text)
    if match:
        value = float(match.group(2) or match.group(1))
        unit = match.group(3).lower()
        factor = 10_000_000 if unit.startswith("cr") else 1_000 if unit == "k" else 100_000
        return int(value * factor)
    match = _RUPEES.search(text)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def budget_band(text: str) -> str | None:
    label = _choice_by_label(text, BUDGETS)
    if label:
        return label
    lower = (text or "").lower()
    amount = parse_budget_rupees(text)
    if amount is None:
        return None
    if re.search(r"\b(under|below|less than|upto|up to|max)\b", lower) and amount <= 300_000:
        return "under_3l"
    for limit, band in [(300_000, "under_3l"), (600_000, "3_6l"), (1_000_000, "6_10l"), (1_500_000, "10_15l")]:
        if amount < limit or (amount == limit and band != "under_3l"):
            return band
    return "above_15l"


def timeline_band(text: str) -> str | None:
    label = _choice_by_label(text, TIMELINES)
    if label:
        return label
    lower = (text or "").lower()
    if re.search(r"\b(asap|immediately|right away|this month|next week|within a month|in a month|2 weeks|two weeks|urgent)\b", lower):
        return "within_1m"
    match = re.search(r"\b(\d+|one|two|three|four|five|six)\s*(?:-|to)?\s*(?:\d+\s*)?months?\b", lower)
    if match:
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
        n = int(match.group(1)) if match.group(1).isdigit() else words[match.group(1)]
        return "within_1m" if n <= 1 else "1_3m" if n <= 3 else "3_6m" if n <= 6 else "later"
    if re.search(r"\bnext month\b", lower):
        return "1_3m"
    if re.search(r"\b(next year|not sure|just exploring|exploring|no hurry|later)\b", lower):
        return "later"
    return None


def project_type(text: str) -> str | None:
    label = _choice_by_label(text, PROJECT_TYPES)
    if label:
        return label
    lower = (text or "").lower()
    rules = [
        ("full_home", r"full (home|house|flat|apartment)|whole (home|house|flat)|entire (home|house|flat)|complete (home|house|flat)|\bvilla\b|\d\s?bhk (interior|home)|new flat"),
        ("kitchen", r"kitchen"),
        ("wardrobes", r"wardrobe|closet"),
        ("office", r"\boffice\b|\bshop\b|\bclinic\b|\bcaf[eé]\b|showroom"),
        ("single_room", r"bedroom|living room|kids'? room|study|home office|one room|two rooms|single room"),
    ]
    for key, pattern in rules:
        if re.search(pattern, lower):
            return key
    return None


def property_type(text: str) -> str | None:
    label = _choice_by_label(text, PROPERTIES)
    if label:
        return label
    lower = (text or "").lower()
    match = re.search(r"\b([1-9])\s?bhk\b", lower)
    if match:
        n = int(match.group(1))
        return f"{n}bhk" if n <= 3 else "4bhk_plus"
    if "villa" in lower or "bungalow" in lower:
        return "villa"
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


def normalise_fields(raw: dict) -> dict:
    """Keep only valid values. Used for both the AI's output and the parsers'."""
    out: dict = {}
    if raw.get("name"):
        name = clean_name(str(raw["name"]))
        if name:
            out["name"] = name
    if raw.get("phone"):
        phone = parse_phone(str(raw["phone"]))
        if phone:
            out["phone"] = phone
    if raw.get("email"):
        email = parse_email(str(raw["email"]))
        if email:
            out["email"] = email
    for key, choices in [("project_type", PROJECT_TYPES), ("property", PROPERTIES), ("budget", BUDGETS),
                         ("timeline", TIMELINES)]:
        if raw.get(key) in choices:
            out[key] = raw[key]
    if raw.get("area"):
        area = str(raw["area"]).strip()[:60]
        out["area"] = match_area(area) or area.title()
    return out
