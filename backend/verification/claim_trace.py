"""Citation-grounded claim tracing.

Walks a model-generated answer sentence by sentence and, for each factual
claim, scores it against the texts of the provisions cited in that answer.
The "best supporter" for each claim is the cited provision with the most
token overlap.

This is the dissertation's "claim trace" deliverable: each load-bearing
sentence ends up paired with the legal source whose text most closely
echoes it. Token overlap is a baseline; a future iteration could swap in
NLI (e.g. DeBERTa-v3-mnli) for semantic entailment scoring.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

from backend.graph.client import get_session

_WORD_RE = re.compile(r"[a-z]{3,}")
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "these", "those", "from",
    "into", "such", "have", "has", "had", "been", "being", "will", "would",
    "may", "must", "shall", "should", "can", "any", "all", "are", "was",
    "were", "but", "not", "you", "your", "our", "his", "her", "its",
    "they", "their", "them", "who", "what", "when", "where", "why", "how",
    "which", "whose", "whom", "between", "under", "over", "about", "above",
    "below", "before", "after", "during", "through", "until", "while",
    "because", "although", "however", "therefore", "thus", "also", "only",
    "than", "then", "there", "here", "where", "more", "less", "most", "least",
    "each", "every", "some", "many", "few", "other", "another", "same",
    "uses", "used", "use",
}


def _tokens(text: str) -> List[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS]


def extract_claims(answer_text: str, min_length: int = 25) -> List[str]:
    """Split an answer into sentence-level factual claims.

    Skips: blank lines, Markdown headers, the trailing 'Source:' line,
    citation-only bullets, and very short fragments. Bullet markers and
    numbered prefixes are stripped from sentence starts."""
    if not answer_text:
        return []
    claims: List[str] = []
    for raw in answer_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if re.match(r"^\s*source\s*:\s*", line, re.I):
            continue
        if re.match(r"^>", line):
            continue
        cleaned = re.sub(r"^[-*•]\s+", "", line)
        cleaned = re.sub(r"^\d+\.\s+", "", cleaned)
        cleaned = re.sub(r"^[`*_]+|[`*_]+$", "", cleaned)
        if not cleaned:
            continue
        # Sentence-segment on . ! ? followed by whitespace.
        for sent in re.split(r"(?<=[.!?])\s+", cleaned):
            sent = sent.strip()
            if len(sent) >= min_length:
                claims.append(sent)
    return claims


def fetch_provision_texts(cites: Iterable[str]) -> Dict[str, str]:
    """Return `{cite: text}` for cited provisions. One Cypher round-trip;
    falls back to an empty dict if the graph is unavailable."""
    cite_list = [c for c in cites if c]
    if not cite_list:
        return {}
    try:
        with get_session() as sess:
            if sess is None:
                return {}
            res = sess.run(
                """
                UNWIND $cites AS c
                MATCH (p:Provision {cite: c})
                RETURN c AS cite, head(collect(p.text)) AS text
                """,
                cites=cite_list,
            )
            return {r["cite"]: (r["text"] or "") for r in res}
    except Exception:
        return {}


def trace_claim_to_provision(
    claim: str, provision_texts: Dict[str, str]
) -> Optional[Dict]:
    """Find the cited provision whose text most overlaps with the claim.

    Returns `{cite, score, normalised_overlap}` or None if no provision
    has any overlap. The score is the count of non-stopword tokens
    appearing in both the claim and the provision; the `normalised_overlap`
    divides by the claim's token count for a 0–1 confidence-like figure."""
    claim_tokens = set(_tokens(claim))
    if not claim_tokens:
        return None
    best_cite: Optional[str] = None
    best_score = 0
    for cite, text in provision_texts.items():
        if not text:
            continue
        prov_tokens = set(_tokens(text))
        score = len(claim_tokens & prov_tokens)
        if score > best_score:
            best_score = score
            best_cite = cite
    if best_cite is None or best_score == 0:
        return None
    return {
        "cite": best_cite,
        "score": best_score,
        "normalised_overlap": round(best_score / max(1, len(claim_tokens)), 3),
    }


def trace_all(
    answer_text: str,
    cites: Iterable[str],
    *,
    provision_texts: Optional[Dict[str, str]] = None,
) -> List[Dict]:
    """Full per-claim trace: every claim mapped to its best supporting cite.

    Args:
        answer_text: the model's response (Markdown).
        cites: the cited provisions (typically from `gboost['source_line']`
            plus anything else extracted from the answer).
        provision_texts: optional pre-fetched `{cite: text}` map — pass
            this to avoid an extra Neo4j round-trip when the caller has
            already loaded the texts.

    Returns:
        list of `{claim, best_match}` records. `best_match` is None when no
        cited provision provided enough overlap to be a credible supporter.
    """
    claims = extract_claims(answer_text)
    if not claims:
        return []
    if provision_texts is None:
        provision_texts = fetch_provision_texts(cites)
    out: List[Dict] = []
    for claim in claims:
        out.append({
            "claim": claim[:240],
            "best_match": trace_claim_to_provision(claim, provision_texts),
        })
    return out
