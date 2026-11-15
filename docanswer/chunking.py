"""Split pages into retrievable chunks.

Two strategies are kept on purpose so the evaluation can show the effect of
better chunking:

* ``fixed``    – the naive approach: cut every N characters, wherever that lands.
* ``sentence`` – packs whole sentences up to a size limit and repeats the last
                 sentence of a chunk at the start of the next (overlap), so an
                 answer that sits on a boundary is never cut in half.

Chunks never cross a page/section, which keeps every citation exact.
"""
from __future__ import annotations

import re

from .types import Chunk, Page

# A sentence ends at . ! or ? followed by whitespace, or at a line break
# (bullet lists and table rows in policies are line-based).
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s and s.strip()]


def _chunk_id(page: Page, index: int) -> str:
    return f"{page.source}::{page.location}::{index}"


def fixed_chunks(pages: list[Page], size: int = 1000, overlap: int = 0) -> list[Chunk]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("need size > 0 and 0 <= overlap < size")
    chunks = []
    for page in pages:
        step = size - overlap
        for i, start in enumerate(range(0, len(page.text), step)):
            piece = page.text[start:start + size].strip()
            if piece:
                chunks.append(Chunk(_chunk_id(page, i), piece, page.source, page.location))
    return chunks


def sentence_chunks(pages: list[Page], max_chars: int = 600, overlap_sentences: int = 1) -> list[Chunk]:
    if max_chars <= 0 or overlap_sentences < 0:
        raise ValueError("need max_chars > 0 and overlap_sentences >= 0")
    chunks = []
    for page in pages:
        sentences = split_sentences(page.text)
        current: list[str] = []
        index = 0

        def flush() -> None:
            nonlocal index
            if current:
                chunks.append(Chunk(_chunk_id(page, index), " ".join(current), page.source, page.location))
                index += 1

        for sentence in sentences:
            projected = len(" ".join(current + [sentence]))
            if current and projected > max_chars:
                flush()
                # Carry the tail of the previous chunk forward as context,
                # unless the carried text alone would already be too long.
                tail = current[-overlap_sentences:] if overlap_sentences else []
                current = tail if len(" ".join(tail + [sentence])) <= max_chars else []
            current.append(sentence)
        flush()
    return chunks


def make_chunks(pages: list[Page], strategy: str = "sentence", size: int = 600, overlap: int = 1) -> list[Chunk]:
    if strategy == "sentence":
        return sentence_chunks(pages, max_chars=size, overlap_sentences=overlap)
    if strategy == "fixed":
        return fixed_chunks(pages, size=size, overlap=overlap)
    raise ValueError(f"unknown chunking strategy: {strategy}")
