"""Cross-encoder reranker for retrieval post-processing.

Loaded LAZILY (only on first call to ``rerank()``) so the backend cold-start
doesn't have to wait ~3 s for a transformer that may never be used in a
given session.

Default model is ``BAAI/bge-reranker-base`` (~280 MB, ~80-300 ms per
query depending on candidate count) — BGE rerankers handle UK
legal / regulatory phrasing better than the MS MARCO MiniLM
cross-encoder we used previously. Override via env var
``RAG_RERANK_MODEL`` (e.g. ``cross-encoder/ms-marco-MiniLM-L-6-v2`` to
fall back).

Used by ``backend.retrieval.orchestrator._hybrid_search`` when
``RAG_RERANK_ENABLED=1``; the orchestrator retrieves top-30 hybrid then
asks ``rerank()`` to return the top-k strongest matches.
"""

from __future__ import annotations

import logging
import os
from typing import List, Tuple

log = logging.getLogger(__name__)

_MODEL = None
_DISABLED = False
_MODEL_NAME = os.getenv("RAG_RERANK_MODEL", "BAAI/bge-reranker-base")


def _get_model():
    """Lazy single-process load of the cross-encoder."""
    global _MODEL, _DISABLED
    if _MODEL is not None:
        return _MODEL
    if _DISABLED:
        return None
    try:
        from sentence_transformers import CrossEncoder
    except Exception as e:
        log.warning("sentence-transformers not available, reranker disabled: %s", e)
        _DISABLED = True
        return None
    try:
        _MODEL = CrossEncoder(_MODEL_NAME)
        log.info("Cross-encoder reranker loaded: %s", _MODEL_NAME)
    except Exception as e:
        log.warning("Failed to load cross-encoder %s, reranker disabled: %s",
                    _MODEL_NAME, e)
        _DISABLED = True
        return None
    return _MODEL


def rerank(query: str, candidates: List[Tuple[str, str]], top_k: int) -> List[Tuple[str, str]]:
    """Rerank `(key, text)` pairs against `query`. Returns at most `top_k`.

    Falls through to input order if the model can't be loaded — never raises.
    """
    if not candidates or top_k <= 0:
        return []
    if len(candidates) <= top_k:
        # Nothing to filter; rerank order has no effect.
        return candidates[:top_k]
    model = _get_model()
    if model is None:
        return candidates[:top_k]
    try:
        pairs = [(query, text or "") for _, text in candidates]
        scores = model.predict(pairs)
    except Exception as e:
        log.warning("Cross-encoder inference failed, falling back to input order: %s", e)
        return candidates[:top_k]
    scored = list(zip(candidates, scores))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [cand for cand, _score in scored[:top_k]]
