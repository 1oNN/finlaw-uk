#!/usr/bin/env python3
"""CLI for the FinLaw-UK evaluation runner.

Examples:
    python scripts/run_evaluation.py --sample 5 --mode ragas
    python scripts/run_evaluation.py --sample 5 --mode both
    python scripts/run_evaluation.py --mode lexical          # full 80 questions, lexical only
    python scripts/run_evaluation.py --judge hf              # use HF Mistral instead of Ollama
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["lexical", "ragas", "both"], default="ragas")
    parser.add_argument("--sample", type=int, default=None, help="Run first N questions only.")
    parser.add_argument(
        "--judge",
        choices=["ollama", "hf"],
        default="ollama",
        help="RAGAS judge LLM (only used in 'ragas' / 'both' modes).",
    )
    parser.add_argument("--output-dir", default="./data/eval_results")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from backend.evaluation.runner import run
    run(
        mode=args.mode,
        sample=args.sample,
        judge=args.judge,
        output_dir=Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
