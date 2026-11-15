"""Profile: Harbour & Finch Estate Agents, a fictional estate and letting agency in Bristol.

Four kinds of visitor, each asked only what matters for them:

    buy       area, budget, buying position, when they can view
    rent      area, monthly rent, move-in date, when they can view
    sell      where the property is, when a valuer can visit
    let_out   the same, for landlords

Sellers and landlords are the leads an agency values most, so they are always
hot. A buyer who has to sell first is also hot: that is a valuation to win.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..fields import choice_by_label, clean_name, parse_email, parse_name
from ..qualify import Qualification

KEY = "estate"
BUSINESS = "Harbour & Finch Estate Agents"
DOCS = Path(__file__).resolve().parents[2] / "business" / KEY

# ------------------------------------------------------------------ what the assistant says
GREETING = ("Hi! I'm the AI assistant at Harbour & Finch Estate Agents. Ask me about our properties for sale "
            "or to rent, or book a viewing or a free valuation.")
GREETING_CHOICES = ["Book a viewing", "Get a free valuation", "What are your selling fees?"]
OFFER = "Would you like to book a viewing or a free valuation? I just need a few details."
OFFER_CHOICES = ["Book a viewing", "Get a free valuation", "I have another question"]
NOT_FOUND = "I'm not sure about that one, so I won't guess. One of our team can answer it on a call."
HELP = "I can answer questions about our properties, fees and viewings, or book a viewing or a free valuation for you."
AFTER_SUBMIT = "Your details are with our team; they'll call you soon. Anything else I can help with?"
CHAT_END = ("We've reached the end of this chat. Please call 0117 496 0123 or email "
            "hello@harbourandfinch.example and our team will help.")
OFFER_TRIGGER = re.compile(r"\b(price|how much|fees?|cost|costs|available|view|viewing|viewings|valuation|worth|deposit)\b",
                           re.IGNORECASE)
WANTS = re.compile(r"\b(book|viewing|view it|view the|see it|see the|arrange|valuation|valued|call me|call back|"
                   r"callback|appointment|register|interested|get started|value (it|my|our)|come (and|to) value|come round|"
                   r"come out)\b", re.IGNORECASE)

# ------------------------------------------------------------------ choices
INTERESTS = {"buy": "Buy", "rent": "Rent", "sell": "Sell my property", "let_out": "Let my property"}
BUY_BUDGETS = {
    "buy_under_200k": "Under £200,000",
    "buy_200_300k": "£200,000–£300,000",
    "buy_300_450k": "£300,000–£450,000",
    "buy_450_650k": "£450,000–£650,000",
    "buy_above_650k": "Above £650,000",
}
RENT_BUDGETS = {
    "rent_under_1000": "Under £1,000 pcm",
    "rent_1000_1500": "£1,000–£1,500 pcm",
    "rent_1500_2200": "£1,500–£2,200 pcm",
    "rent_above_2200": "Above £2,200 pcm",
}
BUDGETS = {**BUY_BUDGETS, **RENT_BUDGETS}
POSITIONS = {"cash": "Cash buyer", "aip": "Mortgage agreed in principle", "sell_first": "Need to sell first",
             "not_yet": "Not arranged yet"}
MOVE_INS = {"within_1m": "Within a month", "1_3m": "1–3 months", "later": "Later / just looking"}
VISIT_TIMES = {"weekday_day": "Weekday daytime", "weekday_evening": "Weekday evening", "saturday": "Saturday"}

SERVICE_AREAS = [
    "Clifton", "Redland", "Cotham", "Bishopston", "Horfield", "Henleaze", "Westbury-on-Trym", "Southville",
    "Bedminster", "Totterdown", "Knowle", "Hotwells", "Harbourside", "Montpelier", "St Andrews", "Easton",
    "Fishponds",
]
_AREA_ALIASES = {"westbury on trym": "Westbury-on-Trym", "wot": "Westbury-on-Trym", "st andrew's": "St Andrews",
                 "saint andrews": "St Andrews", "the harbourside": "Harbourside"}


# ------------------------------------------------------------------ questions
def required(lead: dict) -> list[str]:
    """The details to collect, in the order to ask. What comes after `interest` depends on its answer."""
    after = {"buy": ["area", "budget", "position", "visit_time"],
             "rent": ["area", "budget", "move_in", "visit_time"],
             "sell": ["area", "visit_time"],
             "let_out": ["area", "visit_time"]}
    return ["name", "phone", "interest", *after.get(lead.get("interest"), [])]


def question(field: str, lead: dict) -> tuple[str, list[str]]:
    owner = lead.get("interest") in ("sell", "let_out")   # they have a property, rather than wanting one
    renting = lead.get("interest") == "rent"
    times = list(VISIT_TIMES.values())
    return {
        "name": ("Happy to help. May I have your name?", []),
        "phone": ("Thanks, {name}! What's the best phone number to reach you on? "
                  "We'll only use it about your enquiry.", []),
        "interest": ("Are you looking to buy or rent, or do you have a property to sell or let?",
                     list(INTERESTS.values())),
        "area": ("Which part of Bristol is your property in?" if owner
                 else "Which part of Bristol would you like to live in?", []),
        "budget": ("What monthly rent are you looking at?", list(RENT_BUDGETS.values())) if renting
        else ("What's your budget?", list(BUY_BUDGETS.values())),
        "position": ("How will you be buying?", list(POSITIONS.values())),
        "move_in": ("When would you like to move in?", list(MOVE_INS.values())),
        "visit_time": ("When would suit you for the valuation visit? Tap one, or type a day and time. "
                       "We're closed on Sundays." if owner
                       else "When are you usually free for viewings? Tap one, or type a day and time. "
                       "We're closed on Sundays.", times),
    }[field]


# ------------------------------------------------------------------ validators
# UK numbers: 0 or +44, then ten digits starting 1, 2, 3 (landlines) or 7 (mobiles).
_PHONE = re.compile(r"(?<![\d£,.])(?:\+?44[\s-]?(?:\(0\)[\s-]?)?|0)([1237](?:[\s-]?\d){9})(?!\d)")


def parse_phone(text: str) -> str | None:
    """UK phone number as +44XXXXXXXXXX, or None."""
    match = _PHONE.search(text or "")
    return "+44" + re.sub(r"\D", "", match.group(1)) if match else None


def display_phone(phone: str) -> str:
    """+447700900123 -> 07700 900123"""
    return f"0{phone[3:7]} {phone[7:]}" if len(phone) == 13 else phone


def match_area(text: str) -> str | None:
    """A Bristol area we cover; plain "Bristol" counts too. None for anywhere else."""
    lower = (text or "").lower().replace("’", "'")
    for alias, area in _AREA_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            return area
    for area in sorted(SERVICE_AREAS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(area.lower())}\b", lower):   # whole words: "Knowle", not "knowledge"
            return area
    return "Bristol" if re.search(r"\bbristol\b", lower) else None


def in_service_area(area: str | None) -> bool:
    return match_area(area or "") is not None


_MONEY = re.compile(r"(£\s*)?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(\s?k\b|m\b|\s?million\b|\s?thousand\b)?"
                    r"(\s*(?:pcm|pm|p/m|per calendar month|per month|a month|/month)\b)?", re.IGNORECASE)


def parse_budget_pounds(text: str, was_asked: bool = False) -> int | None:
    """'£350k' -> 350000, '300-350k' -> 350000 (upper end), '£1,200 pcm' -> 1200.
    A bare number only counts if we just asked for the budget, or it is clearly a price (50,000 or more)."""
    amounts = []
    for pound, number, unit, monthly in _MONEY.findall(_PHONE.sub(" ", text or "")):
        unit = unit.strip().lower()
        value = float(number.replace(",", "")) * (1_000 if unit in ("k", "thousand") else
                                                  1_000_000 if unit in ("m", "million") else 1)
        if pound or unit or monthly or was_asked or value >= 50_000:
            amounts.append(int(value))
    return max(amounts) if amounts else None


def budget_band(text: str, was_asked: bool = False) -> str | None:
    label = choice_by_label(text, BUDGETS)
    if label:
        return label
    amount = parse_budget_pounds(text, was_asked)
    if amount is None or amount < 300:
        return None
    # ponytail: sale or rent is told apart by size alone, so a buyer typing "350" for £350k is read as rent.
    # The buttons avoid it; pass the visitor's interest in here if it shows up in real chats.
    if amount >= 50_000:
        bands = [(200_000, "buy_under_200k"), (300_000, "buy_200_300k"), (450_000, "buy_300_450k"),
                 (650_000, "buy_450_650k")]
        top = "buy_above_650k"
    else:
        bands = [(1_000, "rent_under_1000"), (1_500, "rent_1000_1500"), (2_200, "rent_1500_2200")]
        top = "rent_above_2200"
    return next((band for limit, band in bands if amount <= limit), top)


_BUY = re.compile(r"\b(buy|buying|purchase|purchasing|first[- ]time buyer|mortgage|cash buyer)\b", re.I)
_SELL = re.compile(r"\b(sell|selling|valuation|valued|market appraisal)\b|\bvalue (my|our)\b|"
                   r"\b(my|our)\b[^.?!]*\bworth\b", re.I)
_LET_OUT = re.compile(r"\blandlord\b|\b(let|letting|rent|renting) (out )?(my|our)\b|\brent(ing)? (it |them )?out\b|"
                      r"\btenants? for (my|our)\b", re.I)
_RENT = re.compile(r"\b(rent|renting|rental|to let|tenancy|pcm)\b|\bper month\b", re.I)
_SELL_FIRST = re.compile(r"\bsell\b[^.?!]*\b(first|before)\b", re.I)


def _has_to_sell_first(text: str) -> bool:
    """A buyer with a home to sell: 'need to sell first', or buying and selling 'my/our' place in one message."""
    return bool(_SELL_FIRST.search(text) or
                (_SELL.search(text) and _BUY.search(text) and re.search(r"\b(my|our)\b", text, re.I)))


def interest(text: str) -> str | None:
    text = text or ""
    label = choice_by_label(text, INTERESTS)
    if label:
        return label
    if _has_to_sell_first(text):
        return "buy"
    for key, pattern in (("let_out", _LET_OUT), ("sell", _SELL), ("rent", _RENT), ("buy", _BUY)):
        if pattern.search(text):
            return key
    return None


def position(text: str, was_asked: bool = False) -> str | None:
    text = text or ""
    label = choice_by_label(text, POSITIONS)
    if label:
        return label
    if _has_to_sell_first(text):
        return "sell_first"
    if re.search(r"\bcash\b", text, re.I):
        return "cash"
    if re.search(r"\b(agreement|decision|agreed|approved|mortgage) in principle\b|\b(aip|dip)\b|"
                 r"\bmortgage (is )?(approved|agreed|in place|offer|sorted|arranged)\b", text, re.I):
        return "aip"
    if was_asked and re.search(r"\b(not yet|haven't|have not|no mortgage|not arranged|need a mortgage|no)\b", text, re.I):
        return "not_yet"
    return None


def move_in(text: str, was_asked: bool = False) -> str | None:
    text = text or ""
    label = choice_by_label(text, MOVE_INS)
    if label:
        return label
    lower = text.lower()
    # "minimum tenancy 12 months?" is not a move-in date: outside our own question, require a word about moving.
    if not was_asked and not re.search(r"\b(move|moving|need (it|a place|somewhere)|start(ing)?)\b", lower):
        return None
    if re.search(r"\b(asap|immediately|right away|straight away|now|this month|next week|within a month|in a month|"
                 r"2 weeks|two weeks|urgent)\b", lower):
        return "within_1m"
    match = re.search(r"\b(\d+|one|two|three|four|five|six)\s*(?:-|to)?\s*(?:\d+\s*)?months?\b", lower)
    if match:
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
        n = int(match.group(1)) if match.group(1).isdigit() else words[match.group(1)]
        return "within_1m" if n <= 1 else "1_3m" if n <= 3 else "later"
    if re.search(r"\bnext month\b", lower):
        return "1_3m"
    if re.search(r"\b(next year|not sure|just looking|no rush|no hurry|later)\b", lower):
        return "later"
    return None


_DAY_OR_TIME = re.compile(r"\b((mon|tues|wednes|thurs|fri|satur|sun)days?|mornings?|afternoons?|evenings?|"
                          r"weekends?|weekdays?)\b", re.IGNORECASE)


def _plain(text: str, limit: int = 60) -> str:
    """Free text kept for the team: short, and never starting like a spreadsheet formula."""
    return " ".join(str(text).split())[:limit].lstrip("=+-@ ").strip(" .!")


def visit_time(text: str, was_asked: bool = False) -> str | None:
    """One of the buttons, or (only when we asked) the visitor's own words, like 'Tuesday after 5'."""
    # "ok saturday then" is just "Saturday".
    text = re.sub(r"\b(ok|okay|yes|yeah|sure|then|maybe|probably|please|i think|let's say)\b", " ", text or "",
                  flags=re.IGNORECASE)
    text = " ".join(text.split()).strip(" ,.!")
    label = choice_by_label(text, VISIT_TIMES)
    if label:
        return label
    lower = text.lower()
    if not was_asked and not re.search(r"\b(view|viewing|viewings|valuation|appointment|visit|free on|free at)\b", lower):
        return None
    for key, pattern in (("saturday", r"\b(saturdays?|sat|weekends?)\b"),
                         ("weekday_evening", r"\b(evenings?|after work|after [4-7]|[5-7] ?pm)\b"),
                         ("weekday_day", r"\b(mornings?|afternoons?|daytime|lunchtime|weekdays?|"
                                         r"(mon|tues|wednes|thurs|fri)days?)\b")):
        if re.search(pattern, lower):
            # A named day and time ("Tuesday after 5") is more useful to the team than the band.
            return _plain(text) if was_asked and len(text.split()) <= 8 and "?" not in text and len(text) > 12 else key
    if was_asked and "?" not in text and len(text.split()) <= 8:
        return _plain(text) or None
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
    for key, choices in [("interest", INTERESTS), ("budget", BUDGETS), ("position", POSITIONS), ("move_in", MOVE_INS)]:
        if raw.get(key) in choices:
            out[key] = raw[key]
    if raw.get("visit_time"):
        value = str(raw["visit_time"])
        value = value if value in VISIT_TIMES else _plain(value)
        if value:
            out["visit_time"] = value
    if raw.get("area"):
        area = _plain(raw["area"])
        if area:
            out["area"] = match_area(area) or area.title()
    return out


def rule_fields(message: str, asked: str | None) -> dict:
    """Lead details found in one message by plain rules (no AI)."""
    found: dict = {}
    if phone := parse_phone(message):
        found["phone"] = phone
    if email := parse_email(message):
        found["email"] = email
    text = _PHONE.sub(" ", message)   # so a phone number is never read as a budget
    name = parse_name(message, asked == "name")
    # "Fishponds" or "Thursday morning", typed while we wait for the name, is an answer to something else.
    if name and not (match_area(name) == name or _DAY_OR_TIME.search(name)):
        found["name"] = name
    if wants := interest(text):
        found["interest"] = wants
    if buying := position(text, asked == "position"):
        found["position"] = buying
    if budget := budget_band(text, asked == "budget"):
        found["budget"] = budget
    if moving := move_in(text, asked == "move_in"):
        found["move_in"] = moving
    if area := match_area(text):
        found["area"] = area
    elif asked == "area" and "?" not in message and len(message.split()) <= 6 and not found:
        found["area"] = message
    if when := visit_time(text, asked == "visit_time"):
        found["visit_time"] = when
    return normalise_fields(found)


# ------------------------------------------------------------------ AI extraction
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "phone": {"type": "string"},
        "email": {"type": "string"},
        "interest": {"type": "string", "enum": [*INTERESTS, "none"]},
        "area": {"type": "string", "description": "Area of Bristol, or the town or city if elsewhere"},
        "budget": {"type": "string", "enum": [*BUDGETS, "none"]},
        "position": {"type": "string", "enum": [*POSITIONS, "none"]},
        "move_in": {"type": "string", "enum": [*MOVE_INS, "none"]},
        "visit_time": {"type": "string", "description": "weekday_day, weekday_evening, saturday, or the visitor's "
                                                         "own day and time in a few words"},
        "question": {"type": "string"},
        "wants_consultation": {"type": "boolean"},
    },
    "required": ["name", "phone", "email", "interest", "area", "budget", "position", "move_in", "visit_time",
                 "question", "wants_consultation"],
}

EXTRACT_PROMPT = """You read one chat message from a visitor on the website of an estate and letting agency in Bristol, UK.
Extract ONLY details stated in this message. Use "" or "none" for anything not stated. Never guess.
- interest: buy (wants to buy a home), rent (wants to rent a home), sell (has a property to sell or wants a valuation),
  let_out (a landlord who wants to let their property). Someone buying who must sell their current home first is "buy".
- budget, when buying: buy_under_200k, buy_200_300k, buy_300_450k, buy_450_650k, buy_above_650k. "£350k" -> buy_300_450k.
- budget, when renting (per month): rent_under_1000, rent_1000_1500, rent_1500_2200, rent_above_2200.
- A range -> use its upper end. An amount exactly on a boundary belongs to the lower band (£300,000 -> buy_200_300k).
- position (buyers only): cash, aip (mortgage agreed in principle), sell_first (must sell their home first), not_yet.
- move_in (renters only): within_1m, 1_3m, later (more than 3 months, or just looking).
- visit_time: when they can come to a viewing or have a valuer visit.
- area: where they want to live, or where the property they are selling or letting is.
- A short reply usually answers the assistant's last question (shown below).
- question: if the visitor asks something about the agency or its properties (prices, rooms, parking, fees, viewings,
  deposits, pets, areas), rewrite it as one standalone question in English; otherwise "".
- wants_consultation: true if they ask to book a viewing, get a valuation, be called back or register interest."""

# ------------------------------------------------------------------ scoring
# Plain code, so the agency can see and change exactly how leads are ranked.
BUY_BUDGET_POINTS = {"buy_under_200k": 10, "buy_200_300k": 20, "buy_300_450k": 25, "buy_450_650k": 30,
                     "buy_above_650k": 30}
POSITION_POINTS = {"cash": 35, "aip": 30, "sell_first": 25, "not_yet": 5}
RENT_BUDGET_POINTS = {"rent_under_1000": 15, "rent_1000_1500": 25, "rent_1500_2200": 30, "rent_above_2200": 30}
MOVE_IN_POINTS = {"within_1m": 35, "1_3m": 25, "later": 0}
HOT, WARM = 70, 45


def qualify(lead: dict) -> Qualification:
    wants, area = lead.get("interest"), lead.get("area")
    if not in_service_area(area):
        return Qualification("cold", 0, [f"Outside Bristol ({area or 'unknown'})"])
    if wants in ("sell", "let_out"):
        return Qualification("hot", 90, [f"Wants a valuation to {'sell' if wants == 'sell' else 'let'} in {area}"])

    score = 20  # inside the area we cover
    reasons = [INTERESTS.get(wants, "")] if wants else []
    budget = lead.get("budget")
    if wants == "buy":
        score += BUY_BUDGET_POINTS.get(budget, 0) + POSITION_POINTS.get(lead.get("position"), 0)
        if lead.get("position"):
            reasons.append(POSITIONS[lead["position"]])
        if lead.get("position") == "sell_first":
            score = max(score, HOT)
            reasons.append("Has a property to sell: offer a valuation")
    else:
        score += RENT_BUDGET_POINTS.get(budget, 0) + MOVE_IN_POINTS.get(lead.get("move_in"), 0)
        if lead.get("move_in"):
            reasons.append(f"Wants to move {MOVE_INS[lead['move_in']].lower()}")
    if budget:
        reasons.append(f"Budget {BUDGETS[budget]}")
    temperature = "hot" if score >= HOT else "warm" if score >= WARM else "cold"
    return Qualification(temperature, max(0, min(100, score)), reasons)


# ------------------------------------------------------------------ the saved lead
LEAD_HEADER = ["Name", "Phone", "Email", "Interest", "Area", "In Bristol", "Budget", "Buying position", "Move-in",
               "Best time"]


def _visit_label(lead: dict) -> str:
    return VISIT_TIMES.get(lead.get("visit_time"), lead.get("visit_time") or "")


def lead_columns(lead: dict) -> list:
    return [
        lead.get("name", ""), lead.get("phone", ""), lead.get("email", ""), INTERESTS.get(lead.get("interest"), ""),
        lead.get("area", ""), "yes" if in_service_area(lead.get("area")) else "no",
        BUDGETS.get(lead.get("budget"), ""), POSITIONS.get(lead.get("position"), ""),
        MOVE_INS.get(lead.get("move_in"), ""), _visit_label(lead),
    ]


def hot_lead_alert(lead: dict, why: str) -> dict:
    """The email sent to the office about a hot lead."""
    wants = INTERESTS.get(lead.get("interest"), "")
    details = [(label, value) for label, value in zip(LEAD_HEADER, lead_columns(lead))
               if value and label != "In Bristol"] + [("Why", why)]
    return {"subject": f"Hot lead: {lead.get('name')} - {wants} in {lead.get('area')}",
            "body": "\n".join(f"{label}: {value}" for label, value in details)}


def thanks(lead: dict, result: Qualification) -> str:
    """What the visitor is told once their details are saved."""
    first = lead.get("name", "").split(" ")[0]
    wants = lead.get("interest")
    if not in_service_area(lead.get("area")):
        return (f"Thank you, {first}. We only cover Bristol, so we may not be able to help with this one, "
                "but I've passed your details to the team and they'll get back to you.")
    phone, when = display_phone(lead.get("phone", "")), _visit_label(lead)
    when = when.lower() if lead.get("visit_time") in VISIT_TIMES else when
    if wants in ("sell", "let_out"):
        return (f"Thank you, {first}! One of our valuers will call you on {phone} during office hours to arrange "
                f"your free valuation. I've noted that this suits you best: {when}.")
    team = "lettings" if wants == "rent" else "sales"
    text = (f"Thank you, {first}! Our {team} team will call you on {phone} during office hours to arrange "
            f"viewings. I've noted that this suits you best: {when}.")
    if lead.get("position") == "sell_first":
        text += " As you have a home to sell, they'll also offer you a free valuation."
    return text
