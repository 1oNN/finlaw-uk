"""Graph-grounded citation verification — the dissertation's
"symbolic verification" mechanism.

For every short-form citation that appears in a model-generated answer:

    1. Normalise via `citations.normalise_citations` so near-misses
       (`COBS 4.2`, `COBS 4.2.1 R`) collapse onto the canonical short-form.
    2. Look up the citation against `(:Provision {cite: ...})` in Neo4j.
       A match means the citation refers to a provision the graph knows
       about; a miss means the model invented (or misrendered) it.
    3. Optionally, cross-check that every cited provision was actually
       present in the context the retriever surfaced — a citation the
       model "remembered" without any retrieval support is flagged as
       potentially hallucinated.

The check fails open: if Neo4j is unavailable the function returns
permissive defaults plus a `note` field so the caller can surface the
degraded mode to the user.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Set

from backend.graph.client import get_session
from backend.graph.extract_xrefs import extract_from_clause
from backend.verification.citations import normalise_citations


def _extract_cites(answer_text: str) -> List[str]:
    """Pull the citation set out of an answer, with near-miss normalisation."""
    if not answer_text:
        return []
    normalised = normalise_citations(answer_text)
    return extract_from_clause(normalised)


def verify_citation_against_graph(cite: str) -> bool:
    """Return True iff a `Provision` node with this exact `cite` exists.

    The lookup is exact-match (Neo4j string equality); we rely on
    `normalise_citations` to have already collapsed common variants
    onto the canonical short-form before this is called."""
    if not cite:
        return False
    try:
        with get_session() as sess:
            if sess is None:
                return False
            result = sess.run(
                "MATCH (p:Provision {cite: $cite}) RETURN p.id AS id LIMIT 1",
                cite=cite,
            ).single()
            return result is not None
    except Exception:
        return False


def verify_citations_batch(cites: Iterable[str]) -> Set[str]:
    """Single-roundtrip variant of `verify_citation_against_graph` — returns
    the subset of `cites` that exist in the graph."""
    cite_list = [c for c in cites if c]
    if not cite_list:
        return set()
    try:
        with get_session() as sess:
            if sess is None:
                return set()
            result = sess.run(
                "UNWIND $cites AS c MATCH (p:Provision {cite: c}) RETURN DISTINCT c AS cite",
                cites=cite_list,
            )
            return {r["cite"] for r in result}
    except Exception:
        return set()


def verify_answer(answer_text: str, context_cites: Iterable[str] = ()) -> Dict:
    """Audit every citation in `answer_text`.

    Args:
        answer_text: the full model-generated response (Markdown).
        context_cites: the citations the retriever surfaced to the model,
            usually `gboost['source_line'].split('|')`. Used to flag
            citations that appear in the answer without ever having been
            shown to the model.

    Returns:
        {
            'all_grounded': bool,            # every cited provision exists in the graph
            'all_retrieved': bool,           # every cited provision was in the context
            'verified':    list[str],        # cites that pass the graph lookup
            'unverified':  list[str],        # cites that fail the graph lookup
            'hallucinated_context': list[str], # cites not in `context_cites`
            'note': str,                     # diagnostic when graph unavailable
        }
    """
    cites = _extract_cites(answer_text)
    context_set: Set[str] = {c.strip() for c in context_cites if c and c.strip()}

    if not cites:
        return {
            "all_grounded": True,
            "all_retrieved": True,
            "verified": [],
            "unverified": [],
            "hallucinated_context": [],
            "note": "no_citations",
        }

    verified_set = verify_citations_batch(cites)

    # If the batch returned empty and we expected hits, the graph is probably down.
    note = ""
    if not verified_set:
        # Try a single lookup to confirm; if that also fails it's a degraded run.
        if not verify_citation_against_graph(cites[0]):
            note = "graph_unavailable"

    verified: List[str] = []
    unverified: List[str] = []
    seen = set()
    for c in cites:
        if c in seen:
            continue
        seen.add(c)
        if c in verified_set:
            verified.append(c)
        else:
            unverified.append(c)

    hallucinated_context = [c for c in cites if context_set and c not in context_set]

    if note == "graph_unavailable":
        # Fail open: don't penalise the model when we can't actually check.
        return {
            "all_grounded": True,
            "all_retrieved": True,
            "verified": [],
            "unverified": [],
            "hallucinated_context": hallucinated_context,
            "note": note,
        }

    return {
        "all_grounded": len(unverified) == 0,
        "all_retrieved": len(hallucinated_context) == 0,
        "verified": verified,
        "unverified": unverified,
        "hallucinated_context": hallucinated_context,
        "note": note,
    }
