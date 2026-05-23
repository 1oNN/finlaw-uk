# backend/plot_thesis_figures.py
"""
Thesis figures (matplotlib only) from backend/results_full/eval_results_updated.csv

Outputs -> backend/results_full/:
  fig_by_compliance_class.png
  fig_by_complexity.png
  summary_by_compliance.csv
  summary_by_complexity.csv
"""

from pathlib import Path
import math
import pandas as pd
import matplotlib.pyplot as plt

IN_CSV = Path("backend/results_full/eval_results_updated.csv")
OUTDIR = Path("backend/results_full")
OUTDIR.mkdir(parents=True, exist_ok=True)

# ---- plotting helpers ----
plt.rcParams.update({
    "figure.dpi": 140,
    "font.size": 12,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
})

def _save(fig, name):
    p = OUTDIR / name
    fig.tight_layout()
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    print(f"✔ saved {p}")

def _val_labels(ax, fmt="{:.3f}"):
    for p in ax.patches:
        x = p.get_x() + p.get_width() / 2
        y = p.get_height()
        ax.text(x, y + (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.01, fmt.format(y), ha="center")

def _pick_score_cols(df: pd.DataFrame):
    """
    Prefer RAGAS 'answer_relevancy'; otherwise fall back to 'ragas_faithfulness',
    then 'keyword_recall'. Returns a numeric Series.
    """
    candidates = ["ragas_answer_relevancy", "ragas_faithfulness", "keyword_recall"]
    for c in candidates:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            if s.notna().any():
                return s
    return pd.Series([float("nan")] * len(df))

def _norm_compliance_labels(s: pd.Series) -> pd.Series:
    return (
        s.astype(str).str.strip().replace({
            "potential issue": "Potential issue",
            "potential_issue": "Potential issue",
            "noncompliant": "Non-compliant",
            "non_compliant": "Non-compliant",
            "Compliant": "Compliant",
            "compliant": "Compliant",
        })
    )

def main():
    if not IN_CSV.exists():
        raise SystemExit(f"Missing {IN_CSV}. Run your evaluation first.")

    df = pd.read_csv(IN_CSV)

    # ---------------- Figure 1: Performance by Compliance Class ----------------
    if "compliance_class" in df.columns:
        df_cc = df.copy()
        df_cc["compliance_class"] = _norm_compliance_labels(df_cc["compliance_class"])
        score = _pick_score_cols(df_cc)
        df_cc = df_cc.assign(score=score)

        # group + mean + order for thesis look
        order = ["Compliant", "Potential issue", "Non-compliant"]
        g = df_cc.groupby("compliance_class", dropna=False)["score"].mean()
        g = g.reindex(order).dropna()
        n = int(df_cc["compliance_class"].notna().sum())

        # save summary CSV
        g.round(3).to_frame("average_score").to_csv(OUTDIR / "summary_by_compliance.csv")

        # plot
        if len(g):
            fig, ax = plt.subplots(figsize=(7, 4.6))
            g.plot(kind="bar", ax=ax)
            ax.set_ylim(0.50, 0.80)  # matches the visual bounds you showed
            ax.set_ylabel("Average RAGAS Score")
            ax.set_title(f"Performance by Compliance Class (n={n})")
            _val_labels(ax, fmt="{:.3f}")
            _save(fig, "fig_by_compliance_class.png")

    # ---------------- Figure 2: Average RAGAS Scores by Complexity -------------
    if "complexity" in df.columns:
        df_cx = df.copy()
        df_cx["complexity"] = (
            df_cx["complexity"].astype(str).str.strip().str.lower()
            .replace({"adv": "advanced", "hard": "advanced", "mid": "intermediate", "easy": "basic"})
        )
        score = _pick_score_cols(df_cx)
        df_cx = df_cx.assign(score=score)

        order = ["basic", "intermediate", "advanced"]
        g2 = df_cx.groupby("complexity", dropna=False)["score"].mean()
        g2 = g2.reindex(order).dropna()

        # save summary CSV
        g2.round(3).to_frame("average_score").to_csv(OUTDIR / "summary_by_complexity.csv")

        if len(g2):
            fig, ax = plt.subplots(figsize=(7.4, 4.6))
            g2.plot(kind="bar", ax=ax)
            ax.set_ylim(0.50, 0.80)
            ax.set_ylabel("Average RAGAS Score")
            ax.set_title("Average RAGAS Scores by Question Complexity")
            ax.set_xticklabels([s.title() for s in g2.index])
            _val_labels(ax, fmt="{:.3f}")
            _save(fig, "fig_by_complexity.png")

if __name__ == "__main__":
    main()
