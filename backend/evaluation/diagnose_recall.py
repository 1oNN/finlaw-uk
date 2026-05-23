"""Diagnose why ragas_context_recall was 0.075 on the 20260523 run.

For 10 questions sampled (stratified by domain) from the latest per-question
CSV in ``data/eval_results/``, check:

    is_placeholder   — does the ground-truth match the literal
                       "Gold-standard answer for X, Y level." pattern
                       (or other placeholder/TBD/TODO/stub markers)?
                       This is the single most important signal: a
                       placeholder gold answer cannot be retrieved
                       regardless of retrieval quality.
    gt_in_corpus     — does the (non-placeholder) ground-truth string
                       have a 3-word substring in ANY document in
                       backend.retrieval.sparse._LOCAL_DB?
    gt_in_retrieved  — same check against the row's `contexts` field
                       (pipe-separated by " ||| ").
    top1_citation    — first UK regulatory citation extracted from `answer`.

Hard stop: if more than 2 of 10 sampled questions are placeholders OR
have no corpus match, this is a corpus/test-set quality problem rather
than a retrieval ranking problem, and Task 4 retrieval tuning will not
move the needle until the test-set is re-curated. The script exits
with code 2 in that case.

Usage:
    python -m backend.evaluation.diagnose_recall
    python -m backend.evaluation.diagnose_recall path/to/per_question.csv
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import pandas as pd

from backend.retrieval import sparse


EVAL_DIR = Path("data/eval_results")
QUESTIONS_CSV = Path("backend/evaluation/questions/questions_80_balanced.csv")
SAMPLE_SIZE = 10
STOP_THRESHOLD = 2          # >this many quality issues → halt
NGRAM_WORDS = 3             # n-word sliding window for substring check
RANDOM_SEED = 17

# Ground-truths that match this pattern are clearly placeholder text
# (e.g. "Gold-standard answer for FSMA, basic level.") rather than real
# gold answers. These cannot possibly retrieve from the corpus and will
# always score recall=0 regardless of retrieval quality.
_PLACEHOLDER_RE = re.compile(
    r"(?:^|\s)(?:gold[- ]?standard\s+answer|placeholder|tbd|todo|stub|fixture|n/?a)\b",
    re.IGNORECASE,
)


# Citation extraction — same patterns used elsewhere in the codebase for the
# UK regulatory short-forms. Kept local so this diagnostic does not import the
# Flask app module.
_CITE_PATTERNS = [
    r"FSMA\s*2000\s*s\.?\s*\d+[A-Za-z]?",
    r"COBS\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?",
    r"SYSC\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?",
    r"PRIN\s*\d+(?:\.\d+)*",
    r"CONC\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?",
    r"ICOBS\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?",
    r"MCOB\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?",
    r"PROD\s*\d+(?:\.\d+)*",
    r"DISP\s*\d+(?:\.\d+)*[A-Z]?(?:R|G)?",
    r"COMP\s*\d+(?:\.\d+)*",
    r"COLL\s*\d+(?:\.\d+)*",
    r"UK\s*MAR\s*art\.?\s*\d+[A-Za-z]?",
    r"MLR\s*2017\s*reg\.?\s*\d+[A-Za-z]?",
    r"PSR\s*2017\s*reg\.?\s*\d+[A-Za-z]?",
    r"RAO\s*2001\s*art\.?\s*\d+[A-Za-z]?",
    r"DTR\s*\d+(?:\.\d+)*",
]
_CITE_RE = re.compile("|".join(_CITE_PATTERNS), re.IGNORECASE)


def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip the underscores / periods that
    sometimes appear inside citation IDs (`s.19` → `s19`)."""
    if not text:
        return ""
    out = text.lower()
    out = re.sub(r"[._]+", "", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _ngrams(words: List[str], n: int) -> Iterable[str]:
    for i in range(len(words) - n + 1):
        yield " ".join(words[i : i + n])


def _has_substring_match(needle: str, haystack: str, n: int = NGRAM_WORDS) -> bool:
    """Return True iff any n-word window of `needle` is a substring of
    `haystack` (both pre-normalised)."""
    words = needle.split()
    if len(words) < n:
        return bool(words) and needle in haystack
    return any(window in haystack for window in _ngrams(words, n))


def _top1_citation(answer: str) -> str:
    if not answer:
        return ""
    m = _CITE_RE.search(answer)
    return m.group(0) if m else ""


def _is_placeholder(gt: str) -> bool:
    return bool(_PLACEHOLDER_RE.search(gt or ""))


def _count_placeholders_in_test_set(questions_csv: Path = QUESTIONS_CSV) -> Tuple[int, int]:
    """Return (n_placeholder, n_total) for the source test-set CSV.

    Done against the question CSV (not the eval results) because the eval
    results file copies gold_answer into `ground_truth` and we want to
    report on the source of truth.
    """
    if not questions_csv.exists():
        return 0, 0
    qdf = pd.read_csv(questions_csv)
    if "gold_answer" not in qdf.columns:
        return 0, 0
    n_total = len(qdf)
    n_placeholder = int(qdf["gold_answer"].apply(_is_placeholder).sum())
    return n_placeholder, n_total


def _latest_per_question_csv() -> Path:
    excluded = ("summary", "diagnose_recall", "ablation")
    matches = sorted(
        p for p in EVAL_DIR.glob("eval_results_ragas_*.csv")
        if not any(tag in p.name for tag in excluded)
    )
    if not matches:
        raise FileNotFoundError(f"No per-question CSV found in {EVAL_DIR}")
    return matches[-1]


def _stratified_sample(df: pd.DataFrame, k: int, seed: int) -> pd.DataFrame:
    """Spread `k` rows across the domain values present in `df`."""
    domains = sorted(df["domain"].dropna().unique())
    if not domains:
        return df.sample(n=min(k, len(df)), random_state=seed)
    per = max(1, k // len(domains))
    pieces = []
    for d in domains:
        sub = df[df["domain"] == d]
        pieces.append(sub.sample(n=min(per, len(sub)), random_state=seed))
    out = pd.concat(pieces)
    if len(out) < k:
        remainder = df.drop(out.index).sample(
            n=min(k - len(out), len(df) - len(out)), random_state=seed,
        )
        out = pd.concat([out, remainder])
    return out.head(k).reset_index(drop=True)


def diagnose(csv_path: Optional[Path] = None) -> int:
    csv_path = csv_path or _latest_per_question_csv()
    df = pd.read_csv(csv_path)
    print(f"Diagnosing {csv_path.name} ({len(df)} rows)")
    print()

    n_ph, n_total = _count_placeholders_in_test_set()
    if n_total:
        print(f"Test-set-wide placeholder gold_answer rows: "
              f"{n_ph}/{n_total} ({n_ph * 100 // n_total}%)")
        print()

    sample = _stratified_sample(df, SAMPLE_SIZE, RANDOM_SEED)
    print(f"Sampled {len(sample)} rows stratified by domain "
          f"({sorted(sample['domain'].unique())})")
    print()

    # Pre-normalise the corpus once so the n-gram check is fast.
    corpus_norm: List[Tuple[str, str]] = [
        (key, _normalise(text)) for key, text in sparse._LOCAL_DB.items()
    ]
    print(f"Corpus: {len(corpus_norm)} documents from sparse._LOCAL_DB")
    print()

    header = (f"{'qid':5s}  {'domain':10s}  {'placeholder':11s}  "
              f"{'gt_in_corpus':12s}  {'gt_in_retrieved':15s}  top1_citation")
    print(header)
    print("-" * len(header))

    miss_corpus = 0
    miss_retrieved = 0
    placeholder = 0
    rows_out: List[dict] = []

    for _, row in sample.iterrows():
        raw_gt = str(row.get("ground_truth", ""))
        gt = _normalise(raw_gt)
        ctxs = _normalise(str(row.get("contexts", "")))
        ans = str(row.get("answer", ""))

        is_ph = _is_placeholder(raw_gt)
        # Don't bother running corpus / retrieval checks against placeholder
        # gold answers — the substring search would just confirm the obvious.
        in_corpus = (
            False if is_ph
            else any(_has_substring_match(gt, doc_norm) for _, doc_norm in corpus_norm)
        )
        in_retrieved = False if is_ph else _has_substring_match(gt, ctxs)
        top1 = _top1_citation(ans)

        if is_ph:
            placeholder += 1
        if not is_ph and not in_corpus:
            miss_corpus += 1
        if not is_ph and not in_retrieved:
            miss_retrieved += 1

        print(
            f"{str(row['qid']):5s}  {str(row['domain']):10s}  "
            f"{str(is_ph):11s}  "
            f"{str(in_corpus):12s}  {str(in_retrieved):15s}  {top1 or '(none)'}"
        )
        rows_out.append({
            "qid": row["qid"],
            "domain": row["domain"],
            "is_placeholder": is_ph,
            "gt_in_corpus": in_corpus,
            "gt_in_retrieved": in_retrieved,
            "top1_citation": top1,
        })

    print()
    quality_issues = placeholder + miss_corpus
    print(f"Summary: placeholders {placeholder}/{SAMPLE_SIZE}, "
          f"corpus misses (real GTs) {miss_corpus}/{SAMPLE_SIZE}, "
          f"retrieved misses (real GTs) {miss_retrieved}/{SAMPLE_SIZE}, "
          f"total quality issues {quality_issues}/{SAMPLE_SIZE}")

    out_path = csv_path.parent / f"{csv_path.stem}_diagnose_recall.csv"
    pd.DataFrame(rows_out).to_csv(out_path, index=False)
    print(f"Wrote {out_path}")

    if quality_issues > STOP_THRESHOLD:
        print()
        print("=" * 72)
        print("STOP: TEST-SET QUALITY PROBLEM, NOT A RETRIEVAL PROBLEM")
        print("=" * 72)
        print(f"  Placeholders in sample:      {placeholder}/{SAMPLE_SIZE}")
        print(f"  Corpus misses (real GTs):    {miss_corpus}/{SAMPLE_SIZE}")
        if n_total:
            print(f"  Placeholders in full test:   {n_ph}/{n_total} "
                  f"({n_ph * 100 // n_total}%)")
            print(f"  Expected recall floor:       {(n_total - n_ph) / n_total:.4f} "
                  f"(only the {n_total - n_ph} real GTs are scorable)")
        print()
        print("Task 4 retrieval tuning will NOT move recall against this set.")
        print("Re-curate the placeholders OR drop them and re-eval on n<80")
        print("before running retrieval ablation.")
        print("=" * 72)
        return 2

    return 0


if __name__ == "__main__":
    arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.exit(diagnose(arg))
