"""Model providers.

* Gemini (via LangChain) for real use. Needs GOOGLE_API_KEY from Google AI Studio.
* Offline fakes for tests and for running the app without a key. They are
  deterministic and make no network calls; answers are extractive, not generated.

LangChain is imported inside the Gemini classes only, so the core engine and
the test-suite run without it.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from typing import Callable, Protocol, TypeVar

import numpy as np

from .bm25 import tokenize
from .prompting import HUMAN_PROMPT, REFUSAL, SYSTEM_PROMPT

DEFAULT_CHAT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_EMBED_MODEL = "gemini-embedding-001"

T = TypeVar("T")


class AnswerModel(Protocol):
    name: str

    def answer(self, business: str, context: str, question: str) -> str: ...


def _is_rate_limit(error: Exception) -> bool:
    text = f"{type(error).__name__} {error}".lower()
    return any(s in text for s in ("429", "resource_exhausted", "resourceexhausted", "rate limit", "quota"))


def with_backoff(call: Callable[[], T], retries: int = 4, base_delay: float = 2.0) -> T:
    """Retry on rate-limit errors with exponential backoff (2s, 4s, 8s, 16s)."""
    for attempt in range(retries + 1):
        try:
            return call()
        except Exception as error:  # noqa: BLE001 - providers raise many types
            if attempt == retries or not _is_rate_limit(error):
                raise
            time.sleep(base_delay * (2 ** attempt))
    raise RuntimeError("unreachable")


def _message_text(message) -> str:
    """Gemini 3 returns content blocks; `.text` gives the plain string.
    Older langchain-core exposed `.text` as a method, newer as a property."""
    text = getattr(message, "text", None)
    if callable(text):
        text = text()
    if isinstance(text, str) and text:
        return text
    content = getattr(message, "content", "")
    if isinstance(content, list):
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content)


# --------------------------------------------------------------------------- Gemini

class GeminiEmbedder:
    """Reads the key from GOOGLE_API_KEY (set by `make_providers`)."""

    def __init__(self, model: str | None = None, dimensions: int = 768):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        self.model = model or os.getenv("GEMINI_EMBED_MODEL", DEFAULT_EMBED_MODEL)
        self.name = f"gemini:{self.model}:{dimensions}"
        self._client = GoogleGenerativeAIEmbeddings(model=self.model, output_dimensionality=dimensions)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return with_backoff(lambda: self._client.embed_documents(texts))

    def embed_query(self, text: str) -> list[float]:
        return with_backoff(lambda: self._client.embed_query(text))


class GeminiAnswerModel:
    """Reads the key from GOOGLE_API_KEY (set by `make_providers`)."""

    def __init__(self, model: str | None = None):
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_google_genai import ChatGoogleGenerativeAI

        self.model = model or os.getenv("GEMINI_CHAT_MODEL", DEFAULT_CHAT_MODEL)
        self.name = f"gemini:{self.model}"
        llm = ChatGoogleGenerativeAI(model=self.model, max_retries=2)
        prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)])
        # LCEL pipeline: prompt template -> Gemini.
        self._chain = prompt | llm

    def answer(self, business: str, context: str, question: str) -> str:
        message = with_backoff(lambda: self._chain.invoke({"business": business, "context": context, "question": question}))
        return _message_text(message).strip()


# --------------------------------------------------------------------------- Offline

class OfflineEmbedder:
    """Feature-hashing bag of words + character trigrams. Captures word overlap,
    not meaning; good enough to exercise the pipeline without a network."""

    def __init__(self, dimensions: int = 512):
        self.dimensions = dimensions
        self.name = f"offline-hash:{dimensions}"

    def _vector(self, text: str) -> list[float]:
        vec = np.zeros(self.dimensions, dtype=np.float32)
        words = tokenize(text)
        features = words + [w[i:i + 3] for w in words for i in range(max(1, len(w) - 2))]
        for feature in features:
            digest = hashlib.md5(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[index] += sign
        return vec.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


_BLOCK = re.compile(r"^\[(\d+)\] \((.+?)\)\n(.*?)(?=^\[\d+\] \(|\Z)", re.MULTILINE | re.DOTALL)


class OfflineAnswerModel:
    """Extractive stand-in for an LLM: returns the best-matching sentence of the
    best-matching source, with its citation, or the refusal if nothing matches."""

    name = "offline-extractive"

    def __init__(self, min_overlap: int = 2):
        self.min_overlap = min_overlap

    def answer(self, business: str, context: str, question: str) -> str:
        from .chunking import split_sentences

        q_terms = set(tokenize(question))
        best: tuple[int, int, str] | None = None
        for match in _BLOCK.finditer(context):
            number, body = int(match.group(1)), match.group(3)
            for sentence in split_sentences(body):
                overlap = len(q_terms & set(tokenize(sentence)))
                if best is None or overlap > best[0]:
                    best = (overlap, number, sentence)
        if best is None or best[0] < self.min_overlap:
            return REFUSAL
        _, number, sentence = best
        return f"{sentence} [{number}]"


def make_providers(api_key: str | None = None) -> tuple[object, AnswerModel, bool]:
    """Gemini when a key is available, otherwise offline. Returns (embedder, model, is_live)."""
    key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if key:
        # Both LangChain Gemini classes read GOOGLE_API_KEY from the environment.
        os.environ["GOOGLE_API_KEY"] = key
        return GeminiEmbedder(), GeminiAnswerModel(), True
    return OfflineEmbedder(), OfflineAnswerModel(), False
