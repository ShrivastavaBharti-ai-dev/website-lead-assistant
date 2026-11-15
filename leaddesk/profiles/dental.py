"""Profile: Amberwick Dental, a fictional private dental practice in Leeds.

The assistant answers questions about fees, treatments and opening hours, and
takes appointment requests for the reception team to confirm by phone.

It never gives dental or medical advice. A message that sounds like an urgent
problem (pain, swelling, bleeding, a knocked-out tooth) gets one fixed reply,
written here and chosen by plain code: where to get help now. The request is
then marked urgent so reception calls that person first.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..fields import (DAY_OR_TIME, choice_by_label, clean_name, parse_email, parse_name, plain, time_preference)
from ..fields import display_uk_phone as display_phone
from ..fields import parse_uk_phone as parse_phone
from ..qualify import Qualification

KEY = "dental"
BUSINESS = "Amberwick Dental"
DOCS = Path(__file__).resolve().parents[2] / "business" / KEY

# ------------------------------------------------------------------ what the assistant says
GREETING = ("Hi! I'm the AI assistant at Amberwick Dental. Ask me about our treatments, fees or opening hours, "
            "or request an appointment. In pain? Tell me and I'll show you how to get help quickly.")
GREETING_CHOICES = ["Request an appointment", "Are you taking new patients?", "I'm in pain"]
OFFER = "Would you like to request an appointment? I just need a few details."
OFFER_CHOICES = ["Request an appointment", "I have another question"]
NOT_FOUND = ("I can't answer that one. I'm an AI assistant, so I can't give dental or medical advice, and I won't "
             "guess. Our team can help if you call 0113 496 0456.")
HELP = "I can answer questions about our treatments, fees and opening hours, or take an appointment request for you."
AFTER_SUBMIT = "Your request is with our reception team; they'll call you to confirm. Anything else I can help with?"
CHAT_END = ("We've reached the end of this chat. Please call 0113 496 0456 or email "
            "hello@amberwickdental.example and our team will help.")
OFFER_TRIGGER = re.compile(r"\b(price|prices|cost|costs|how much|fees?|new patients?|register|whitening|implants?|"
                           r"straighten\w*|aligners?|braces|veneers?|bonding|appointments?|available)\b", re.IGNORECASE)
# "appointment" alone is not enough: "how much is an emergency appointment?" is a question, not a request.
WANTS = re.compile(r"\b(book|(request|make|need|want|like|get|have) an appointment|appointment please|register|join|"
                   r"sign up|see (a|the) dentist|call me|call back|callback|get started|interested|come in)\b",
                   re.IGNORECASE)

# The fixed reply to anything that sounds urgent. A person wrote it; the AI never changes it.
URGENT_REPLY = ("That sounds like it may need urgent care. I'm an AI assistant and can't give dental or medical advice, "
                "so please don't wait for a reply here. When we're open, call us on 0113 496 0456: we keep "
                "appointments free every weekday morning for urgent problems. When we're closed, call NHS 111. "
                "If you have swelling that makes it hard to breathe or swallow, bleeding that won't stop, or an injury "
                "to your face or head, call 999 or go to A&E now.")
_URGENT = re.compile(
    r"\b(tooth ?ache|in (a lot of |so much |severe |terrible |real |constant )?pain|agony|severe pain|unbearable|"
    r"excruciating|throbbing|abscess|swelling|swelled|swollen|bleeding|bleeds|knocked[- ]out|"
    r"knocked (a|my|his|her|their) tooth|(broken|broke|snapped|cracked) (a |my |his |her )?(tooth|teeth)|"
    r"tooth (has |is )?(broken|broke|snapped|cracked|fell out|fallen out|came out|come out)|infection|infected|pus|"
    r"emergency|urgent|urgently|can'?t (breathe|swallow|sleep|eat|open my mouth))\b|"
    # Knocks, falls and injuries, however the sentence is put together ("knocked her front tooth out").
    r"\bknock\w*\b[^.?!]{0,40}\b(tooth|teeth)\b|\b(tooth|teeth)\b[^.?!]{0,40}\bknock\w*\b|"
    r"\b(tooth|teeth)\b[^.?!]{0,25}\b(fell|fallen|came|come|pulled) out\b|"
    r"\b(fell|fall|fallen|accident|injur\w*|hit|punched|banged|bashed)\b[^.?!]{0,60}\b(tooth|teeth|mouth|jaw|face|lip)\b|"
    r"\b(tooth|teeth|mouth|jaw|face|lip)\b[^.?!]{0,60}\b(fell|fall|fallen|accident|injur\w*|punched|banged|bashed)\b",
    re.IGNORECASE)

# The fixed reply to a request for dental or medical advice that doesn't sound urgent.
ADVICE_REPLY = ("I can't help with that. I'm an AI assistant, so I can't give dental or medical advice. Please call us "
                "on 0113 496 0456 when we're open, or NHS 111 when we're closed, to speak to someone who can. "
                "If you'd like a dentist to have a look, I can take an appointment request.")
_ADVICE = re.compile(
    r"\b(painkillers?|ibuprofen|paracetamol|aspirin|antibiotics?|medication|medicine|tablets?|"
    r"is (it|this|that) (normal|serious|bad|safe)|should i (be )?worr\w*|what should i (do|take|use)|"
    r"what (can|do|should) i (take|use)|what do i do|what'?s wrong|lump|ulcers?|bleed|numb|numbness|diagnos\w*|"
    r"side effects?|home remed\w*)\b", re.IGNORECASE)


_URGENT_WORD = re.compile(r"\b(emergency|emergencies|urgent|urgently)\b", re.IGNORECASE)
_ABOUT_THE_SERVICE = re.compile(r"\b(how much|cost|costs|price|prices|fee|fees|charge|do you (have|offer|do)|"
                                r"opening|hours)\b", re.IGNORECASE)


def urgent(message: str) -> tuple[str, dict] | None:
    """A fixed reply for a message the AI must not answer: the urgent-care reply (with the details that mark
    the request urgent for reception), or the no-advice reply."""
    text = (message or "").replace("’", "'")
    # "How much is an emergency appointment?" asks about the service, and the documents answer it.
    if _ABOUT_THE_SERVICE.search(text) and not _URGENT.search(_URGENT_WORD.sub(" ", text)):
        return None
    if _URGENT.search(text):
        return URGENT_REPLY, {"reason": "problem", "urgent": "yes"}
    if _ADVICE.search(text):
        return ADVICE_REPLY, {}
    return None


# ------------------------------------------------------------------ choices
PATIENT_TYPES = {"new": "New patient", "existing": "Existing patient"}
REASONS = {
    "checkup": "Check-up",
    "hygienist": "Hygienist",
    "problem": "A problem with a tooth",
    "whitening": "Whitening or cosmetic",
    "straightening": "Teeth straightening",
    "implants": "Implants",
    "other": "Something else",
}
VISIT_TIMES = {"weekday_morning": "Weekday morning", "weekday_afternoon": "Weekday afternoon",
               "saturday_morning": "Saturday morning"}


# ------------------------------------------------------------------ questions
QUESTIONS = {
    "name": ("So our reception team can call you, may I have your name?", []),
    "phone": ("Thanks, {name}. What's the best phone number to reach you on? "
              "We'll only use it about your appointment.", []),
    "patient_type": ("Have you been to Amberwick Dental before?", list(PATIENT_TYPES.values())),
    "reason": ("What would you like the appointment for?", list(REASONS.values())),
    "visit_time": ("When would suit you best? Tap one, or type a day and time. We're closed on Sundays.",
                   list(VISIT_TIMES.values())),
}


def required(lead: dict) -> list[str]:
    """The details to collect, in the order to ask. Every visitor gets the same questions here."""
    return list(QUESTIONS)


def question(field: str, lead: dict) -> tuple[str, list[str]]:
    return QUESTIONS[field]


# ------------------------------------------------------------------ validators
def patient_type(text: str, was_asked: bool = False) -> str | None:
    text = text or ""
    label = choice_by_label(text, PATIENT_TYPES)
    if label:
        return label
    lower = text.lower().replace("’", "'")
    if re.search(r"\b(new patients?|never been|first time|first visit|not registered|not a patient|"
                 r"looking for a (new )?dentist|register|join)\b", lower):
        return "new"
    if re.search(r"\b(existing patient|already (a patient|registered|with you)|i'?m a patient|been (coming|with you)|"
                 r"my usual dentist|regular patient)\b", lower):
        return "existing"
    if was_asked:
        if re.search(r"\b(no|nope|never|new|first)\b", lower):
            return "new"
        if re.search(r"\b(yes|yeah|yep|existing|already|before)\b", lower):
            return "existing"
    return None


def reason(text: str) -> str | None:
    """The kind of appointment, as one of the buttons. We record the category only, never symptoms."""
    text = text or ""
    label = choice_by_label(text, REASONS)
    if label:
        return label
    lower = text.lower()
    rules = [
        ("implants", r"\bimplants?\b|\bmissing (tooth|teeth)\b"),
        ("straightening", r"\b(straighten\w*|aligners?|braces|crooked)\b"),
        ("whitening", r"\b(whiten\w*|veneers?|bonding|cosmetic|smile makeover)\b"),
        ("problem", r"\b(filling|fillings|crown|chipped|sensitive|sensitivity|wisdom tooth|wisdom teeth|sore|hurts|"
                    r"hurting|painful|ache|aching|loose tooth|problem with)\b"),
        ("hygienist", r"\b(hygienist|hygiene|scale and polish|clean|cleaning)\b"),
        ("checkup", r"\b(check[- ]?up|examination|exam)\b"),
    ]
    if (urgent(text) or ("",))[0] == URGENT_REPLY:
        return "problem"
    return next((key for key, pattern in rules if re.search(pattern, lower)), None)


def visit_time(text: str, was_asked: bool = False) -> str | None:
    """One of the buttons, or (only when we asked) the visitor's own words, like 'Tuesday after 3'."""
    value = time_preference(text, was_asked, VISIT_TIMES, [
        ("saturday_morning", r"\b(saturdays?|sat|weekends?)\b"),
        ("weekday_afternoon", r"\b(afternoons?|after lunch|after school|after [1-4]|[1-4] ?pm)\b"),
        ("weekday_morning", r"\b(mornings?|weekdays?|(mon|tues|wednes|thurs|fri)days?)\b"),
    ], context=r"\b(appointment|book|come in|free on|free at|best|suits?|prefer\w*|call me)\b")
    # "Whitening", typed when we asked for a time, answers a different question: ask again.
    if value and value not in VISIT_TIMES and (reason(value) or patient_type(value)):
        return None
    return value


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
    for key, choices in [("patient_type", PATIENT_TYPES), ("reason", REASONS)]:
        if raw.get(key) in choices:
            out[key] = raw[key]
    if raw.get("visit_time"):
        value = str(raw["visit_time"])
        value = value if value in VISIT_TIMES else plain(value)
        if value:
            out["visit_time"] = value
    return out


def rule_fields(message: str, asked: str | None) -> dict:
    """Appointment details found in one message by plain rules (no AI)."""
    found: dict = {}
    if phone := parse_phone(message):
        found["phone"] = phone
    if email := parse_email(message):
        found["email"] = email
    name = parse_name(message, asked == "name")
    # "Saturday morning" or "Check-up", typed while we wait for the name, is an answer to something else.
    if name and not (DAY_OR_TIME.search(name) or reason(name) or patient_type(name)):
        found["name"] = name
    if kind := patient_type(message, asked == "patient_type"):
        found["patient_type"] = kind
    if why := reason(message):
        found["reason"] = why
    if when := visit_time(message, asked == "visit_time"):
        found["visit_time"] = when
    return normalise_fields(found)


# ------------------------------------------------------------------ AI extraction
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "phone": {"type": "string"},
        "email": {"type": "string"},
        "patient_type": {"type": "string", "enum": [*PATIENT_TYPES, "none"]},
        "reason": {"type": "string", "enum": [*REASONS, "none"]},
        "visit_time": {"type": "string", "description": "weekday_morning, weekday_afternoon, saturday_morning, or "
                                                         "the visitor's own day and time in a few words"},
        "question": {"type": "string"},
        "wants_consultation": {"type": "boolean"},
    },
    "required": ["name", "phone", "email", "patient_type", "reason", "visit_time", "question", "wants_consultation"],
}

EXTRACT_PROMPT = """You read one chat message from a visitor on the website of a private dental practice in Leeds, UK.
Extract ONLY details stated in this message. Use "" or "none" for anything not stated. Never guess.
- patient_type: new (has not been to this practice before, or wants to register) or existing.
- reason: the kind of appointment, as one category: checkup, hygienist, problem (toothache, a broken or lost filling,
  anything wrong with a tooth or the gums), whitening (whitening, veneers, bonding, cosmetic), straightening
  (aligners, braces), implants, other. Record the category only: never copy symptoms or medical details.
- visit_time: when they would like to come in.
- A short reply usually answers the assistant's last question (shown below).
- question: if the visitor asks something about the practice (fees, treatments offered, opening hours, new patients,
  parking, payment, the membership plan), rewrite it as one standalone question in English; otherwise "".
  A request for dental or medical advice (what to take, what is wrong, whether something is serious) is not a
  question for this field: leave it "".
- wants_consultation: true if they ask to book or request an appointment, register, or be called back."""

# ------------------------------------------------------------------ scoring
# Plain code, so the practice can see and change exactly whom reception calls first.
NEW_PATIENT_POINTS = {"implants": 90, "straightening": 90, "problem": 75, "whitening": 65, "checkup": 60,
                      "hygienist": 60, "other": 50}
HOT = 70


def qualify(lead: dict) -> Qualification:
    """Hot means "call first": anything urgent, and new patients for higher-value treatment. Nobody is cold:
    every request is from someone who wants an appointment."""
    kind, why = lead.get("patient_type"), lead.get("reason")
    reasons = [PATIENT_TYPES.get(kind, ""), REASONS.get(why, "")]
    if lead.get("urgent"):
        return Qualification("hot", 100, ["Possible urgent problem: call first", *filter(None, reasons)])
    score = NEW_PATIENT_POINTS.get(why, 50) if kind == "new" else 45
    return Qualification("hot" if score >= HOT else "warm", score, [r for r in reasons if r])


# ------------------------------------------------------------------ the saved request
LEAD_HEADER = ["Name", "Phone", "Email", "Patient", "Appointment for", "Urgent", "Best time"]


def _visit_label(lead: dict) -> str:
    return VISIT_TIMES.get(lead.get("visit_time"), lead.get("visit_time") or "")


def lead_columns(lead: dict) -> list:
    return [
        lead.get("name", ""), lead.get("phone", ""), lead.get("email", ""),
        PATIENT_TYPES.get(lead.get("patient_type"), ""), REASONS.get(lead.get("reason"), ""),
        "YES" if lead.get("urgent") else "", _visit_label(lead),
    ]


def hot_lead_alert(lead: dict, why: str) -> dict:
    """The email sent to reception about a request to call first."""
    kind = "URGENT" if lead.get("urgent") else "Call first"
    details = [(label, value) for label, value in zip(LEAD_HEADER, lead_columns(lead)) if value] + [("Why", why)]
    return {"subject": f"{kind}: {lead.get('name')} - {REASONS.get(lead.get('reason'), 'appointment request')}",
            "body": "\n".join(f"{label}: {value}" for label, value in details)}


def thanks(lead: dict, result: Qualification) -> str:
    """What the visitor is told once their request is saved."""
    first = lead.get("name", "").split(" ")[0]
    phone, when = display_phone(lead.get("phone", "")), _visit_label(lead)
    when = when.lower() if lead.get("visit_time") in VISIT_TIMES else when
    if lead.get("urgent"):
        return (f"Thank you, {first}. I've marked your request as urgent, and our reception team will call you on "
                f"{phone} as soon as the practice is open. If it gets worse before then, call NHS 111.")
    return (f"Thank you, {first}! Our reception team will call you on {phone} during opening hours to confirm "
            f"your appointment. I've noted that this suits you best: {when}.")
