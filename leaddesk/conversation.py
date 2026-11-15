"""The chat flow: answer questions from the business's documents, and when the
visitor is interested, collect their details one question at a time, score
the lead and hand it to the sink. Everything about the particular business
(questions, wording, scoring) comes from its profile."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from .extract import Extractor
from .sinks import LeadSink

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
    def __init__(self, profile, extractor: Extractor, faq, sink: LeadSink):
        self.profile, self.extractor, self.faq, self.sink = profile, extractor, faq, sink

    def greet(self) -> Reply:
        return Reply(self.profile.GREETING, self.profile.GREETING_CHOICES)

    def _next_field(self, session: Session) -> str | None:
        return next((f for f in self.profile.required(session.lead) if not session.lead.get(f)), None)

    def _ask(self, session: Session, field_name: str) -> tuple[str, list[str]]:
        session.asked = field_name
        text, choices = self.profile.question(field_name, session.lead)
        first = session.lead.get("name", "").split(" ")[0] or "there"
        return text.format(name=first), choices

    def handle(self, session: Session, message: str) -> Reply:
        p = self.profile
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
            parts.append(answer or p.NOT_FOUND)

        if session.submitted:
            if not parts:
                parts.append(p.AFTER_SUBMIT)
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
        elif question and not session.offered and (p.OFFER_TRIGGER.search(question) or len(session.questions) >= 2):
            session.offered = True
            parts.append(p.OFFER)
            choices = p.OFFER_CHOICES
        elif not parts:
            return Reply(p.HELP, p.GREETING_CHOICES)
        return Reply(" ".join(parts), choices)

    def _submit(self, session: Session, parts: list[str]) -> Reply:
        lead, p = session.lead, self.profile
        result = p.qualify(lead)
        why = "; ".join(result.reasons)
        row = [datetime.now().isoformat(timespec="seconds"), *p.lead_columns(lead), result.temperature.upper(),
               result.score, why, " | ".join(session.questions[-5:]), session.page, session.id]
        self.sink.save(row, p.hot_lead_alert(lead, why) if result.temperature == "hot" else None)
        session.submitted = True
        session.asked = None
        parts.append(p.thanks(lead, result))
        return Reply(" ".join(parts), [], lead_complete=True, temperature=result.temperature)
