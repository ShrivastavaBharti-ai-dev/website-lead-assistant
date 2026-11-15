"""Measure the chatbot on a labelled question set.

Each question records where the answer lives (file + page/section) and a few
facts the answer must contain. Unanswerable questions check that the bot
refuses instead of guessing. No LLM-as-judge: scoring is deterministic and
costs no extra API calls.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .engine import RagEngine


@dataclass
class EvalQuestion:
    id: str
    question: str
    answerable: bool = True
    expected_source: str | None = None
    expected_location: str | None = None
    must_include: list[str] = field(default_factory=list)


@dataclass
class EvalRow:
    id: str
    answerable: bool
    hit: bool
    reciprocal_rank: float
    answered_correctly: bool | None = None
    cited_correctly: bool | None = None
    refused: bool | None = None
    answer: str = ""


def load_questions(path: str | Path) -> list[EvalQuestion]:
    questions = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            questions.append(EvalQuestion(**json.loads(line)))
    return questions


def normalise(text: str) -> str:
    text = text.lower().replace("₹", " ").replace("rs.", " ").replace(",", "")
    text = re.sub(r"[‐-―]", "-", text)  # all dash variants -> hyphen
    return " ".join(text.split())


def _matches(source: str, location: str, q: EvalQuestion) -> bool:
    return source == q.expected_source and location == q.expected_location


def evaluate(engine: RagEngine, questions: list[EvalQuestion], answer: bool = True,
             pause_seconds: float = 0.0) -> list[EvalRow]:
    rows = []
    for q in questions:
        retrieved = engine.retrieve(q.question)
        rank = next((i + 1 for i, item in enumerate(retrieved)
                     if _matches(item.chunk.source, item.chunk.location, q)), None)
        row = EvalRow(q.id, q.answerable, hit=rank is not None,
                      reciprocal_rank=(1.0 / rank) if rank else 0.0)
        if answer:
            result = engine.ask(q.question)
            row.answer, row.refused = result.text, result.refused
            if q.answerable:
                text = normalise(result.text)
                row.answered_correctly = (not result.refused) and all(normalise(f) in text for f in q.must_include)
                row.cited_correctly = any(_matches(c.source, c.location, q) for c in result.citations)
            if pause_seconds:
                time.sleep(pause_seconds)  # stay under free-tier requests-per-minute
        rows.append(row)
    return rows


def summarise(rows: list[EvalRow]) -> dict[str, float]:
    answerable = [r for r in rows if r.answerable]
    unanswerable = [r for r in rows if not r.answerable]
    pct = lambda n, d: round(100.0 * n / d, 1) if d else 0.0  # noqa: E731
    summary = {
        "questions": len(rows),
        "retrieval_hit_rate": pct(sum(r.hit for r in answerable), len(answerable)),
        "mrr": round(sum(r.reciprocal_rank for r in answerable) / len(answerable), 3) if answerable else 0.0,
    }
    if any(r.answered_correctly is not None for r in answerable):
        summary["answer_accuracy"] = pct(sum(bool(r.answered_correctly) for r in answerable), len(answerable))
        summary["correct_citation_rate"] = pct(sum(bool(r.cited_correctly) for r in answerable), len(answerable))
        summary["wrongly_refused"] = pct(sum(bool(r.refused) for r in answerable), len(answerable))
        summary["refused_when_should"] = pct(sum(bool(r.refused) for r in unanswerable), len(unanswerable))
    return summary
