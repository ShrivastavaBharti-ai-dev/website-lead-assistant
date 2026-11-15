"""Dense (embedding) search with an on-disk cache.

The cache matters on Gemini's free tier: documents are embedded once, and
restarting the app or re-running the evaluation costs no extra API calls.
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    """Anything with LangChain's embedding interface works here."""

    name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class EmbeddingCache:
    """JSON file mapping (embedder, kind, text hash) -> vector."""

    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None
        self._data: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        if self.path and self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    @staticmethod
    def key(embedder_name: str, kind: str, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
        return f"{embedder_name}|{kind}|{digest}"

    def get(self, key: str) -> list[float] | None:
        return self._data.get(key)

    def put_many(self, items: dict[str, list[float]]) -> None:
        with self._lock:
            self._data.update(items)
            if self.path:
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = self.path.with_suffix(".tmp")
                    tmp.write_text(json.dumps(self._data))
                    tmp.replace(self.path)
                except OSError:
                    # Read-only disk (some hosts): keep the cache in memory only.
                    self.path = None


def _normalise(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class VectorIndex:
    def __init__(self, embedder: Embedder, cache: EmbeddingCache | None = None, batch_size: int = 32):
        self.embedder = embedder
        self.cache = cache or EmbeddingCache(None)
        self.batch_size = batch_size
        self.matrix = np.zeros((0, 0))

    def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        keys = [EmbeddingCache.key(self.embedder.name, "doc", t) for t in texts]
        missing = [(k, t) for k, t in zip(keys, texts) if self.cache.get(k) is None]
        for start in range(0, len(missing), self.batch_size):
            batch = missing[start:start + self.batch_size]
            vectors = self.embedder.embed_documents([t for _, t in batch])
            self.cache.put_many({k: list(map(float, v)) for (k, _), v in zip(batch, vectors)})
        return [self.cache.get(k) for k in keys]  # type: ignore[misc]

    def _embed_query(self, text: str) -> list[float]:
        key = EmbeddingCache.key(self.embedder.name, "query", text)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        vector = list(map(float, self.embedder.embed_query(text)))
        self.cache.put_many({key: vector})
        return vector

    def build(self, texts: list[str]) -> "VectorIndex":
        vectors = self._embed_documents(texts) if texts else []
        self.matrix = _normalise(np.array(vectors, dtype=np.float32)) if vectors else np.zeros((0, 0))
        return self

    def top(self, query: str, k: int) -> list[tuple[int, float]]:
        if self.matrix.size == 0:
            return []
        q = np.array(self._embed_query(query), dtype=np.float32)
        q /= np.linalg.norm(q) or 1.0
        sims = self.matrix @ q
        order = np.argsort(-sims)[:k]
        return [(int(i), float(sims[i])) for i in order]
