"""Plain data types shared across the pipeline.

Kept free of third-party imports so the core engine can be tested without
LangChain, Streamlit or an API key.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Page:
    """One unit of extracted text with a human-readable location.

    `location` is what a customer sees in a citation: "p. 2" for PDFs,
    "Section: Gift wrapping" for Word documents.
    """

    text: str
    source: str
    location: str


@dataclass(frozen=True)
class Chunk:
    """A retrievable piece of a document."""

    id: str
    text: str
    source: str
    location: str


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class Citation:
    number: int
    source: str
    location: str
    snippet: str


@dataclass
class Answer:
    text: str
    citations: list[Citation] = field(default_factory=list)
    refused: bool = False
    retrieved: list[ScoredChunk] = field(default_factory=list)
