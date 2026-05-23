"""Retrieval orchestrator: high-level `get_context()` and `get_graph_boost()`.

Combines BM25 (sparse) and BGE-small (dense) results via Reciprocal Rank
Fusion as the primary retrieval path. Falls back through the legacy
phrase/keyword/upload/remote layers when the hybrid path is empty (e.g.,
during cold-start before the dense index is built, or when the dense
encoder is unavailable).

`get_graph_boost()` queries Neo4j (via `backend.graph.client.get_session()`)
for fulltext matches on the `provisionIdx` index and returns context bullets
plus a suggested source line.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from backend.graph.client import get_session
from backend.graph.traversal import neighbors_2hop
from backend.retrieval import sparse
from backend.retrieval.hybrid import reciprocal_rank_fusion

ENABLE_GRAPH = bool(int(os.getenv("RAG_ENABLE_GRAPH", "1")))
ENABLE_DENSE = bool(int(os.getenv("RAG_ENABLE_DENSE", "1")))
RRF_K = int(os.getenv("RAG_RRF_K", "60"))
MAX_SNIP = sparse.MAX_SNIP
TOPK = sparse.TOPK

_DENSE = None
_DENSE_TRIED = False
_DENSE_DISABLED = False


def _get_dense():
    """Lazily build (or restore from cache) the dense retriever.

    Returns None if dense retrieval is disabled, sentence-transformers is
    unavailable, or initialisation has previously failed.
    """
    global _DENSE, _DENSE_TRIED, _DENSE_DISABLED
    if _DENSE is not None:
        return _DENSE
    if _DENSE_DISABLED or not ENABLE_DENSE:
        return None
    _DENSE_TRIED = True
    try:
        from backend.retrieval.dense import DenseRetriever
    except Exception as e:
        sparse._dbg(f"Dense disabled (sentence-transformers not importable): {e}")
        _DENSE_DISABLED = True
        return None
    try:
        dr = DenseRetriever()
        current_keys = set(sparse._LOCAL_DB.keys())
        if dr.load_cache() and set(dr.keys) == current_keys:
            sparse._dbg(f"Dense cache loaded: {dr.num_docs()} docs")
            _DENSE = dr
            return dr
        if not current_keys:
            sparse._dbg("No documents to index for dense retrieval.")
            _DENSE = dr
            return dr
        sparse._dbg(f"Building dense index over {len(current_keys)} docs (first call may take a minute)…")
        dr.index_documents(dict(sparse._LOCAL_DB))
        sparse._dbg(f"Dense index built: {dr.num_docs()} docs")
        _DENSE = dr
        return dr
    except Exception as e:
        sparse._dbg(f"Dense init failed, disabling: {e}")
        _DENSE_DISABLED = True
        return None


def _hybrid_search(query: str, k: int) -> List[Tuple[str, str]]:
    """BM25 + dense → RRF. Returns (key, snippet) pairs.

    Fusion strategy is controlled by `RAG_FUSION_MODE`:
        'rrf'   (default) — Reciprocal Rank Fusion over both sources
        'dense'           — dense-only (skip BM25)
        'bm25'            — bm25-only (skip dense)
    The env var is read per-call so the ablation harness can flip strategies
    without restarting the process.
    """
    mode = os.getenv("RAG_FUSION_MODE", "rrf").lower()
    over_k = max(k * 2, 10)

    bm25_keys: List[str] = []
    dense_keys: List[str] = []

    if mode != "dense":
        bm25_hits = sparse.search_bm25(query, k=over_k)
        bm25_keys = [key for key, _ in bm25_hits]

    if mode != "bm25":
        dense = _get_dense()
        if dense is not None:
            dense_hits = dense.search(query, k=over_k)
            dense_keys = [key for key, _ in dense_hits]

    if not bm25_keys and not dense_keys:
        return []

    rank_lists = [lst for lst in (bm25_keys, dense_keys) if lst]
    # When a reranker will trim later, fuse over a wider pool so the
    # cross-encoder has more candidates to score.
    rerank_enabled = bool(int(os.getenv("RAG_RERANK_ENABLED", "0")))
    fuse_k = max(int(os.getenv("RAG_RERANK_POOL", "30")), k) if rerank_enabled else k
    if len(rank_lists) == 1:
        fused_keys = rank_lists[0][:fuse_k]
    else:
        fused = reciprocal_rank_fusion(rank_lists, k=fuse_k, rrf_k=RRF_K)
        fused_keys = [key for key, _ in fused]

    out: List[Tuple[str, str]] = []
    for key in fused_keys:
        text = sparse.get_doc(key)
        if not text:
            continue
        out.append((key, sparse._snippet(text, None)))

    if rerank_enabled and len(out) > k:
        from backend.retrieval.reranker import rerank
        out = rerank(query, out, top_k=k)

    return out


def _format_hits(hits: List[Tuple[str, str]], max_chars: int) -> str:
    return "".join(f"**Context ({k}):**\n{snip}\n\n" for k, snip in hits)[:max_chars]


def get_raw_context(query: str, *, max_chars: int = MAX_SNIP) -> List[Tuple[str, str]]:
    """Return the underlying `(key, snippet)` hits without Markdown formatting.

    Stops at the first cascade layer that produces results (hybrid → phrase →
    keyword → upload → remote). Used by the evaluation pipeline which needs
    the discrete snippets as RAGAS `contexts` rather than a glued blob."""
    hits = _hybrid_search(query, k=TOPK)
    if hits:
        sparse._dbg(f"hybrid-hit: {len(hits)} for query='{query[:60]}…'")
        return hits

    hits = sparse.search_phrase(query, k=TOPK)
    if hits:
        sparse._dbg(f"phrase-hit: {len(hits)} for query='{query[:60]}…'")
        return hits

    hits = sparse.search_keywords(query, k=TOPK)
    if hits:
        sparse._dbg(f"keyword-hit: {len(hits)} for query='{query[:60]}…'")
        return hits

    upload_keys = sparse.list_upload_keys()
    if upload_keys:
        sparse._dbg("returning full uploaded doc fallback")
        return [(k, sparse.get_doc(k)[:max_chars]) for k in upload_keys[:3]]

    remote = sparse.search_remote(query, max_chars)
    if remote:
        sparse._dbg("returning remote fallback")
        return [("legislation.gov.uk", remote)]
    sparse._dbg("no context found")
    return []


def get_context(query: str, *, max_chars: int = MAX_SNIP) -> str:
    """Return a Markdown context block for the model — the chat-backend
    entry point. Internally delegates to `get_raw_context` then formats.

    Primary path: BM25 + dense → RRF → top-k.
    Fallback cascade if hybrid returns nothing: phrase → keyword →
    uploaded-document concat → remote legislation.gov.uk.
    """
    hits = get_raw_context(query, max_chars=max_chars)
    if not hits:
        return ""
    if len(hits) == 1 and hits[0][0] == "legislation.gov.uk":
        return hits[0][1]
    upload_keys = set(sparse.list_upload_keys())
    if hits and all(k in upload_keys for k, _ in hits):
        full = "\n\n".join(snip for _, snip in hits)
        return f"**Full uploaded document:**\n{full[:max_chars]}\n\n"
    return _format_hits(hits, max_chars)


def gather_contexts(query: str) -> List[str]:
    """Return every retrieval snippet shown to the model for `query` — both
    graph hits (from `get_graph_boost`) and document hits (from
    `get_raw_context`). Used by the RAGAS pipeline as the `contexts` field
    for each row. Returns a flat `list[str]`; empty if no retrieval succeeds."""
    out: List[str] = []
    if ENABLE_GRAPH:
        gboost = get_graph_boost(query)
        for line in (gboost.get("context_md") or "").splitlines():
            line = line.strip()
            if line.startswith("- ") and len(line) > 4:
                out.append(line[2:])
    for _, snippet in get_raw_context(query):
        if snippet:
            out.append(snippet)
    return out


def get_graph_boost(query: str) -> Dict[str, object]:
    """Two-stage Neo4j boost.

    1. Fulltext seed retrieval on `provisionIdx` → top-K matches.
    2. 2-hop traversal via `:CITES`/`:MENTIONS`/`:DEFINED_BY` from those
       seeds → related provisions and their terms.

    Returns:
        {
            'context_md':  Markdown bullet block (seed hits + a few 2-hop related),
            'source_line': 'A | B | C' style citation line (seeds only — they're
                           the strongest match for the question),
            'must_terms':  sorted list of terms from seeds and 2-hop neighbours,
        }
    """
    if not ENABLE_GRAPH:
        return {"context_md": "", "source_line": "", "must_terms": []}

    cypher = """
    CALL db.index.fulltext.queryNodes('provisionIdx', $q) YIELD node, score
    WITH node, score
    OPTIONAL MATCH (t:Term)-[:MENTIONS]->(node)
    WITH node, score, collect(distinct t.name)[..8] AS terms
    RETURN node.cite AS cite, node.title AS title, node.text AS text,
           node.module AS module, node.domain AS domain,
           node.threshold AS threshold, node.deadline AS deadline,
           terms, score
    ORDER BY score DESC
    LIMIT $k
    """

    try:
        with get_session() as sess:
            if sess is None:
                return {"context_md": "", "source_line": "", "must_terms": []}
            recs = sess.run(cypher, q=query, k=6).data()
    except Exception as e:
        sparse._dbg(f"Neo4j query failed: {e}")
        return {"context_md": "", "source_line": "", "must_terms": []}

    if not recs:
        return {"context_md": "", "source_line": "", "must_terms": []}

    cites: List[str] = []
    must_terms: set[str] = set()
    bullets: List[str] = []
    for h in recs[:3]:
        cites.append(h.get("cite", ""))
        must_terms.update([t for t in (h.get("terms") or []) if t])
        snippet = (h.get("text") or "").replace("\n", " ")
        if len(snippet) > 220:
            snippet = snippet[:220] + "…"
        meta = ", ".join(
            x for x in [h.get("module"), h.get("domain"), h.get("threshold"), h.get("deadline")] if x
        )
        bullets.append(f"- **{h.get('cite','')}** — {h.get('title','')}. {snippet} ({meta})")

    # 2-hop expansion from seed cites — surface a few related provisions
    seed_cites = [c for c in cites if c]
    try:
        expansion = neighbors_2hop(seed_cites)
    except Exception as e:
        sparse._dbg(f"2-hop traversal failed: {e}")
        expansion = {"must_terms": [], "related_cites": [], "hops": {}}

    related = [c for c in expansion.get("related_cites", []) if c not in seed_cites][:5]
    if related:
        bullets.append("- *Related (2-hop)*: " + ", ".join(
            f"{c} ({expansion['hops'].get(c, '?')}-hop)" for c in related
        ))
    must_terms.update(expansion.get("must_terms", []))

    ctx = "**Graph hits:**\n" + "\n".join(bullets) + "\n\n" if bullets else ""
    source_line = " | ".join(seed_cites[:4])
    return {"context_md": ctx, "source_line": source_line, "must_terms": sorted(must_terms)}
