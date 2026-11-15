"""Okapi BM25 keyword search, implemented in pure Python.

Semantic (embedding) search is good at paraphrases ("small town" ~ "non-metro")
but weak at exact tokens such as product codes, order-number formats or
prices. BM25 is the opposite. The hybrid retriever combines both.
"""
from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

STOPWORDS = frozenset(
    """a an and are as at be but by can do does for from has have how i if in into is it its
    me my no not of on or our so than that the their them then there these they this to too
    was we what when where which who will with you your""".split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens; hyphenated codes like ``snt-bd-114`` stay whole
    and are also indexed by their parts so ``BD-114`` still matches."""
    tokens: list[str] = []
    for tok in _TOKEN.findall(text.lower().replace(",", "")):
        if tok in STOPWORDS:
            continue
        tokens.append(tok)
        if "-" in tok:
            tokens.extend(part for part in tok.split("-") if part and part not in STOPWORDS)
    return tokens


class BM25Index:
    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.doc_tokens = [tokenize(d) for d in documents]
        self.doc_freqs = [Counter(toks) for toks in self.doc_tokens]
        self.doc_lens = [len(toks) for toks in self.doc_tokens]
        self.avg_len = (sum(self.doc_lens) / len(self.doc_lens)) if self.doc_lens else 0.0
        df: Counter[str] = Counter()
        for freqs in self.doc_freqs:
            df.update(freqs.keys())
        n = len(documents)
        # BM25+ style idf that never goes negative for very common terms.
        self.idf = {term: math.log(1 + (n - f + 0.5) / (f + 0.5)) for term, f in df.items()}

    def scores(self, query: str) -> list[float]:
        terms = tokenize(query)
        out = []
        for freqs, length in zip(self.doc_freqs, self.doc_lens):
            score = 0.0
            for term in terms:
                tf = freqs.get(term, 0)
                if not tf:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * length / (self.avg_len or 1))
                score += self.idf[term] * tf * (self.k1 + 1) / denom
            out.append(score)
        return out

    def top(self, query: str, k: int) -> list[tuple[int, float]]:
        """Indices and scores of the best k documents with a non-zero score."""
        ranked = sorted(enumerate(self.scores(query)), key=lambda p: p[1], reverse=True)
        return [(i, s) for i, s in ranked[:k] if s > 0]
