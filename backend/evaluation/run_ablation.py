"""Retrieval ablation harness — runs one eval step and appends to ablation.csv.

Used to attribute the per-step contribution of each Task 4 sub-step
(hybrid fusion variants, embedder swap, reranker, parent-doc, KG expansion)
to the n=10 curated test set.

Each step sets environment variables that the retrieval orchestrator reads
per-call (so no restart needed between steps), runs the full eval against
``backend/evaluation/questions/questions_10_curated.csv``, and appends one
row to ``data/eval_results/ablation.csv``:

    step,context_recall,faithfulness,answer_relevancy,context_precision,
    n_valid_recall,seconds_per_q,timestamp

Usage:
    python -m backend.evaluation.run_ablation 4a-rrf-baseline
    python -m backend.evaluation.run_ablation 4a-dense-only --set RAG_FUSION_MODE=dense
    python -m backend.evaluation.run_ablation 4a-bm25-only  --set RAG_FUSION_MODE=bm25
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import pandas as pd

QUESTIONS_CSV = Path("backend/evaluation/questions/questions_10_curated.csv")
ABLATION_CSV  = Path("data/eval_results/ablation.csv")


def _safe_mean(series: pd.Series) -> Tuple[float | None, int]:
    """Strip None and NaN, then mean. Returns (mean_or_None, n_valid)."""
    real = [
        float(v) for v in series.tolist()
        if v is not None
        and isinstance(v, (int, float))
        and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))
    ]
    if not real:
        return None, 0
    return round(sum(real) / len(real), 4), len(real)


def run_step(step_name: str, env_overrides: List[Tuple[str, str]]) -> None:
    # Apply env overrides BEFORE importing the eval module so any module-level
    # reads of env vars (ENABLE_DENSE, DENSE_MODEL, etc) pick them up. Vars
    # the orchestrator reads per-call (RAG_FUSION_MODE) work either way.
    for k, v in env_overrides:
        os.environ[k] = v
        print(f"  env {k}={v}")

    from backend.evaluation.ragas_eval import evaluate_questions

    out_dir = Path("data/eval_results")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Running ablation step: {step_name}")
    per_q_csv = evaluate_questions(
        sample=None,
        judge="ollama",
        output_dir=out_dir,
        questions_path=QUESTIONS_CSV,
    )

    df = pd.read_csv(per_q_csv)
    rec_mean, rec_n = _safe_mean(df["ragas_context_recall"])
    faith_mean, _   = _safe_mean(df["ragas_faithfulness"])
    rel_mean, _     = _safe_mean(df["ragas_answer_relevancy"])
    prec_mean, _    = _safe_mean(df["ragas_context_precision"])
    rt_mean, _      = _safe_mean(df["runtime_s"])

    row = {
        "step": step_name,
        "context_recall": rec_mean,
        "faithfulness": faith_mean,
        "answer_relevancy": rel_mean,
        "context_precision": prec_mean,
        "n_valid_recall": rec_n,
        "n_questions": len(df),
        "seconds_per_q": rt_mean,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "per_question_csv": per_q_csv.name,
    }

    write_header = not ABLATION_CSV.exists()
    pd.DataFrame([row]).to_csv(ABLATION_CSV, mode="a", header=write_header, index=False)

    print()
    print(f"Ablation row written to {ABLATION_CSV}")
    print(f"  step={step_name}")
    print(f"  context_recall    = {rec_mean}  (n={rec_n}/{len(df)})")
    print(f"  faithfulness      = {faith_mean}")
    print(f"  answer_relevancy  = {rel_mean}")
    print(f"  context_precision = {prec_mean}")
    print(f"  seconds_per_q     = {rt_mean}")
    print()
    print("Current ablation table:")
    print(pd.read_csv(ABLATION_CSV).to_string(index=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("step", help="Label for this ablation row (e.g. '4a-rrf-baseline').")
    p.add_argument(
        "--set", action="append", default=[],
        metavar="KEY=VALUE",
        help="Env var override; may be repeated.",
    )
    args = p.parse_args()
    overrides: List[Tuple[str, str]] = []
    for kv in args.set:
        if "=" not in kv:
            print(f"Bad --set spec {kv!r} (expected KEY=VALUE)", file=sys.stderr)
            sys.exit(2)
        k, v = kv.split("=", 1)
        overrides.append((k, v))
    run_step(args.step, overrides)
