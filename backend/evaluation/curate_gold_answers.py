"""Re-curate placeholder gold-answers in the eval question set.

Background: the 20260523 RAGAS run revealed 70/80 questions had gold-answers
of the form "Gold-standard answer for X, Y level." rather than real factual
ground-truth text. RAGAS context_recall scored those rows at 0 regardless of
retrieval quality, dragging the mean to 0.075. Diagnosed by
``backend/evaluation/diagnose_recall.py``.

This script drafts replacement gold-answers grounded in the actual corpus:

    1. Load ``questions_80_balanced.csv``.
    2. For each placeholder row, fetch every Provision in
       ``expected_citations`` from Neo4j by short-form cite.
    3. If Neo4j returns no Provisions for a row, fall back to a fulltext
       search of the question against the ``provisionIdx`` index, then
       failing that, sparse retrieval against ``_LOCAL_DB``.
    4. Prompt Mistral with the question + the retrieved source text and
       a strict "answer in 1-2 sentences from this text only OR reply
       NEEDS_MANUAL_CURATION" instruction.
    5. Write ``questions_80_curated.csv`` with the new gold-answers; the
       schema is identical to the input so it's a drop-in replacement.
       Original CSV is left intact.

The output also includes a ``curation_status`` column:
    'llm_drafted'              — model produced a grounded answer
    'kept_original'            — row was already curated (non-placeholder)
    'needs_manual'             — sources missing or LLM declined

The user is expected to spot-check 'llm_drafted' rows and manually fill
the 'needs_manual' rows before running the next eval.

Usage:
    python -m backend.evaluation.curate_gold_answers
    python -m backend.evaluation.curate_gold_answers --limit 5     # first 5
    python -m backend.evaluation.curate_gold_answers --dry-run     # no LLM
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from backend.evaluation.diagnose_recall import _is_placeholder
from backend.graph.traversal import search_provisions
from backend.graph.client import get_session
from backend.llm.ollama_client import generate_stream
from backend.retrieval import sparse


QUESTIONS_CSV = Path("backend/evaluation/questions/questions_80_balanced.csv")
CURATED_CSV   = Path("backend/evaluation/questions/questions_80_curated.csv")

REFUSAL_TOKEN = "NEEDS_MANUAL_CURATION"


CURATE_PROMPT = (
    "You are drafting a gold-standard reference answer for a legal QA "
    "evaluation. Read the SOURCE TEXT carefully and answer the QUESTION "
    "in ONE or TWO sentences using ONLY the source text below.\n\n"
    "STRICT RULES:\n"
    "  - Include the specific threshold, deadline, or duty mentioned in "
    "the source (e.g. \"£85,000\", \"8 weeks\", \"14 days\").\n"
    "  - Do NOT include citations, '[brackets]', 'Source:' lines, or URLs.\n"
    "  - Do NOT use prior knowledge outside the source text.\n"
    f"  - If the source text does not directly answer the question, "
    f"reply EXACTLY: {REFUSAL_TOKEN}\n"
    "  - No preamble, no 'Answer:', just the factual answer text.\n"
)


def _fetch_provision_by_cite(cite: str) -> Optional[Dict[str, str]]:
    """Direct lookup by `Provision.cite`. Returns None if not found."""
    cypher = (
        "MATCH (p:Provision) "
        "WHERE p.cite = $c OR toLower(p.cite) = toLower($c) "
        "RETURN p.cite AS cite, p.title AS title, p.text AS text "
        "LIMIT 1"
    )
    with get_session() as sess:
        if sess is None:
            return None
        rec = sess.run(cypher, c=cite).single()
        return rec.data() if rec else None


def _gather_source_text(question: str, expected_citations: str) -> Tuple[str, str]:
    """Return (source_text, source_label).

    Priority:
      1. Neo4j Provision lookup by each expected_citation token.
      2. Neo4j fulltext on the question via provisionIdx.
      3. Sparse retrieval against _LOCAL_DB.
    """
    cites = [c.strip() for c in re.split(r"[|,]", expected_citations or "") if c.strip()]
    chunks: List[str] = []
    used_cites: List[str] = []

    for c in cites:
        prov = _fetch_provision_by_cite(c)
        if prov and prov.get("text"):
            chunks.append(f"[{prov['cite']}] {prov.get('title','')}\n{prov['text']}")
            used_cites.append(prov["cite"])

    if not chunks:
        hits = search_provisions(question, k=3) or []
        for h in hits:
            if h.get("text"):
                chunks.append(f"[{h['cite']}] {h.get('title','')}\n{h['text']}")
                used_cites.append(h["cite"])

    if not chunks:
        q_tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
        for key, text in sparse._LOCAL_DB.items():
            if not text:
                continue
            t_lower = text.lower()
            hits = sum(1 for tok in q_tokens if tok in t_lower)
            if hits >= 4:
                chunks.append(f"[{key}]\n{text[:1500]}")
                used_cites.append(key)
                if len(chunks) >= 2:
                    break

    return "\n\n".join(chunks), " | ".join(used_cites)


def _llm_draft(question: str, source_text: str) -> str:
    """Ask Mistral to draft a grounded answer. Empty string = decline."""
    if not source_text.strip():
        return ""
    messages = [
        {"role": "system", "content": CURATE_PROMPT},
        {"role": "user", "content": f"QUESTION: {question}\n\nSOURCE TEXT:\n{source_text}"},
    ]
    parts: List[str] = []
    try:
        for tok in generate_stream(
            messages, model_id=None,
            options={"temperature": 0.0, "top_p": 0.9, "num_predict": 200},
        ):
            parts.append(tok)
    except Exception as e:
        print(f"  LLM error: {e}", file=sys.stderr)
        return ""
    answer = "".join(parts).strip()
    if REFUSAL_TOKEN in answer:
        return ""
    return answer


def curate(limit: Optional[int] = None, dry_run: bool = False) -> Path:
    df = pd.read_csv(QUESTIONS_CSV)
    print(f"Loaded {len(df)} questions from {QUESTIONS_CSV}")

    placeholder_mask = df["gold_answer"].apply(_is_placeholder)
    n_placeholder = int(placeholder_mask.sum())
    print(f"Found {n_placeholder} placeholder rows (will be re-drafted)")
    if limit:
        print(f"Limiting to first {limit} placeholder rows")

    new_gold: List[str] = []
    statuses: List[str] = []
    used_sources: List[str] = []

    redrafted = 0
    needs_manual = 0
    kept = 0

    for idx, row in df.iterrows():
        if not _is_placeholder(row["gold_answer"]):
            new_gold.append(row["gold_answer"])
            statuses.append("kept_original")
            used_sources.append(str(row.get("expected_citations", "")))
            kept += 1
            continue

        if limit is not None and redrafted + needs_manual >= limit:
            new_gold.append(row["gold_answer"])
            statuses.append("kept_original")
            used_sources.append("")
            continue

        question = str(row["question"])
        expected_cites = str(row.get("expected_citations", ""))

        if dry_run:
            new_gold.append(row["gold_answer"])
            statuses.append("dry_run_skip")
            used_sources.append("")
            continue

        source_text, used = _gather_source_text(question, expected_cites)
        if not source_text.strip():
            new_gold.append(row["gold_answer"])
            statuses.append("needs_manual")
            used_sources.append("")
            needs_manual += 1
            print(f"  Q{row['id']:>4} [{row['domain']:>7s}] no source found; needs manual curation")
            continue

        answer = _llm_draft(question, source_text)
        if not answer:
            new_gold.append(row["gold_answer"])
            statuses.append("needs_manual")
            used_sources.append(used)
            needs_manual += 1
            print(f"  Q{row['id']:>4} [{row['domain']:>7s}] LLM declined; needs manual")
            continue

        new_gold.append(answer)
        statuses.append("llm_drafted")
        used_sources.append(used)
        redrafted += 1
        ans_preview = answer[:90].replace("\n", " ")
        print(f"  Q{row['id']:>4} [{row['domain']:>7s}] {ans_preview}")

    out_df = df.copy()
    out_df["gold_answer"] = new_gold
    out_df["curation_status"] = statuses
    out_df["curation_source_cites"] = used_sources
    out_df.to_csv(CURATED_CSV, index=False)

    print()
    print(f"Drafted (LLM):     {redrafted}")
    print(f"Needs manual:      {needs_manual}")
    print(f"Kept original:     {kept}")
    print(f"Wrote {CURATED_CSV}")
    return CURATED_CSV


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None,
                   help="Re-draft only the first N placeholder rows (smoke test)")
    p.add_argument("--dry-run", action="store_true",
                   help="Skip LLM calls; just report what would change")
    args = p.parse_args()
    curate(limit=args.limit, dry_run=args.dry_run)
