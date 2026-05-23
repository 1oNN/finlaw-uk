"""Combined evaluation runner — lexical + RAGAS.

Orchestrates a single evaluation pass over the question CSV:

    1. Load questions (optionally a head sample).
    2. Run the FinLaw-UK RAG pipeline once per question, capturing
       (answer, contexts, runtime).
    3. Compute lexical metrics (Jaccard, ROUGE-L, citation-match,
       keyword-F1) directly from the captured answer + ground truth.
    4. Optionally run RAGAS scoring against the same records using a
       local Mistral judge (Ollama by default; HF transformers opt-in).
    5. Write a single combined CSV with all per-question scores plus a
       summary row of metric means.

Designed to be importable (`runner.run(...)`) and also driven from the
CLI in `scripts/run_evaluation.py`.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from backend.evaluation.ragas_eval import (
    EVAL_OUTPUT_DIR,
    EvalRecord,
    QUESTIONS_CSV,
    _ragas_evaluate,
    load_questions,
    run_rag_pipeline,
)

log = logging.getLogger(__name__)


@dataclass
class LexicalScores:
    jaccard: float = 0.0
    rouge_l: float = 0.0
    citation_match: float = 0.0
    keyword_f1: float = 0.0


_WORD_RE = re.compile(r"[A-Za-z0-9£]+")


def _tokens(s: str) -> List[str]:
    return _WORD_RE.findall((s or "").lower())


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(_tokens(a)), set(_tokens(b))
    if not ta and not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / max(1, len(union))


def _rouge_l(answer: str, reference: str) -> float:
    """Longest-common-subsequence ratio as a stand-in for ROUGE-L F1.

    Uses `rouge` library when available; otherwise falls back to
    `difflib.SequenceMatcher.ratio()` which approximates the same idea."""
    if not answer or not reference:
        return 0.0
    try:
        from rouge import Rouge
        scores = Rouge().get_scores(answer, reference)
        return float(scores[0]["rouge-l"]["f"])
    except Exception:
        return SequenceMatcher(None, answer.lower(), reference.lower()).ratio()


def _citation_match(answer: str, expected_citations: str) -> float:
    """Fraction of expected pipe-separated citations that appear in the answer."""
    cites = [c.strip() for c in (expected_citations or "").split("|") if c.strip()]
    if not cites:
        return 0.0
    found = sum(1 for c in cites if c.lower() in (answer or "").lower())
    return found / len(cites)


def _keyword_f1(answer: str, expected_keywords: str) -> float:
    """Token-level F1 against pipe-separated expected keywords."""
    expected = {k.strip().lower() for k in (expected_keywords or "").split("|") if k.strip()}
    if not expected:
        return 0.0
    answer_tokens = set(_tokens(answer))
    tp = len(expected & answer_tokens)
    if tp == 0:
        return 0.0
    precision = tp / max(1, len(expected))
    recall = tp / max(1, len(expected))
    return 2 * precision * recall / max(1e-6, (precision + recall))


def compute_lexical(record: EvalRecord, expected_keywords: str = "") -> LexicalScores:
    return LexicalScores(
        jaccard=_jaccard(record.answer, record.ground_truth),
        rouge_l=_rouge_l(record.answer, record.ground_truth),
        citation_match=_citation_match(record.answer, record.expected_citations),
        keyword_f1=_keyword_f1(record.answer, expected_keywords),
    )


def run(
    *,
    mode: str = "both",
    sample: Optional[int] = None,
    judge: str = "ollama",
    output_dir: Path = EVAL_OUTPUT_DIR,
    questions_path: Path = QUESTIONS_CSV,
) -> Path:
    """Run the chosen evaluation mode end-to-end. Returns the combined CSV path.

    `mode` ∈ {'lexical', 'ragas', 'both'}.
    """
    if mode not in ("lexical", "ragas", "both"):
        raise ValueError(f"mode must be one of lexical/ragas/both, got {mode!r}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = load_questions(questions_path, sample=sample)
    # Capture expected_keywords for lexical scoring (not on the dataclass)
    raw = pd.read_csv(questions_path)
    if sample is not None:
        raw = raw.head(sample)
    expected_keywords_by_qid: Dict[str, str] = {
        str(row["id"]): str(row.get("expected_keywords", ""))
        for _, row in raw.iterrows()
    }

    print(f"Loaded {len(records)} questions; mode={mode}, judge={judge}")

    # ---- Step 1: run the RAG pipeline for every question -----
    for i, r in enumerate(records, start=1):
        try:
            answer, contexts, runtime_s = run_rag_pipeline(r.question)
            r.answer = answer
            r.contexts = contexts
            r.runtime_s = round(runtime_s, 2)
            print(f"  [{i}/{len(records)}] {r.qid} ({runtime_s:.1f}s)")
        except Exception as e:
            r.error = str(e)
            print(f"  [{i}/{len(records)}] {r.qid} ERROR: {e}")

    # ---- Step 2: lexical scoring (always cheap; computed from captured data) -----
    lex_rows: Dict[str, LexicalScores] = {}
    if mode in ("lexical", "both"):
        for r in records:
            lex_rows[r.qid] = compute_lexical(
                r, expected_keywords=expected_keywords_by_qid.get(r.qid, "")
            )

    # ---- Step 3: RAGAS scoring (LLM-heavy, gated on mode) -----
    if mode in ("ragas", "both"):
        print(f"Running RAGAS judge ({judge}) …")
        try:
            _ragas_evaluate(records, judge=judge)
        except Exception as e:
            log.exception("RAGAS scoring failed: %s", e)
            print(f"RAGAS scoring failed: {e}")

    # ---- Step 4: combined CSV + summary -----
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"eval_results_{mode}_{timestamp}.csv"
    summary_path = output_dir / f"eval_results_{mode}_{timestamp}_summary.csv"

    rows = []
    for r in records:
        row = {k: v for k, v in asdict(r).items() if k != "contexts"}
        row["contexts"] = " ||| ".join(r.contexts) if r.contexts else ""
        if r.qid in lex_rows:
            ls = lex_rows[r.qid]
            row["lex_jaccard"] = round(ls.jaccard, 4)
            row["lex_rouge_l"] = round(ls.rouge_l, 4)
            row["lex_citation_match"] = round(ls.citation_match, 4)
            row["lex_keyword_f1"] = round(ls.keyword_f1, 4)
        rows.append(row)
    pd.DataFrame(rows).to_csv(out_path, index=False)

    _write_summary(records, lex_rows, summary_path, mode=mode)
    print(f"Per-question results: {out_path}")
    print(f"Summary:              {summary_path}")
    return out_path


def run_streaming(
    *,
    mode: str = "ragas",
    sample: Optional[int] = 5,
    judge: str = "ollama",
    output_dir: Path = EVAL_OUTPUT_DIR,
    questions_path: Path = QUESTIONS_CSV,
):
    """Generator twin of `run()` — yields progress events so a web frontend
    can stream them as Server-Sent Events. Each yielded value is a dict:

        {"event": "<name>", "data": {...}}

    Events: start, loaded, question, question_error, phase, ragas_error,
    done.

    Side-effects are the same as `run()` — writes the per-question CSV +
    summary CSV under `output_dir`.
    """
    if mode not in ("lexical", "ragas", "both"):
        raise ValueError(f"mode must be one of lexical/ragas/both, got {mode!r}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    yield {"event": "start", "data": {"mode": mode, "sample": sample, "judge": judge}}

    records = load_questions(questions_path, sample=sample)
    raw = pd.read_csv(questions_path)
    if sample is not None:
        raw = raw.head(sample)
    expected_keywords_by_qid: Dict[str, str] = {
        str(row["id"]): str(row.get("expected_keywords", ""))
        for _, row in raw.iterrows()
    }
    total = len(records)
    yield {"event": "loaded", "data": {"total": total}}

    yield {"event": "phase", "data": {"phase": "pipeline"}}
    for i, r in enumerate(records, start=1):
        try:
            answer, contexts, runtime_s = run_rag_pipeline(r.question)
            r.answer = answer
            r.contexts = contexts
            r.runtime_s = round(runtime_s, 2)
            yield {
                "event": "question",
                "data": {
                    "i": i,
                    "total": total,
                    "qid": r.qid,
                    "domain": r.domain,
                    "complexity": r.complexity,
                    "question": r.question,
                    "answer": r.answer,
                    "ground_truth": r.ground_truth,
                    "expected_citations": r.expected_citations,
                    "runtime_s": r.runtime_s,
                },
            }
        except Exception as e:
            r.error = str(e)
            yield {
                "event": "question_error",
                "data": {"i": i, "total": total, "qid": r.qid, "error": str(e)},
            }

    lex_rows: Dict[str, LexicalScores] = {}
    if mode in ("lexical", "both"):
        yield {"event": "phase", "data": {"phase": "lexical"}}
        for r in records:
            lex_rows[r.qid] = compute_lexical(
                r, expected_keywords=expected_keywords_by_qid.get(r.qid, "")
            )

    if mode in ("ragas", "both"):
        yield {"event": "phase", "data": {"phase": "ragas_judge"}}
        try:
            _ragas_evaluate(records, judge=judge)
        except Exception as e:
            log.exception("RAGAS scoring failed: %s", e)
            yield {"event": "ragas_error", "data": {"error": str(e)}}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"eval_results_{mode}_{timestamp}.csv"
    summary_path = output_dir / f"eval_results_{mode}_{timestamp}_summary.csv"

    rows = []
    per_question_summary = []
    for r in records:
        row = {k: v for k, v in asdict(r).items() if k != "contexts"}
        row["contexts"] = " ||| ".join(r.contexts) if r.contexts else ""
        if r.qid in lex_rows:
            ls = lex_rows[r.qid]
            row["lex_jaccard"] = round(ls.jaccard, 4)
            row["lex_rouge_l"] = round(ls.rouge_l, 4)
            row["lex_citation_match"] = round(ls.citation_match, 4)
            row["lex_keyword_f1"] = round(ls.keyword_f1, 4)
        rows.append(row)
        per_question_summary.append({
            "qid": r.qid,
            "domain": r.domain,
            "complexity": r.complexity,
            "question": r.question,
            "answer": r.answer,
            "ground_truth": r.ground_truth,
            "runtime_s": r.runtime_s,
            "error": r.error,
            "ragas_faithfulness": r.ragas_faithfulness,
            "ragas_answer_relevancy": r.ragas_answer_relevancy,
            "ragas_context_precision": r.ragas_context_precision,
            "ragas_context_recall": r.ragas_context_recall,
            "lex_jaccard": rows[-1].get("lex_jaccard"),
            "lex_rouge_l": rows[-1].get("lex_rouge_l"),
            "lex_citation_match": rows[-1].get("lex_citation_match"),
            "lex_keyword_f1": rows[-1].get("lex_keyword_f1"),
        })
    pd.DataFrame(rows).to_csv(out_path, index=False)
    _write_summary(records, lex_rows, summary_path, mode=mode)

    summary: Dict[str, float] = {
        "questions": total,
        "errors": sum(1 for r in records if r.error),
        "runtime_total_s": round(sum(r.runtime_s for r in records), 1),
    }
    if mode in ("lexical", "both") and lex_rows:
        for metric in ("jaccard", "rouge_l", "citation_match", "keyword_f1"):
            vals = [getattr(ls, metric) for ls in lex_rows.values()]
            summary[f"lex_{metric}_mean"] = round(sum(vals) / max(1, len(vals)), 4)
    if mode in ("ragas", "both"):
        for col in ("ragas_faithfulness", "ragas_answer_relevancy",
                    "ragas_context_precision", "ragas_context_recall"):
            vals = [getattr(r, col) for r in records if isinstance(getattr(r, col), (int, float))]
            summary[f"{col}_mean"] = round(sum(vals) / len(vals), 4) if vals else None
            summary[f"{col}_n"] = len(vals)

    yield {
        "event": "done",
        "data": {
            "summary": summary,
            "per_question": per_question_summary,
            "csv_path": str(out_path),
            "summary_csv_path": str(summary_path),
        },
    }


def _write_summary(
    records: List[EvalRecord],
    lex_rows: Dict[str, LexicalScores],
    path: Path,
    *,
    mode: str,
) -> None:
    summary: Dict[str, float] = {
        "questions": len(records),
        "errors": sum(1 for r in records if r.error),
        "runtime_total_s": round(sum(r.runtime_s for r in records), 1),
    }
    if mode in ("lexical", "both") and lex_rows:
        for metric in ("jaccard", "rouge_l", "citation_match", "keyword_f1"):
            vals = [getattr(ls, metric) for ls in lex_rows.values()]
            summary[f"lex_{metric}_mean"] = round(sum(vals) / max(1, len(vals)), 4)
    if mode in ("ragas", "both"):
        for col in ("ragas_faithfulness", "ragas_answer_relevancy",
                    "ragas_context_precision", "ragas_context_recall"):
            vals = [getattr(r, col) for r in records if isinstance(getattr(r, col), (int, float))]
            summary[f"{col}_mean"] = round(sum(vals) / len(vals), 4) if vals else float("nan")
            summary[f"{col}_n"] = len(vals)
    pd.DataFrame([summary]).to_csv(path, index=False)
