"""Hybrid retrieval via Reciprocal Rank Fusion.

`reciprocal_rank_fusion` combines multiple ranked lists by summing the
RRF score `1 / (rrf_k + rank)` across appearances. Items in higher
positions across more lists rise to the top. The convention follows
Cormack, Clarke and Buettcher (2009), "Reciprocal Rank Fusion outperforms
Condorcet and individual Rank Learning Methods" (SIGIR).

The function is symbol-agnostic — pass it lists of any hashable keys
(document IDs, citation strings, etc.).
"""

from __future__ import annotations

from typing import Hashable, List, Tuple, TypeVar

T = TypeVar("T", bound=Hashable)


def reciprocal_rank_fusion(
    rank_lists: List[List[T]],
    k: int = 10,
    rrf_k: int = 60,
) -> List[Tuple[T, float]]:
    """Fuse ranked lists by RRF.

    Args:
        rank_lists: each inner list is ordered from rank 1 (best) downward.
        k:          maximum number of results to return.
        rrf_k:      RRF constant. Smaller values give more weight to top ranks;
                    the literature default is 60.

    Returns:
        List of (item, score) sorted by score descending, length <= k.
    """
    if not rank_lists:
        return []
    scores: dict[T, float] = {}
    for rl in rank_lists:
        for rank, item in enumerate(rl, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (rrf_k + rank)
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ordered[:k]
