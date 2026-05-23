"""Neo4j traversal helpers.

Wraps the legacy `GraphClient` pattern around the shared driver in
`backend.graph.client`. Exposes:

    search_provisions(query, k)   — fulltext search on the `provisionIdx` index
    neighbors(cites)              — 1-hop traversal returning related cites + terms
    neighbors_2hop(cites)         — 2-hop traversal via :CITES|MENTIONS (Stage 3)
    build_graph_context(query)    — composes a source line + bullet block
"""

from __future__ import annotations

import re
from typing import Dict, List

from backend.graph.client import get_session

_CLEAN = re.compile(r"\s+")


def search_provisions(query: str, k: int = 6) -> List[Dict]:
    q = _CLEAN.sub(" ", query).strip()
    cypher = """
    CALL db.index.fulltext.queryNodes('provisionIdx', $q) YIELD node, score
    WITH node, score
    OPTIONAL MATCH (t:Term)-[:MENTIONS]->(node)
    WITH node, score, collect(distinct t.name)[..6] AS terms
    RETURN node.cite AS cite, node.title AS title, node.text AS text,
           node.module AS module, node.domain AS domain,
           node.threshold AS threshold, node.deadline AS deadline,
           terms, score
    ORDER BY score DESC
    LIMIT $k
    """
    with get_session() as sess:
        if sess is None:
            return []
        res = sess.run(cypher, q=q, k=k)
        return [r.data() for r in res]


def neighbors(cites: List[str], k_terms: int = 10) -> Dict:
    cypher = """
    UNWIND $cites AS c
    MATCH (p:Provision {cite: c})
    OPTIONAL MATCH (t:Term)-[:MENTIONS]->(p)
    WITH p, collect(distinct t.name) AS tnames
    OPTIONAL MATCH (p)-[:DEFINED_BY|:CITES|:RELATES_TO]->(q:Provision)
    WITH p, tnames, collect(distinct q.cite)[..6] AS related
    RETURN p.cite AS cite, p.title AS title, tnames[..$k_terms] AS terms, related
    """
    out = {"must_terms": set(), "related_cites": []}
    with get_session() as sess:
        if sess is None:
            out["must_terms"] = []
            return out
        res = sess.run(cypher, cites=cites, k_terms=k_terms)
        for r in res:
            out["must_terms"].update(r["terms"])
            out["related_cites"].extend(r["related"])
        out["must_terms"] = sorted({t for t in out["must_terms"] if t})
        out["related_cites"] = sorted({c for c in out["related_cites"] if c})
    return out


def neighbors_2hop(cites: List[str], max_hops: int = 2, limit: int = 20) -> Dict:
    """Two-hop traversal from each seed cite via `:CITES`, `:MENTIONS`, or
    `:DEFINED_BY` relationships (in either direction). Returns related
    provisions plus the terms attached to them, deduplicated.

    The 2-hop expansion includes paths like:
        seed -CITES-> related                  (cross-reference)
        seed -CITES-> X -CITES-> related       (transitive citation)
        seed <-MENTIONS- Term -MENTIONS-> related   (shared term)
    """
    if not cites:
        return {"must_terms": [], "related_cites": [], "hops": {}}
    cypher = """
    UNWIND $cites AS c
    MATCH (seed:Provision {cite: c})
    MATCH path = (seed)-[:CITES|MENTIONS|DEFINED_BY*1..%d]-(related:Provision)
    WHERE related <> seed
    WITH seed, related, min(length(path)) AS hops
    ORDER BY hops ASC
    WITH collect({related: related, hops: hops})[..$limit] AS matches
    UNWIND matches AS m
    WITH m.related AS related, m.hops AS hops
    OPTIONAL MATCH (t:Term)-[:MENTIONS]->(related)
    RETURN related.cite AS cite, related.title AS title,
           hops, collect(DISTINCT t.name)[..6] AS terms
    """ % max_hops
    out: Dict = {"must_terms": set(), "related_cites": [], "hops": {}}
    with get_session() as sess:
        if sess is None:
            out["must_terms"] = []
            return out
        res = sess.run(cypher, cites=cites, limit=limit)
        for r in res:
            cite = r["cite"]
            if cite and cite not in out["hops"]:
                out["related_cites"].append(cite)
                out["hops"][cite] = r["hops"]
            for term in r["terms"]:
                if term:
                    out["must_terms"].add(term)
        out["must_terms"] = sorted(out["must_terms"])
        out["related_cites"] = sorted(set(out["related_cites"]))
    return out


def build_graph_context(query: str, k: int = 5) -> Dict:
    """Compose a source line + bullet block from the top-k fulltext hits.

    Returns:
        {'source_line': 'A | B | C', 'must_terms': 'term1, term2', 'context_md': '...'}
    """
    hits = search_provisions(query, k=k)
    cites = [h["cite"] for h in hits]
    neigh = neighbors(cites)

    source_line = " | ".join(cites[:4]) if cites else ""
    must_terms = ", ".join(neigh["must_terms"][:8])
    bullets = []
    for h in hits[:3]:
        snippet = (h["text"] or "").replace("\n", " ")
        if len(snippet) > 220:
            snippet = snippet[:220] + "…"
        meta = ", ".join(
            x for x in [h["module"], h["domain"], h.get("threshold"), h.get("deadline")] if x
        )
        bullets.append(f"- **{h['cite']}** — {h['title']}. {snippet} ({meta})")
    context = "**Graph hits:**\n" + "\n".join(bullets) if bullets else ""
    return {"source_line": source_line, "must_terms": must_terms, "context_md": context}
