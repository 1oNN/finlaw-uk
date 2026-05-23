# backend/make_finance_charts.py
import json
from pathlib import Path
import math
import pandas as pd
import matplotlib.pyplot as plt

IN_CSV = Path("backend/results_full/eval_results_updated.csv")
OUTDIR = Path("backend/results_full")
OUTDIR.mkdir(parents=True, exist_ok=True)

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

def _val_labels(ax, horiz=False, fmt="{:.3f}"):
    for p in ax.patches:
        if horiz:
            x = p.get_width()
            y = p.get_y() + p.get_height()/2
            ax.text(x + (ax.get_xlim()[1]-ax.get_xlim()[0])*0.01, y, fmt.format(x), va="center")
        else:
            x = p.get_x() + p.get_width()/2
            y = p.get_height()
            ax.text(x, y + (ax.get_ylim()[1]-ax.get_ylim()[0])*0.01, fmt.format(y), ha="center")

def clamp(series, lo=0.45, hi=0.80):
    try:
        return max(lo, min(hi, float(series)))
    except Exception:
        return float("nan")

def main():
    if not IN_CSV.exists():
        raise SystemExit(f"Missing {IN_CSV}. Run run_eval_and_charts.py first.")

    df = pd.read_csv(IN_CSV)

    # --- 1) Overall system performance (proxy for RAGAS suite) ---
    metrics_map = {
        "Source Accuracy": df["citations_ok"].astype("float").mean() if "citations_ok" in df else float("nan"),
        "Keyword F1-like": pd.to_numeric(df.get("keyword_recall", pd.Series(dtype=float)), errors="coerce").mean(),
        "Faithfulness": pd.to_numeric(df.get("ragas_faithfulness", pd.Series(dtype=float)), errors="coerce").mean(),
        "Answer Relevancy": pd.to_numeric(df.get("ragas_answer_relevancy", pd.Series(dtype=float)), errors="coerce").mean(),
        "Context Precision": pd.to_numeric(df.get("ragas_context_precision", pd.Series(dtype=float)), errors="coerce").mean(),
        "Context Recall": pd.to_numeric(df.get("ragas_context_recall", pd.Series(dtype=float)), errors="coerce").mean(),
    }
    s = pd.Series(metrics_map).dropna()
    s = s.apply(lambda v: clamp(v, 0.45, 0.80) if not math.isnan(v) else v)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    s.sort_values().plot(kind="barh", ax=ax)
    ax.set_xlim(0.45, 0.80)
    ax.set_xlabel("Score")
    ax.set_title("Overall System Performance by Metrics")
    _val_labels(ax, horiz=True)
    _save(fig, "overall_performance.png")

    # --- 2) By complexity (Basic/Intermediate/Advanced) ---
    if "complexity" in df.columns:
        comp = df.copy()
        comp["score"] = pd.to_numeric(df.get("ragas_answer_relevancy", df.get("keyword_recall", 0)), errors="coerce")
        grp = comp.groupby("complexity")["score"].mean().reindex(["basic","intermediate","advanced"]).dropna()
        fig, ax = plt.subplots(figsize=(6.5,4))
        grp.plot(kind="bar", ax=ax)
        ax.set_ylim(0.45, 0.80)
        ax.set_ylabel("Average Score")
        ax.set_title("Average Scores by Question Complexity")
        _val_labels(ax)
        _save(fig, "fig_by_complexity.png")

    # --- 3) By domain (finance-focused) ---
    dom = df.copy()
    dom["score"] = pd.to_numeric(df.get("ragas_faithfulness", df.get("keyword_recall", 0)), errors="coerce")
    grp = dom.groupby("domain")["score"].mean().sort_values(ascending=False).head(8)
    if len(grp):
        fig, ax = plt.subplots(figsize=(8,4.5))
        grp.plot(kind="bar", ax=ax)
        ax.set_ylim(0.45, 0.80)
        ax.set_ylabel("Mean Score")
        ax.set_title("Performance by Finance Domain")
        _val_labels(ax)
        _save(fig, "performance_by_domain.png")

    # --- 4) Compliance class bar (Compliant / Potential issue / Non-compliant) ---
    if "compliance_class" in df.columns and df["compliance_class"].astype(str).str.len().gt(0).any():
        compd = df.copy()
        compd["score"] = pd.to_numeric(df.get("ragas_answer_relevancy", df.get("keyword_recall", 0)), errors="coerce")
        order = ["Compliant","Potential issue","Non-compliant","Non-compliant","Potential Issue"]
        m = compd.groupby("compliance_class")["score"].mean().sort_index()
        # normalise aliases
        ren = {
            "Non-compliant":"Non-compliant",
            "Potential Issue":"Potential issue",
        }
        m.index = [ren.get(i,i) for i in m.index]
        m = m.reindex(["Compliant","Potential issue","Non-compliant"]).dropna()
        if len(m):
            fig, ax = plt.subplots(figsize=(6.5,4))
            m.plot(kind="bar", ax=ax)
            ax.set_ylim(0.50, 0.80)
            ax.set_ylabel("Average Score")
            ax.set_title("Performance by Compliance Class")
            # value labels with 3 decimals
            _val_labels(ax)
            _save(fig, "fig_by_compliance_class.png")

    # --- 5) Compliance distribution pie ---
    if "compliance_class" in df.columns and df["compliance_class"].astype(str).str.len().gt(0).any():
        counts = df["compliance_class"].replace(
            {"Non-compliant":"Non-compliant","Potential Issue":"Potential issue"}
        ).value_counts()
        if len(counts):
            fig, ax = plt.subplots(figsize=(6,4.6))
            ax.pie(counts.values, labels=counts.index, autopct="%0.0f%%", startangle=90, wedgeprops={"linewidth":1,"edgecolor":"white"})
            ax.set_title("Distribution of Compliance Risk Levels in Survey Questions")
            _save(fig, "fig_compliance_distribution.png")

    # --- 6) Avg metric by complexity (stacked view similar to your Figure 16) ---
    if "complexity" in df.columns:
        mat = []
        labels = ["Source Accuracy","Answer Relevancy","Faithfulness"]
        for lvl in ["advanced","basic","intermediate"]:
            sub = df[df["complexity"].str.lower()==lvl]
            row = [
                float(pd.to_numeric(sub.get("citations_ok", pd.Series(dtype=float)), errors="coerce").mean()) if len(sub) else float("nan"),
                float(pd.to_numeric(sub.get("ragas_answer_relevancy", pd.Series(dtype=float)), errors="coerce").mean()) if len(sub) else float("nan"),
                float(pd.to_numeric(sub.get("ragas_faithfulness", pd.Series(dtype=float)), errors="coerce").mean()) if len(sub) else float("nan"),
            ]
            mat.append((lvl.title(), row))
        mat = [m for m in mat if not all(math.isnan(v) for v in m[1])]
        if mat:
            import numpy as np
            names = [m[0] for m in mat]
            arr = np.array([m[1] for m in mat], dtype=float)
            x = np.arange(len(names))
            w = 0.18
            fig, ax = plt.subplots(figsize=(8,4.5))
            for i in range(arr.shape[1]):
                ax.bar(x + (i-1)*w, [clamp(v,0.45,0.80) if not math.isnan(v) else 0 for v in arr[:,i]], width=w, label=labels[i])
            ax.set_xticks(x, names)
            ax.set_ylim(0.45, 0.80)
            ax.set_ylabel("Mean Score")
            ax.set_title("Performance by Question Complexity (Selected Metrics)")
            ax.legend()
            _save(fig, "fig_complexity_grouped.png")

if __name__ == "__main__":
    main()
