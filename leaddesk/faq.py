"""Answer visitor questions from the studio's own documents, using the
DocAnswer engine from my document-chatbot project (hybrid search, citations,
refusal when the documents don't cover it)."""
from __future__ import annotations

import re
from pathlib import Path

from docanswer import OPTIMIZED, RagEngine, load_folder

_CITATION = re.compile(r"\s*\[\d+\]")


class FaqAnswerer:
    def __init__(self, embedder, answer_model, folder: str | Path, business: str,
                 cache_path: str | Path | None = None):
        self.engine = RagEngine(embedder, answer_model, OPTIMIZED, business=business,
                                cache_path=cache_path).build(load_folder(folder))

    def answer(self, question: str) -> str | None:
        """The answer without [n] markers, or None if the documents don't cover it."""
        if getattr(self.engine.answer_model, "name", "") == "offline-extractive":
            return self._best_passage(question)
        result = self.engine.ask(question)
        if result.refused:
            return None
        return _CITATION.sub("", result.text).strip()

    def _best_passage(self, question: str) -> str | None:
        """Offline mode (no API key): show the most relevant passage instead of a generated answer."""
        retrieved = self.engine.retrieve(question)
        if not retrieved:
            return None
        text = " ".join(retrieved[0].chunk.text.replace("- ", "").split())
        if len(text) > 350:
            text = text[:350].rsplit(". ", 1)[0] + "."
        return f"Here's what I found: {text}"
