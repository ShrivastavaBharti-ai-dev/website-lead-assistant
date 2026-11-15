"""The chat flow: answer questions from the studio's documents, and when the
visitor is interested, collect their details one question at a time, score
the lead and hand it to the sink."""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from . import fields as F
from .extract import Extractor
from .qualify import qualify
from .sinks import LeadSink

BUSINESS = "Terracotta Lane Interiors"
GREETING = ("Hi! I'm the assistant at Terracotta Lane Interiors. Ask me about our services, prices or timelines, "
            "or book a free design consultation.")
GREETING_CHOICES = ["Book a free consultation", "How much does a 2 BHK cost?", "Which areas do you cover?"]
OFFER = "Would you like a free 45-minute design consultation? I just need a few details."
OFFER_CHOICES = ["Book a free consultation", "I have another question"]
NOT_FOUND = "I'm not sure about that one, so I won't guess. Our designer can answer it on a call."
_PRICE_WORDS = re.compile(r"\b(price|prices|cost|costs|quote|estimate|budget|charges|fee|fees|how much)\b", re.I)


@dataclass
class Session:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    lead: dict = field(default_factory=dict)
    asked: str | None = None
    collecting: bool = False
    submitted: bool = False
    offered: bool = False
    questions: list[str] = field(default_factory=list)
    messages: int = 0
    page: str = ""
    updated: float = field(default_factory=time.time)


@dataclass
class Reply:
    text: str
    quick_replies: list[str] = field(default_factory=list)
    lead_complete: bool = False
    temperature: str | None = None


class Conversation:
    def __init__(self, extractor: Extractor, faq, sink: LeadSink):
        self.extractor, self.faq, self.sink = extractor, faq, sink

    @staticmethod
    def greet() -> Reply:
        return Reply(GREETING, GREETING_CHOICES)

    def _next_field(self, session: Session) -> str | None:
        return next((f for f in F.REQUIRED if not session.lead.get(f)), None)

    def _ask(self, session: Session, field_name: str) -> tuple[str, list[str]]:
        session.asked = field_name
        text, choices = F.QUESTIONS[field_name]
        first = session.lead.get("name", "").split(" ")[0] or "there"
        return text.format(name=first), choices

    def handle(self, session: Session, message: str) -> Reply:
        session.messages += 1
        session.updated = time.time()
        understood = self.extractor.extract(message, session.asked, session.lead)
        new = {k: v for k, v in understood["fields"].items() if v and k not in session.lead}
        if session.submitted:
            new = {}
        session.lead.update(new)

        parts: list[str] = []
        choices: list[str] = []
        question = understood["question"]
        if question:
            session.questions.append(question[:200])
            answer = self.faq.answer(question)
            parts.append(answer or NOT_FOUND)

        if session.submitted:
            if not parts:
                parts.append("Your request is with our design team; they'll call you soon. Anything else I can help with?")
            return Reply(" ".join(parts))

        # Details mentioned inside a question ("how much is a 2 BHK?") don't start the form on their own.
        wants = understood["wants_consultation"] or (bool(new) and not question)
        if understood["declined"] and not new and session.asked is None:
            session.offered = True
            return Reply(" ".join(parts) or "No problem. What else would you like to know?")
        if wants:
            session.collecting = True

        if session.collecting:
            missing = self._next_field(session)
            if missing:
                if (session.asked and session.asked == missing and not new and not question
                        and not understood["wants_consultation"]):
                    parts.append("Sorry, I didn't quite get that.")
                text, choices = self._ask(session, missing)
                parts.append(text)
            else:
                return self._submit(session, parts)
        elif question and not session.offered and (_PRICE_WORDS.search(question) or len(session.questions) >= 2):
            session.offered = True
            parts.append(OFFER)
            choices = OFFER_CHOICES
        elif not parts:
            return Reply("I can answer questions about our services, prices and timelines, or book a free "
                         "consultation for you.", GREETING_CHOICES)
        return Reply(" ".join(parts), choices)

    def _submit(self, session: Session, parts: list[str]) -> Reply:
        lead = session.lead
        result = qualify(lead)
        row = [
            datetime.now().isoformat(timespec="seconds"), lead.get("name", ""), lead.get("phone", ""),
            lead.get("email", ""), F.PROJECT_TYPES.get(lead.get("project_type"), ""),
            F.PROPERTIES.get(lead.get("property"), ""), lead.get("area", ""),
            "yes" if F.in_service_area(lead.get("area")) else "no", F.BUDGETS.get(lead.get("budget"), ""),
            F.TIMELINES.get(lead.get("timeline"), ""), result.temperature.upper(), result.score,
            "; ".join(result.reasons), " | ".join(session.questions[-5:]), session.page, session.id,
        ]
        notify = None
        if result.temperature == "hot":
            notify = {
                "subject": f"Hot lead: {lead.get('name')} - {F.PROJECT_TYPES.get(lead.get('project_type'), '')} in {lead.get('area')}",
                "body": "\n".join([f"{h}: {v}" for h, v in zip(
                    ["Name", "Phone", "Project", "Area", "Budget", "Timeline", "Why"],
                    [row[1], row[2], row[4], row[6], row[8], row[9], row[12]])]),
            }
        self.sink.save(row, notify)
        session.submitted = True
        session.asked = None
        first = lead.get("name", "").split(" ")[0]
        if result.temperature == "cold" and not F.in_service_area(lead.get("area")):
            parts.append(f"Thank you, {first}. We only take projects in the Pune region, so we may not be able to help "
                         "with this one, but I've passed your details to the team and they'll get back to you.")
        else:
            parts.append(f"Thank you, {first}! I've passed your details to our design team. They'll call you on "
                         f"{F.display_phone(lead.get('phone', ''))} during studio hours (Tuesday to Sunday, 10 am to 7 pm) to fix a time "
                         "for your free consultation.")
        return Reply(" ".join(parts), [], lead_complete=True, temperature=result.temperature)
