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
    gather_contexts_wide,  # Task 3: pre-rerank pool for RAGAS scoring
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
    "You are LEGAL GPT, a UK financial regulation assistant.\n\n"
    "Rules:\n"
    "1. Answer ONLY using the context passages provided in this message.\n"
    "2. If the context does not contain the answer, reply EXACTLY:\n"
    "   \"The provided sources do not contain enough information to answer this confidently.\"\n"
    "3. Cite every factual claim inline using the chunk's UK short-form citation, "
    "e.g. [DISP 1.6.2R], [COBS 4.2.1R], [FSMA 2000 s.19]. Do NOT invent citations.\n"
    "4. Answer the specific question. No background, no related-material digressions.\n"
    "5. Do NOT use prior knowledge outside the provided context. No URLs.\n"
    "6. After the answer, on a NEW line, write 'Source: ' followed by the same "
    "citations separated by ' | ' (UK short-form only).\n\n"
    "Examples:\n"
    "Q: What is the deadline for handling a DISP complaint?\n"
    "A: A firm must send a final response within 8 weeks of receiving the complaint [DISP 1.6.2R].\n"
    "Source: DISP 1.6.2R\n\n"
    "Q: What is the capital requirement for a banana stand?\n"
    "A: The provided sources do not contain enough information to answer this confidently.\n"
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
    # Deterministic sampling so eval runs are reproducible; matches the legal
    # path in backend/app.py.
    for token in generate_stream(
        messages, model_id=None, options={"temperature": 0.0, "top_p": 0.9}
    ):
        parts.append(token)
    answer = "".join(parts).strip()

    # Task 3: score RAGAS against the pre-rerank pool (20) for fair recall.
    # The LLM still saw the post-rerank top-k via `raw` above; only the
    # `contexts` field RAGAS scores against is widened here.
    contexts = gather_contexts_wide(
        question, pool_size=int(os.getenv("EVAL_CONTEXT_POOL", "20"))
    )
    if not contexts and raw:
        # Fallback for the rare case where the wide pool found nothing but
        # the raw retrieval did (e.g., graph disabled and dense unavailable).
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
    # Judge LLM defaults to mistral:7b-instruct: it's the same model the chat
    # backend uses (already loaded into VRAM), and it produces well-formed
    # RAGAS judgment JSON reliably. Smaller models that look attractive on
    # paper either (a) emit reasoning traces that blow the timeout
    # (qwen3:4b), or (b) struggle to produce valid JSON (gemma3:1b).
    # The previous run's 72 timeouts came from RAGAS calling the judge
    # in one big batch with the default 60s per-call ceiling; the new
    # RunConfig pushes that to 180s and the per-record loop limits the
    # blast radius of any single failure.
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.getenv("RAGAS_JUDGE_MODEL", "mistral:7b-instruct")
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


def _ragas_imports():
    """Lazy import of the RAGAS stack so a missing optional dep raises only
    when the evaluation actually runs."""
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
        from ragas.run_config import RunConfig
    except ImportError as e:
        raise RuntimeError(
            "ragas + datasets are required for RAGAS evaluation. "
            "Install with `pip install ragas datasets langchain-community`."
        ) from e
    return {
        "Dataset": Dataset, "evaluate": evaluate,
        "LangchainLLMWrapper": LangchainLLMWrapper,
        "LangchainEmbeddingsWrapper": LangchainEmbeddingsWrapper,
        "metrics": [faithfulness, answer_relevancy, context_precision, context_recall],
        "RunConfig": RunConfig,
    }


def _ragas_run_config(ragas_mods):
    """Construct the shared RunConfig for the judge.

    Settings calibrated from the 20260523 incident (72 timeouts on a single
    full-batch call with the default 60s timeout):
      max_workers=4   parallelism within one record (4 metrics)
      timeout=180     per-call ceiling; way above mistral cold-start
      max_retries=3   covers transient network blips
      max_wait=30     exponential backoff cap
    """
    return ragas_mods["RunConfig"](
        max_workers=int(os.getenv("RAGAS_MAX_WORKERS", "4")),
        timeout=int(os.getenv("RAGAS_TIMEOUT", "180")),
        max_retries=int(os.getenv("RAGAS_MAX_RETRIES", "3")),
        max_wait=int(os.getenv("RAGAS_MAX_WAIT", "30")),
    )


def _coerce_score(v: object) -> Optional[float]:
    try:
        f = float(v)  # type: ignore[arg-type]
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _evaluate_one_record(record: EvalRecord, judge_llm, embeddings, ragas_mods, run_config) -> None:
    """Score a single record in place. Failures leave RAGAS scores as None
    rather than poisoning the rest of the batch."""
    if not record.answer or record.error:
        return
    try:
        ds = ragas_mods["Dataset"].from_list([{
            "user_input": record.question,
            "response": record.answer,
            "retrieved_contexts": record.contexts if record.contexts else [""],
            "reference": record.ground_truth,
        }])
        result = ragas_mods["evaluate"](
            ds,
            metrics=ragas_mods["metrics"],
            llm=judge_llm,
            embeddings=embeddings,
            run_config=run_config,
            raise_exceptions=False,
        )
        df = result.to_pandas()
        if len(df) == 0:
            return
        row = df.iloc[0]
        record.ragas_faithfulness      = _coerce_score(row.get("faithfulness"))
        record.ragas_answer_relevancy  = _coerce_score(row.get("answer_relevancy"))
        record.ragas_context_precision = _coerce_score(row.get("context_precision"))
        record.ragas_context_recall    = _coerce_score(row.get("context_recall"))
    except Exception as e:
        log.warning("RAGAS scoring failed for qid=%s: %s", record.qid, e)


def _ragas_evaluate(records: List[EvalRecord], judge: str) -> List[EvalRecord]:
    """Run RAGAS over `records` and attach the four metric scores in place.

    Per-record loop (instead of one big batch) so a single judge timeout
    no longer wipes out the entire eval — each record is scored independently
    with `raise_exceptions=False`, and partial NaN scores are coerced to None.

    Returns the same list (for chaining)."""
    valid = [r for r in records if r.answer and not r.error]
    if not valid:
        log.warning("No valid records to score; skipping RAGAS.")
        return records

    ragas_mods = _ragas_imports()
    judge_llm = ragas_mods["LangchainLLMWrapper"](_build_judge_llm(judge))
    embeddings = ragas_mods["LangchainEmbeddingsWrapper"](_build_embeddings())
    run_config = _ragas_run_config(ragas_mods)

    for r in valid:
        _evaluate_one_record(r, judge_llm, embeddings, ragas_mods, run_config)

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

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"eval_results_ragas_{timestamp}.csv"
    summary_path = output_dir / f"eval_results_ragas_{timestamp}_summary.csv"

    # Build the judge once so its model is loaded into memory before the loop.
    # If RAGAS deps are missing we surface that NOW rather than after 80 RAG
    # passes have already burned 20+ minutes.
    ragas_mods = _ragas_imports()
    judge_llm = ragas_mods["LangchainLLMWrapper"](_build_judge_llm(judge))
    embeddings = ragas_mods["LangchainEmbeddingsWrapper"](_build_embeddings())
    run_config = _ragas_run_config(ragas_mods)
    print(f"Running per-question RAG + RAGAS judge ({judge}, "
          f"model={os.getenv('RAGAS_JUDGE_MODEL', 'mistral:7b-instruct')}) …")

    header_written = False
    for i, r in enumerate(records, start=1):
        try:
            answer, contexts, runtime_s = run_rag_pipeline(r.question)
            r.answer = answer
            r.contexts = contexts
            r.runtime_s = round(runtime_s, 2)
        except Exception as e:
            r.error = str(e)
            log.exception("RAG pipeline failed for qid=%s: %s", r.qid, e)

        # Score this single record; failures leave RAGAS fields as None
        # rather than dropping the entire batch.
        _evaluate_one_record(r, judge_llm, embeddings, ragas_mods, run_config)

        # Append this record to CSV immediately so a crash on Q47 preserves
        # questions 1..46 instead of losing the whole run.
        row = {
            **{k: v for k, v in asdict(r).items() if k != "contexts"},
            "contexts": " ||| ".join(r.contexts) if r.contexts else "",
        }
        pd.DataFrame([row]).to_csv(
            out_path, mode="a", header=not header_written, index=False,
        )
        header_written = True

        recall = r.ragas_context_recall
        recall_str = f"{recall:.2f}" if recall is not None else "N/A "
        print(
            f"  [{i}/{len(records)}] {r.qid} "
            f"({r.runtime_s:.1f}s) recall={recall_str}  "
            f"{r.question[:55]}"
        )

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
