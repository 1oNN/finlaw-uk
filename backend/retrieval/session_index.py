"""Per-session FAISS index for uploaded files.

Each chat session gets its own in-memory dense index over the chunks
extracted from files uploaded in that session. Embeddings reuse the
process-wide shared BGE encoder from `backend.retrieval.dense`, so
adding a session costs only the embedding compute — there is no extra
model load.

The store is in-memory and bounded by `RAG_MAX_SESSIONS` (default 20):
once the cap is reached, the least-recently-used session is evicted on
the next add. Uploads are intentionally ephemeral; a process restart
clears them and there is no persistence layer.

API:
    add(session_id, filename, chunks) -> int       # chunks indexed
    search(session_id, query, k=5) -> [(key, snippet), ...]
    chunk_count(session_id, filename=None) -> int
    clear(session_id) -> None
    has_session(session_id) -> bool
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import faiss  # type: ignore
    _FAISS_AVAILABLE = True
except Exception:
    faiss = None  # type: ignore
    _FAISS_AVAILABLE = False


from backend.retrieval.dense import _load_shared_model

MAX_SESSIONS = int(os.getenv("RAG_MAX_SESSIONS", "20"))


@dataclass
class _SessionState:
    keys: List[str] = field(default_factory=list)
    texts: List[str] = field(default_factory=list)
    embeddings: Optional[np.ndarray] = None
    index: object = None
    chunks_by_file: Dict[str, int] = field(default_factory=dict)
    last_used: float = field(default_factory=time.monotonic)


_INDICES: Dict[str, _SessionState] = {}


def _encode(texts: List[str]) -> np.ndarray:
    model = _load_shared_model()
    embs = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return embs.astype("float32")


def _build_faiss(state: _SessionState) -> None:
    if not _FAISS_AVAILABLE or state.embeddings is None or len(state.embeddings) == 0:
        state.index = None
        return
    d = state.embeddings.shape[1]
    state.index = faiss.IndexFlatIP(d)
    state.index.add(state.embeddings)


def _evict_lru_if_needed() -> None:
    while len(_INDICES) >= MAX_SESSIONS:
        victim = min(_INDICES.items(), key=lambda kv: kv[1].last_used)[0]
        del _INDICES[victim]


def has_session(session_id: str) -> bool:
    return bool(session_id) and session_id in _INDICES


def chunk_count(session_id: str, filename: Optional[str] = None) -> int:
    state = _INDICES.get(session_id)
    if state is None:
        return 0
    if filename is None:
        return sum(state.chunks_by_file.values())
    return state.chunks_by_file.get(filename, 0)


def clear(session_id: str) -> None:
    _INDICES.pop(session_id, None)


def add(session_id: str, filename: str, chunks: List[str]) -> int:
    """Index `chunks` for one file in the session. Returns the number of
    non-empty chunks indexed."""
    chunks = [c for c in chunks if c and c.strip()]
    if not session_id or not chunks:
        return 0

    state = _INDICES.get(session_id)
    if state is None:
        _evict_lru_if_needed()
        state = _SessionState()
        _INDICES[session_id] = state

    start_idx = state.chunks_by_file.get(filename, 0)
    new_keys = [
        f"session::{filename}::{start_idx + i}" for i in range(len(chunks))
    ]
    new_embs = _encode(chunks)

    if state.embeddings is None or len(state.embeddings) == 0:
        state.embeddings = new_embs
    else:
        state.embeddings = np.vstack([state.embeddings, new_embs])
    state.keys.extend(new_keys)
    state.texts.extend(chunks)
    state.chunks_by_file[filename] = start_idx + len(chunks)
    _build_faiss(state)
    state.last_used = time.monotonic()
    return len(chunks)


def search(session_id: str, query: str, k: int = 5) -> List[Tuple[str, str]]:
    """Return up to k (key, snippet) pairs ranked by cosine similarity.

    Empty list if the session has no chunks or doesn't exist."""
    state = _INDICES.get(session_id)
    if state is None or not state.keys or state.embeddings is None or len(state.embeddings) == 0:
        return []
    q_emb = _encode([query])[0]
    if _FAISS_AVAILABLE and state.index is not None:
        scores, idxs = state.index.search(q_emb.reshape(1, -1), min(k, len(state.keys)))
        hit_idxs = [int(i) for i in idxs[0] if i >= 0]
    else:
        sims = state.embeddings @ q_emb
        hit_idxs = [int(i) for i in np.argsort(-sims)[: min(k, len(state.keys))]]
    state.last_used = time.monotonic()
    return [(state.keys[i], state.texts[i]) for i in hit_idxs]
