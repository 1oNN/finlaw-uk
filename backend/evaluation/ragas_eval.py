"""Real RAGAS evaluation with a local Mistral judge.

Loads `backend/evaluation/questions/questions_80_balanced.csv`, runs each
question through the full FinLaw-UK RAG pipeline (graph boost + sparse +
dense retrieval + Ollama generation), then scores the resulting
(question, answer, contexts, ground_truth) tuples with the `ragas`
library using four metrics:

    - faithfulness         — does the answer follow from the contexts?
    - answer_relevancy     — does the answer address the question?
    - context_precision    — were the retrieved contexts relevant?
    - context_recall       — did the contexts cover the ground truth?

Per-question results plus the four metric averages are written to
`data/eval_results/eval_results_ragas_<timestamp>.csv`.

Judge LLM choice (via `RAGAS_JUDGE` env or the `judge` argument):
    'ollama' (default) — uses the same local Mistral the chat backend uses;
                         requires the Ollama server to be running.
    'hf'              — uses `backend.llm.hf_client.HFMistralClient`,
                         which loads Mistral weights via HF transformers
                         (~14 GB download on first run).

Embeddings (used for some RAGAS metrics): `BAAI/bge-small-en-v1.5` via
`HuggingFaceEmbeddings` — the same encoder Stage 1's dense retriever uses.
"""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from backend.llm.ollama_client import generate_stream
from backend.retrieval.orchestrator import (
    gather_contexts,
    get_graph_boost,
    get_raw_context,
)
from backend.retrieval import sparse


log = logging.getLogger(__name__)

EVAL_OUTPUT_DIR = Path(os.getenv("EVAL_OUTPUT_DIR", "./data/eval_results"))
QUESTIONS_CSV = Path(__file__).resolve().parent / "questions" / "questions_80_balanced.csv"


# A trimmed-down version of the finance Q&A prompt used by the chat backend.
# Keeping the wording aligned with `backend/app.py::FINANCE_QA_PROMPT` so
# RAGAS scores the same answer shape users see in production.
FINANCE_QA_PROMPT = (
    "You are LEGAL GPT, a senior UK finance-law assistant.\n"
    "Answer concisely in 4–6 sentences, using precise legal terminology.\n"
    "Always include: thresholds/amounts or time limits, key conditions/exemptions, "
    "and concrete duties (disclose, maintain lists, refund, investigate, document, notify).\n"
    "Use at least TWO domain keywords from FSMA/COBS/SYSC/CONC/ICOBS/MCOB/PROD/MLR/PSR/RAO/UK MAR/DTR.\n"
    "End with one line starting exactly with 'Source: ' using ONLY UK short-form citations."
)


@dataclass
class EvalRecord:
    """One row of the evaluation set, populated incrementally."""

    qid: str
    domain: str
    complexity: str
    question: str
    ground_truth: str
    expected_citations: str
    answer: str = ""
    contexts: List[str] = field(default_factory=list)
    runtime_s: float = 0.0
    error: str = ""
    # RAGAS scores are filled in after `ragas.evaluate` runs.
    ragas_faithfulness: Optional[float] = None
    ragas_answer_relevancy: Optional[float] = None
    ragas_context_precision: Optional[float] = None
    ragas_context_recall: Optional[float] = None


def load_questions(path: Path = QUESTIONS_CSV, sample: Optional[int] = None) -> List[EvalRecord]:
    """Read the evaluation CSV. If `sample` is given, returns just the first
    N rows — useful for smoke tests."""
    df = pd.read_csv(path)
    if sample is not None:
        df = df.head(sample)
    records: List[EvalRecord] = []
    for _, row in df.iterrows():
        records.append(
            EvalRecord(
                qid=str(row.get("id", "")),
                domain=str(row.get("domain", "")),
                complexity=str(row.get("complexity", "")),
                question=str(row.get("question", "")),
                ground_truth=str(row.get("gold_answer", "")),
                expected_citations=str(row.get("expected_citations", "")),
            )
        )
    return records


def _format_hits_inline(hits: List[Tuple[str, str]]) -> str:
    return "".join(f"**Context ({k}):**\n{snip}\n\n" for k, snip in hits)


def run_rag_pipeline(question: str) -> Tuple[str, List[str], float]:
    """Run the full RAG pipeline once for a single question.

    Returns `(answer, contexts, runtime_s)` where:
        answer   = the joined token stream from Ollama
        contexts = a flat list of retrieval snippets (graph + documents)
        runtime_s = wall-clock seconds for this question
    """
    t0 = time.time()

    gboost = get_graph_boost(question)
    raw = get_raw_context(question)

    ctx_md = gboost.get("context_md", "")
    doc_ctx = _format_hits_inline(raw) if raw else ""
    user_content = (ctx_md + doc_ctx + question).strip()

    messages = [
        {"role": "system", "content": FINANCE_QA_PROMPT},
        {"role": "user", "content": user_content},
    ]

    parts: List[str] = []
    for token in generate_stream(messages, model_id=None):
        parts.append(token)
    answer = "".join(parts).strip()

    contexts = gather_contexts(question)
    if not contexts and raw:
        # Fallback for the rare case where gather_contexts found nothing but
        # the raw retrieval did (e.g., graph disabled).
        contexts = [snip for _, snip in raw if snip]

    return answer, contexts, time.time() - t0


def _build_judge_llm(judge: str):
    """Return a LangChain LLM ready to be wrapped by `LangchainLLMWrapper`.

    `judge` is 'ollama' (default) or 'hf'. The ollama path uses
    `langchain_community.chat_models.ChatOllama` against the same server
    the chat backend uses."""
    if judge == "hf":
        from backend.llm.hf_client import HFMistralClient
        return HFMistralClient.create()

    # Ollama path — preferred (faster, no 14 GB download).
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct")
    try:
        from langchain_community.chat_models import ChatOllama
        return ChatOllama(model=model, base_url=base, temperature=0.0)
    except ImportError as e:
        raise RuntimeError(
            "langchain-community is required for the Ollama judge. "
            "Install with `pip install langchain-community`."
        ) from e


def _build_embeddings():
    """RAGAS needs embeddings for context_precision / context_recall.
    Reuse BGE-small from Stage 1 so we don't download a second encoder."""
    from langchain_community.embeddings import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=os.getenv("DENSE_MODEL", "BAAI/bge-small-en-v1.5"))


def _ragas_evaluate(records: List[EvalRecord], judge: str) -> List[EvalRecord]:
    """Run RAGAS over `records` and attach the four metric scores in place.
    Returns the same list (for chaining)."""
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except ImportError as e:
        raise RuntimeError(
            "ragas + datasets are required for RAGAS evaluation. "
            "Install with `pip install ragas datasets langchain-community`."
        ) from e

    ds = Dataset.from_list([
        {
            "user_input": r.question,
            "response": r.answer,
            "retrieved_contexts": r.contexts if r.contexts else [""],
            "reference": r.ground_truth,
        }
        for r in records
        if r.answer and not r.error
    ])
    if len(ds) == 0:
        log.warning("No valid records to score; skipping RAGAS.")
        return records

    judge_llm = LangchainLLMWrapper(_build_judge_llm(judge))
    embeddings = LangchainEmbeddingsWrapper(_build_embeddings())

    result = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=judge_llm,
        embeddings=embeddings,
    )
    df = result.to_pandas()

    question_col = "user_input" if "user_input" in df.columns else "question"
    by_q: Dict[str, Dict[str, float]] = {}
    for _, row in df.iterrows():
        by_q[row[question_col]] = {
            "faithfulness": row.get("faithfulness"),
            "answer_relevancy": row.get("answer_relevancy"),
            "context_precision": row.get("context_precision"),
            "context_recall": row.get("context_recall"),
        }
    for r in records:
        if r.question in by_q:
            scores = by_q[r.question]
            r.ragas_faithfulness = scores.get("faithfulness")
            r.ragas_answer_relevancy = scores.get("answer_relevancy")
            r.ragas_context_precision = scores.get("context_precision")
            r.ragas_context_recall = scores.get("context_recall")
    return records


def evaluate_questions(
    *,
    sample: Optional[int] = None,
    judge: str = "ollama",
    output_dir: Path = EVAL_OUTPUT_DIR,
    questions_path: Path = QUESTIONS_CSV,
) -> Path:
    """End-to-end Stage 5 entry point.

    1. Load questions (optionally a head sample).
    2. Run the RAG pipeline for each question, capturing answer + contexts.
    3. Score with RAGAS metrics using the chosen judge LLM.
    4. Write per-question CSV + a separate `_summary.csv` with metric averages.

    Returns the path of the per-question CSV."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = load_questions(questions_path, sample=sample)
    log.info("Loaded %d question(s) from %s", len(records), questions_path)

    print(f"Indexing local document corpus … ({sparse.get_index_stats()['num_docs']} docs)")

    for i, r in enumerate(records, start=1):
        try:
            answer, contexts, runtime_s = run_rag_pipeline(r.question)
            r.answer = answer
            r.contexts = contexts
            r.runtime_s = round(runtime_s, 2)
            print(f"  [{i}/{len(records)}] {r.qid} ({runtime_s:.1f}s) {r.question[:60]}")
        except Exception as e:
            r.error = str(e)
            log.exception("RAG pipeline failed for qid=%s: %s", r.qid, e)
            print(f"  [{i}/{len(records)}] {r.qid} ERROR: {e}")

    print(f"Running RAGAS judge ({judge}) over {sum(1 for r in records if r.answer)} answers …")
    try:
        _ragas_evaluate(records, judge=judge)
    except Exception as e:
        log.exception("RAGAS scoring failed: %s", e)
        print(f"RAGAS scoring failed: {e}  (per-question CSV will still be written without scores)")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"eval_results_ragas_{timestamp}.csv"
    summary_path = output_dir / f"eval_results_ragas_{timestamp}_summary.csv"

    rows = [
        {
            **{k: v for k, v in asdict(r).items() if k != "contexts"},
            "contexts": " ||| ".join(r.contexts) if r.contexts else "",
        }
        for r in records
    ]
    pd.DataFrame(rows).to_csv(out_path, index=False)
    _write_summary(records, summary_path)
    print(f"Per-question results: {out_path}")
    print(f"Summary:              {summary_path}")
    return out_path


def _is_real_number(x: object) -> bool:
    """True iff x is a finite int/float (rejects None, bool, NaN, and inf).

    `isinstance(float('nan'), (int, float))` is True, which is why the previous
    summary code was averaging NaN values straight into the mean. We need an
    explicit NaN check; we also reject inf to be safe.
    """
    if x is None or isinstance(x, bool):
        return False
    if isinstance(x, (int, float)):
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return False
        return True
    return False


def _safe_mean(values: Iterable[object]) -> Tuple[Optional[float], int]:
    """Mean of `values`, skipping None / NaN / inf / non-numeric.

    Returns `(mean, n_valid)`; `mean` is `None` when no valid values remain so
    the CSV cell renders empty rather than the literal string "nan".
    """
    real = [float(v) for v in values if _is_real_number(v)]
    if not real:
        return None, 0
    return round(sum(real) / len(real), 4), len(real)


def _write_summary(records: List[EvalRecord], path: Path) -> None:
    metric_cols = (
        "ragas_faithfulness",
        "ragas_answer_relevancy",
        "ragas_context_precision",
        "ragas_context_recall",
    )
    n_total = len(records)
    summary: Dict[str, object] = {}
    for c in metric_cols:
        mean, n_valid = _safe_mean(getattr(r, c) for r in records)
        summary[c + "_mean"]    = mean
        summary[c + "_n_valid"] = n_valid
        summary[c + "_n_total"] = n_total
    summary["runtime_total_s"] = round(sum(r.runtime_s for r in records), 1)
    summary["questions"] = n_total
    summary["errors"] = sum(1 for r in records if r.error)
    pd.DataFrame([summary]).to_csv(path, index=False)
