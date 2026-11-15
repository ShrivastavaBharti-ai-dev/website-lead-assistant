"""Reciprocal Rank Fusion (RRF): merge rankings from different retrievers.

RRF only looks at *positions*, not raw scores, so it can combine BM25 scores
(unbounded) with cosine similarities (-1..1) without any tuning.
"""
from __future__ import annotations


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60, weights: list[float] | None = None) -> list[tuple[int, float]]:
    """Each ranking is a list of item ids, best first. Returns (id, fused score), best first."""
    weights = weights or [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError("one weight per ranking")
    fused: dict[int, float] = {}
    for ranking, weight in zip(rankings, weights):
        for position, item in enumerate(ranking):
            fused[item] = fused.get(item, 0.0) + weight / (k + position + 1)
    return sorted(fused.items(), key=lambda p: (-p[1], p[0]))
