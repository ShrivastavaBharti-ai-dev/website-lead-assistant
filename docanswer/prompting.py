"""Grounded-answer prompt, citation parsing and the refusal guard."""
from __future__ import annotations

import re

from .types import Citation, ScoredChunk

REFUSAL = "I couldn't find that in the documents, so I don't want to guess. Please contact the team directly."

SYSTEM_PROMPT = f"""You are the customer-help assistant for {{business}}.
Answer the customer's question using ONLY the numbered sources below.

Rules:
1. Every factual sentence must end with the number of the source it came from, like [1] or [2][3].
2. If the sources do not contain the answer, reply with exactly: "{REFUSAL}"
3. Never invent prices, dates, policies, phone numbers or links.
4. Be brief and friendly: 1-4 sentences. Quote numbers exactly as written in the sources.
5. If the question has several parts and only some are answered by the sources, answer those parts and say which part you could not find."""

HUMAN_PROMPT = """Sources:
{context}

Customer question: {question}"""

_CITATION = re.compile(r"\[(\d{1,2})\]")


def format_context(retrieved: list[ScoredChunk]) -> str:
    blocks = []
    for number, item in enumerate(retrieved, start=1):
        chunk = item.chunk
        blocks.append(f"[{number}] ({chunk.source}, {chunk.location})\n{chunk.text}")
    return "\n\n".join(blocks)


def is_refusal(text: str) -> bool:
    normalised = " ".join(text.lower().split())
    return "couldn't find that in the documents" in normalised or "could not find that in the documents" in normalised


def cited_numbers(text: str, available: int) -> list[int]:
    """Citation numbers in order of first appearance, ignoring out-of-range ones."""
    seen: list[int] = []
    for match in _CITATION.finditer(text):
        n = int(match.group(1))
        if 1 <= n <= available and n not in seen:
            seen.append(n)
    return seen


def snippet(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def build_citations(answer_text: str, retrieved: list[ScoredChunk]) -> list[Citation]:
    citations = []
    for n in cited_numbers(answer_text, len(retrieved)):
        chunk = retrieved[n - 1].chunk
        citations.append(Citation(number=n, source=chunk.source, location=chunk.location, snippet=snippet(chunk.text)))
    return citations


def strip_invalid_citations(text: str, available: int) -> str:
    """Remove markers like [7] when only 4 sources were given (model slip)."""
    return _CITATION.sub(lambda m: m.group(0) if 1 <= int(m.group(1)) <= available else "", text).strip()
