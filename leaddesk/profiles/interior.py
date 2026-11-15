"""Profile: Terracotta Lane Interiors, a fictional interior design studio in Pune.

Everything specific to this business: the questions and answer choices, the
parsers for how people type things in India ("8 lakh", "98765 43210",
"in 2 months"), the service areas, the lead scoring, and every sentence the
assistant says. The AI extractor's output is always re-validated here.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..fields import choice_by_label, clean_name, parse_email, parse_name
from ..qualify import Qualification

KEY = "interior"
BUSINESS = "Terracotta Lane Interiors"
DOCS = Path(__file__).resolve().parents[2] / "business" / KEY

# ------------------------------------------------------------------ what the assistant says
GREETING = ("Hi! I'm the assistant at Terracotta Lane Interiors. Ask me about our services, prices or timelines, "
            "or book a free design consultation.")
GREETING_CHOICES = ["Book a free consultation", "How much does a 2 BHK cost?", "Which areas do you cover?"]
OFFER = "Would you like a free 45-minute design consultation? I just need a few details."
OFFER_CHOICES = ["Book a free consultation", "I have another question"]
NOT_FOUND = "I'm not sure about that one, so I won't guess. Our designer can answer it on a call."
HELP = "I can answer questions about our services, prices and timelines, or book a free consultation for you."
AFTER_SUBMIT = "Your request is with our design team; they'll call you soon. Anything else I can help with?"
CHAT_END = ("We've reached the end of this chat. Please email hello@terracottalane.example and our team will help.")
# A question matching this makes the assistant offer a consultation straight away.
OFFER_TRIGGER = re.compile(r"\b(price|prices|cost|costs|quote|estimate|budget|charges|fee|fees|how much)\b", re.I)
# A message matching this starts collecting the visitor's details.
WANTS = re.compile(r"\b(book|consult|consultation|call me|call back|callback|site visit|visit|quote|quotation|"
                   r"estimate|meet|appointment|get started|start my project|interested)\b", re.IGNORECASE)

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


def parse_phone(text: str) -> str | None:
    """Indian mobile number as +91XXXXXXXXXX, or None."""
    match = _PHONE.search(text or "")
    return f"+91{match.group(1)}{match.group(2)}" if match else None


def display_phone(phone: str) -> str:
    """+919876543210 -> +91 98765 43210"""
    return f"{phone[:3]} {phone[3:8]} {phone[8:]}" if len(phone) == 13 else phone


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
    label = choice_by_label(text, BUDGETS)
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
    label = choice_by_label(text, TIMELINES)
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
    label = choice_by_label(text, PROJECT_TYPES)
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
    label = choice_by_label(text, PROPERTIES)
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


def rule_fields(message: str, asked: str | None) -> dict:
    """Lead details found in one message by plain rules (no AI)."""
    found: dict = {}
    if phone := parse_phone(message):
        found["phone"] = phone
    if email := parse_email(message):
        found["email"] = email
    if name := parse_name(message, asked == "name"):
        found["name"] = name
    if project := project_type(message):
        found["project_type"] = project
    if prop := property_type(message):
        found["property"] = prop
    if budget := budget_band(message):
        found["budget"] = budget
    if timeline := timeline_band(message):
        found["timeline"] = timeline
    if area := match_area(message):
        found["area"] = area
    elif asked == "area" and "?" not in message and len(message.split()) <= 6 and not found:
        found["area"] = message.strip(" .!")
    return normalise_fields(found)


# ------------------------------------------------------------------ AI extraction
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "phone": {"type": "string"},
        "email": {"type": "string"},
        "project_type": {"type": "string", "enum": [*PROJECT_TYPES, "none"]},
        "property": {"type": "string", "enum": [*PROPERTIES, "none"]},
        "area": {"type": "string", "description": "Locality or city of the property"},
        "budget": {"type": "string", "enum": [*BUDGETS, "none"]},
        "timeline": {"type": "string", "enum": [*TIMELINES, "none"]},
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

# ------------------------------------------------------------------ scoring
# Plain code, so the owner can see and change exactly how leads are ranked.
BUDGET_POINTS = {"under_3l": 5, "3_6l": 20, "6_10l": 30, "10_15l": 35, "above_15l": 40}
TIMELINE_POINTS = {"within_1m": 25, "1_3m": 20, "3_6m": 10, "later": 0}
PROJECT_POINTS = {"full_home": 15, "kitchen": 10, "office": 10, "wardrobes": 5, "single_room": 5, "other": 0}
HOT, WARM = 70, 45


def qualify(lead: dict) -> Qualification:
    reasons: list[str] = []
    if not in_service_area(lead.get("area")):
        return Qualification("cold", 0, [f"Outside the service area ({lead.get('area') or 'unknown'})"])

    score = 20  # inside the service area
    budget, timeline, project = lead.get("budget"), lead.get("timeline"), lead.get("project_type")
    score += BUDGET_POINTS.get(budget, 0)
    score += TIMELINE_POINTS.get(timeline, 0)
    score += PROJECT_POINTS.get(project, 0)
    if budget:
        reasons.append(f"Budget {BUDGETS[budget]}")
    if timeline:
        reasons.append(f"Wants to start {TIMELINES[timeline].lower()}")
    if project:
        reasons.append(PROJECT_TYPES[project])
    if project == "full_home" and budget in ("under_3l", "3_6l"):
        score -= 15
        reasons.append("Budget may be low for a full home (a 2 BHK is usually ₹6–10 lakh)")
    if budget == "under_3l" and project not in ("kitchen", "wardrobes", "single_room"):
        reasons.append("Close to the ₹1.5 lakh minimum project value")
    temperature = "hot" if score >= HOT else "warm" if score >= WARM else "cold"
    return Qualification(temperature, max(0, min(100, score)), reasons)


# ------------------------------------------------------------------ the saved lead
# Columns for this business, between "Received" and the score columns every profile shares.
LEAD_HEADER = ["Name", "Phone", "Email", "Project", "Property", "Area", "In service area", "Budget", "Timeline"]


def lead_columns(lead: dict) -> list:
    return [
        lead.get("name", ""), lead.get("phone", ""), lead.get("email", ""),
        PROJECT_TYPES.get(lead.get("project_type"), ""), PROPERTIES.get(lead.get("property"), ""),
        lead.get("area", ""), "yes" if in_service_area(lead.get("area")) else "no",
        BUDGETS.get(lead.get("budget"), ""), TIMELINES.get(lead.get("timeline"), ""),
    ]


def hot_lead_alert(lead: dict, why: str) -> dict:
    """The email sent to the owner about a hot lead."""
    project = PROJECT_TYPES.get(lead.get("project_type"), "")
    details = [("Name", lead.get("name", "")), ("Phone", lead.get("phone", "")), ("Project", project),
               ("Area", lead.get("area", "")), ("Budget", BUDGETS.get(lead.get("budget"), "")),
               ("Timeline", TIMELINES.get(lead.get("timeline"), "")), ("Why", why)]
    return {"subject": f"Hot lead: {lead.get('name')} - {project} in {lead.get('area')}",
            "body": "\n".join(f"{label}: {value}" for label, value in details)}


def thanks(lead: dict, result: Qualification) -> str:
    """What the visitor is told once their details are saved."""
    first = lead.get("name", "").split(" ")[0]
    if result.temperature == "cold" and not in_service_area(lead.get("area")):
        return (f"Thank you, {first}. We only take projects in the Pune region, so we may not be able to help "
                "with this one, but I've passed your details to the team and they'll get back to you.")
    return (f"Thank you, {first}! I've passed your details to our design team. They'll call you on "
            f"{display_phone(lead.get('phone', ''))} during studio hours (Tuesday to Sunday, 10 am to 7 pm) to fix a time "
            "for your free consultation.")
