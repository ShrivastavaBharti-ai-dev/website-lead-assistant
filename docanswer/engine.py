"""The RAG engine: index documents, retrieve, answer with citations."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .bm25 import BM25Index
from .chunking import make_chunks
from .hybrid import reciprocal_rank_fusion
from .prompting import (
    REFUSAL,
    build_citations,
    format_context,
    is_refusal,
    strip_invalid_citations,
)
from .types import Answer, Chunk, Page, ScoredChunk
from .vector_index import EmbeddingCache, VectorIndex


@dataclass(frozen=True)
class RagConfig:
    chunking: str = "sentence"        # "sentence" or "fixed"
    chunk_size: int = 600             # characters
    chunk_overlap: int = 1            # sentences (sentence) or characters (fixed)
    contextual_headers: bool = True   # prefix each chunk with its document title before indexing
    retrieval: str = "hybrid"         # "hybrid", "dense" or "bm25"
    top_k: int = 4                    # sources shown to the model
    candidate_k: int = 20             # per-retriever candidates before fusion
    require_citations: bool = True    # refuse answers that cite nothing


# The naive setup most first RAG demos ship with. Kept for the evaluation.
BASELINE = RagConfig(chunking="fixed", chunk_size=1000, chunk_overlap=0,
                     contextual_headers=False, retrieval="dense", top_k=3)
OPTIMIZED = RagConfig()


def document_title(source: str) -> str:
    return Path(source).stem.replace("_", " ").replace("-", " ").title()


class RagEngine:
    def __init__(self, embedder, answer_model, config: RagConfig = OPTIMIZED,
                 business: str = "our business", cache_path: str | Path | None = ".cache/embeddings.json"):
        self.embedder = embedder
        self.answer_model = answer_model
        self.config = config
        self.business = business
        self.cache = EmbeddingCache(cache_path)
        self.chunks: list[Chunk] = []
        self._vectors: VectorIndex | None = None
        self._bm25: BM25Index | None = None

    # ------------------------------------------------------------------ indexing
    def _index_text(self, chunk: Chunk) -> str:
        if not self.config.contextual_headers:
            return chunk.text
        return f"{document_title(chunk.source)} ({chunk.location})\n{chunk.text}"

    def build(self, pages: list[Page]) -> "RagEngine":
        cfg = self.config
        self.chunks = make_chunks(pages, cfg.chunking, cfg.chunk_size, cfg.chunk_overlap)
        texts = [self._index_text(c) for c in self.chunks]
        self._vectors = VectorIndex(self.embedder, self.cache).build(texts) if cfg.retrieval != "bm25" else None
        self._bm25 = BM25Index(texts) if cfg.retrieval != "dense" else None
        return self

    def with_config(self, config: RagConfig) -> "RagEngine":
        """Same models and cache, different settings (used by the evaluation)."""
        clone = RagEngine(self.embedder, self.answer_model, config, self.business, None)
        clone.cache = self.cache
        return clone

    # ----------------------------------------------------------------- retrieval
    def retrieve(self, question: str) -> list[ScoredChunk]:
        if not self.chunks:
            return []
        cfg = self.config
        if cfg.retrieval == "dense":
            hits = self._vectors.top(question, cfg.top_k)
        elif cfg.retrieval == "bm25":
            hits = self._bm25.top(question, cfg.top_k)
        elif cfg.retrieval == "hybrid":
            dense = [i for i, _ in self._vectors.top(question, cfg.candidate_k)]
            keyword = [i for i, _ in self._bm25.top(question, cfg.candidate_k)]
            hits = reciprocal_rank_fusion([dense, keyword])[: cfg.top_k]
        else:
            raise ValueError(f"unknown retrieval mode: {cfg.retrieval}")
        return [ScoredChunk(self.chunks[i], score) for i, score in hits]

    # ------------------------------------------------------------------ answering
    def ask(self, question: str) -> Answer:
        question = question.strip()
        if not question:
            return Answer(text="Please type a question.", refused=True)
        retrieved = self.retrieve(question)
        if not retrieved:
            return Answer(text=REFUSAL, refused=True)

        raw = self.answer_model.answer(self.business, format_context(retrieved), question)
        text = strip_invalid_citations(raw, len(retrieved))
        citations = build_citations(text, retrieved)

        if not citations and (is_refusal(text) or self.config.require_citations):
            # Either the model said it couldn't find it, or it answered without
            # pointing to a source. In both cases we don't show a guess.
            return Answer(text=REFUSAL, refused=True, retrieved=retrieved)
        return Answer(text=text, citations=citations, refused=False, retrieved=retrieved)


__all__ = ["RagEngine", "RagConfig", "BASELINE", "OPTIMIZED", "replace"]
