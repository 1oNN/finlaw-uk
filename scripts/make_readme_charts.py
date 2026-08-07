"""Regenerate the figures embedded in README.md.

Every chart in the README is produced here from committed data, so a reader
can rerun this script and reproduce the figures exactly:

    python scripts/make_readme_charts.py

Output lands in docs/assets/ as paired SVGs -- <name>_light.svg and
<name>_dark.svg -- which the README swaps via <picture> and
prefers-color-scheme.

Sources
-------
data/eval_results/ablation.csv
    Four-arm retrieval ablation, n=10 per arm.
backend/results_full/run_20250902_002303/eval_results.csv
    The 110-item benchmark. NOTE: the source_accuracy and citation_quality
    columns in that file are NOT correctness measures -- score_citations() in
    scripts/run_eval_and_charts.py awards a flat 0.85 for any citation-shaped
    string, so 103 of 110 rows carry that constant. This script deliberately
    plots only metrics scored against gold answers.
docs/EVALUATION_COMPARISON.md
    Figures for the measurability and refusal charts, transcribed below.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
ABLATION_CSV = ROOT / "data" / "eval_results" / "ablation.csv"
BENCH_CSV = ROOT / "backend" / "results_full" / "run_20250902_002303" / "eval_results.csv"

# --- theme -----------------------------------------------------------------
# Both modes validated with the dataviz palette validator against their own
# surface: light PASSES all six checks, dark PASSES all six. Do not hand-edit
# these without re-running the validator -- the dark steps in particular sit
# inside a narrow OKLCH lightness band (0.48-0.67) chosen for the dark surface.

THEMES = {
    "light": dict(
        surface="#F7F8FA",
        ink="#0F1419",
        ink_soft="#475467",
        ink_mute="#626D7D",
        grid="#E3E8EE",
        axis="#D5DCE4",
        series="#0A5A8C",
        series_mute="#BFD3E2",
        accent2="#B07A1F",
        ramp=["#EDF3F8", "#CFE1EE", "#A6C7DE", "#74A7CA", "#3F84B2", "#166699", "#0A5A8C"],
    ),
    "dark": dict(
        surface="#1D2635",
        ink="#E8EEF5",
        ink_soft="#9CA5B4",
        ink_mute="#7A8595",
        grid="#2A3340",
        axis="#3A4556",
        series="#2B8ED6",
        series_mute="#2C4356",
        accent2="#B5872F",
        ramp=["#1F2C3C", "#213A50", "#234A67", "#215B80", "#1E6E9C", "#2380BB", "#2B8ED6"],
    ),
}

FONT = ["DejaVu Sans", "Segoe UI", "sans-serif"]


def _base_rc(t: dict) -> dict:
    return {
        "font.family": "sans-serif",
        "font.sans-serif": FONT,
        "figure.facecolor": t["surface"],
        "axes.facecolor": t["surface"],
        "savefig.facecolor": t["surface"],
        "text.color": t["ink"],
        "axes.labelcolor": t["ink_soft"],
        "xtick.color": t["ink_mute"],
        "ytick.color": t["ink_mute"],
        "axes.edgecolor": t["axis"],
        "grid.color": t["grid"],
        "font.size": 9,
        "svg.fonttype": "none",  # keep text as text, not paths
    }


def _rounded_hbar(ax, y, width, height, color, radius_frac=0.45, zorder=2):
    """Horizontal bar anchored at x=0.

    Corners are square. Rounded data-ends were tried via FancyBboxPatch but its
    rounding_size is expressed in data coordinates, and these panels span ~1.0
    on x against ~4 on y -- the radius blows out horizontally and the bars
    render as ellipses. A display-space alternative (a thick line with a round
    solid_capstyle) extends each bar by half its own thickness, which
    misrepresents short bars such as answer_relevancy = 0.10. Square corners
    are the honest option here.
    """
    if width <= 0:
        return
    ax.barh(y, width, height=height, color=color, linewidth=0, zorder=zorder)


def _strip_axes(ax, t: dict, keep_left=True):
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_visible(keep_left)
    if keep_left:
        ax.spines["left"].set_color(t["axis"])
        ax.spines["left"].set_linewidth(1.0)
    ax.tick_params(length=0)


def _save(fig, name: str, mode: str):
    ASSETS.mkdir(parents=True, exist_ok=True)
    out = ASSETS / f"{name}_{mode}.svg"
    fig.savefig(out, format="svg", bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    print(f"  wrote {out.relative_to(ROOT)}")


# --- chart 1: retrieval ablation -------------------------------------------

ARM_LABELS = {
    "4a-bm25-only": "BM25 only",
    "4a-dense-only": "Dense only",
    "4a-rrf-baseline": "RRF fusion",
    "4b-rrf-rerank": "RRF + re-ranker",
}
ARM_ORDER = ["4a-bm25-only", "4a-dense-only", "4a-rrf-baseline", "4b-rrf-rerank"]
SHIPPED = "4b-rrf-rerank"

PANELS = [
    ("faithfulness", "Faithfulness", "{:.2f}"),
    ("context_precision", "Context precision", "{:.2f}"),
    ("context_recall", "Context recall", "{:.2f}"),
    ("answer_relevancy", "Answer relevancy", "{:.2f}"),
    ("seconds_per_q", "Seconds / question", "{:.1f}s"),
]


def chart_ablation(mode: str):
    t = THEMES[mode]
    df = pd.read_csv(ABLATION_CSV).set_index("step").loc[ARM_ORDER]

    with plt.rc_context(_base_rc(t)):
        fig, axes = plt.subplots(
            1, len(PANELS), figsize=(11.4, 2.5), sharey=True,
            gridspec_kw=dict(wspace=0.30),
        )
        ypos = np.arange(len(ARM_ORDER))[::-1]

        for ax, (col, title, fmt) in zip(axes, PANELS):
            vals = df[col].to_numpy(dtype=float)
            hi = float(np.nanmax(vals)) * 1.34
            for y, arm, v in zip(ypos, ARM_ORDER, vals):
                shipped = arm == SHIPPED
                _rounded_hbar(
                    ax, y, v, 0.52,
                    t["series"] if shipped else t["series_mute"],
                )
                ax.text(
                    v + hi * 0.035, y, fmt.format(v),
                    va="center", ha="left", fontsize=8.2,
                    color=t["ink"] if shipped else t["ink_mute"],
                    fontweight="600" if shipped else "normal",
                )
            ax.set_xlim(0, hi)
            ax.set_ylim(-0.72, len(ARM_ORDER) - 0.28)
            ax.set_xticks([])
            ax.set_title(title, fontsize=8.6, color=t["ink_soft"], pad=9, loc="left")
            _strip_axes(ax, t)

        axes[0].set_yticks(ypos)
        axes[0].set_yticklabels(
            [ARM_LABELS[a] for a in ARM_ORDER], fontsize=8.8,
        )
        for lbl, arm in zip(axes[0].get_yticklabels(), ARM_ORDER):
            if arm == SHIPPED:
                lbl.set_color(t["ink"])
                lbl.set_fontweight("600")
            else:
                lbl.set_color(t["ink_mute"])

        fig.text(
            0.0, 1.10,
            "Retrieval ablation — one component varied at a time",
            fontsize=11.5, fontweight="600", color=t["ink"], ha="left",
        )
        fig.text(
            0.0, 1.015,
            "RAGAS metrics on the 10-question curated set. Shipped configuration in navy. Higher is better except seconds/question.",
            fontsize=8.4, color=t["ink_mute"], ha="left",
        )
        _save(fig, "ablation", mode)


# --- chart 2: regulatory coverage ------------------------------------------

COMPLEXITY_ORDER = ["basic", "intermediate", "advanced"]


def chart_coverage(mode: str):
    """Dot plot, not a heatmap.

    Every domain-by-complexity cell falls between 0.63 and 0.73, so a heatmap
    renders ten rows of near-identical blue and encodes no signal. Plotted on a
    true 0-1 axis, the flatness is the finding: no regulatory domain is
    materially weaker than any other.
    """
    t = THEMES[mode]
    df = pd.read_csv(BENCH_CSV)
    df = df[df["domain"].notna() & df["complexity"].notna()]

    by_dom = df.groupby("domain")["legal_completeness"]
    stats = pd.DataFrame({
        "mean": by_dom.mean(),
        "n": by_dom.size(),
    })
    per_cell = df.pivot_table(index="domain", columns="complexity",
                              values="legal_completeness", aggfunc="mean")
    stats["lo"] = per_cell.min(axis=1)
    stats["hi"] = per_cell.max(axis=1)
    stats = stats.sort_values("mean", ascending=True)
    overall = df["legal_completeness"].mean()

    with plt.rc_context(_base_rc(t)):
        fig, ax = plt.subplots(figsize=(7.4, 3.9))
        ypos = np.arange(len(stats))

        ax.axvline(overall, color=t["accent2"], linewidth=1.6,
                   linestyle=(0, (4, 3)), zorder=1)
        ax.text(overall + 0.008, len(stats) - 0.35,
                f"overall {overall:.2f}", fontsize=8, color=t["accent2"],
                va="top", ha="left")

        for y, (_, r) in zip(ypos, stats.iterrows()):
            ax.plot([r["lo"], r["hi"]], [y, y], color=t["series_mute"],
                    linewidth=4.5, solid_capstyle="round", zorder=2)
            ax.scatter([r["mean"]], [y], s=62, color=t["series"], zorder=3,
                       edgecolors=t["surface"], linewidths=1.6)
            ax.text(1.005, y, f"n={int(r['n'])}", va="center", ha="left",
                    fontsize=7.8, color=t["ink_mute"])

        ax.set_yticks(ypos)
        ax.set_yticklabels(stats.index, fontsize=8.8, color=t["ink"])
        ax.set_xlim(0, 1.0)
        ax.set_ylim(-0.7, len(stats) - 0.3)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_xticklabels(["0", "0.25", "0.50", "0.75", "1.00"], fontsize=8,
                           color=t["ink_mute"])
        ax.xaxis.grid(True, color=t["grid"], linewidth=1)
        ax.set_axisbelow(True)
        _strip_axes(ax, t)
        ax.set_xlabel(
            "Legal completeness — expected-keyword coverage against gold answers",
            fontsize=8.4, color=t["ink_soft"], labelpad=8,
        )

        fig.text(0.0, 1.075,
                 "Consistent across 10 regulatory domains",
                 fontsize=11.5, fontweight="600", color=t["ink"], ha="left")
        fig.text(
            0.0, 1.005,
            "Dot is the domain mean over 110 benchmark items; bar spans its basic, intermediate and advanced tiers.",
            fontsize=8.4, color=t["ink_mute"], ha="left",
        )
        _save(fig, "coverage", mode)


# --- chart 3: measurability lift -------------------------------------------
# Transcribed from docs/EVALUATION_COMPARISON.md.
MEASURABILITY = [
    ("Balanced set (n=80)", 8, 80, 77),
    ("Curated set (n=10)", 1, 10, 9),
]


def chart_measurability(mode: str):
    t = THEMES[mode]
    with plt.rc_context(_base_rc(t)):
        fig, ax = plt.subplots(figsize=(6.6, 2.9))

        for i, (label, before, total, after) in enumerate(MEASURABILITY):
            y = len(MEASURABILITY) - 1 - i
            b_pct, a_pct = before / total * 100, after / total * 100
            ax.plot([b_pct, a_pct], [y, y], color=t["axis"], linewidth=2, zorder=1,
                    solid_capstyle="round")
            ax.scatter([b_pct], [y], s=110, color=t["surface"], zorder=2,
                       edgecolors=t["ink_mute"], linewidths=1.6)
            ax.scatter([a_pct], [y], s=140, color=t["series"], zorder=3,
                       edgecolors=t["surface"], linewidths=2)
            ax.text(b_pct, y + 0.30, f"{before}/{total}", ha="center", va="bottom",
                    fontsize=8.4, color=t["ink_mute"])
            ax.text(a_pct, y + 0.30, f"{after}/{total}", ha="center", va="bottom",
                    fontsize=9, color=t["ink"], fontweight="600")
            ax.text(-6, y, label, ha="right", va="center", fontsize=8.8,
                    color=t["ink"])

        ax.set_xlim(-6, 108)
        ax.set_ylim(-0.6, len(MEASURABILITY) - 0.25)
        ax.set_yticks([])
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=8,
                           color=t["ink_mute"])
        ax.xaxis.grid(True, color=t["grid"], linewidth=1)
        ax.set_axisbelow(True)
        _strip_axes(ax, t, keep_left=False)
        ax.set_xlabel("Rows where context precision could be computed", fontsize=8.4,
                      color=t["ink_soft"], labelpad=8)

        fig.text(0.0, 1.10, "Metric coverage, not metric score",
                 fontsize=11.5, fontweight="600", color=t["ink"], ha="left")
        fig.text(
            0.0, 1.012,
            "Per-record scoring loop + 180s timeout. The mean barely moved (0.906 → 0.897); what changed is how many rows scored at all.",
            fontsize=8.4, color=t["ink_mute"], ha="left",
        )
        _save(fig, "measurability", mode)


# --- chart 4: refusal-gate trade-off ---------------------------------------
# Transcribed from docs/EVALUATION_COMPARISON.md.
REFUSAL = [
    ("All 80 rows", 80, 0.4078, False),
    ("Template stubs (Q11–Q80)", 70, 0.3506, False),
    ("Real curated (Q1–Q10)", 10, 0.8023, True),
    ("Excluding refusals", 49, 0.6575, True),
]
BASELINE_RELEVANCY = 0.6412


def chart_refusal(mode: str):
    t = THEMES[mode]
    with plt.rc_context(_base_rc(t)):
        fig, ax = plt.subplots(figsize=(7.2, 2.9))
        ypos = np.arange(len(REFUSAL))[::-1]

        for y, (label, n, val, emph) in zip(ypos, REFUSAL):
            _rounded_hbar(ax, y, val, 0.54,
                          t["series"] if emph else t["series_mute"])
            ax.text(val + 0.018, y, f"{val:.2f}", va="center", ha="left",
                    fontsize=8.6, color=t["ink"] if emph else t["ink_mute"],
                    fontweight="600" if emph else "normal")

        ax.axvline(BASELINE_RELEVANCY, color=t["accent2"], linewidth=1.6,
                   linestyle=(0, (4, 3)), zorder=4)
        ax.text(BASELINE_RELEVANCY + 0.006, len(REFUSAL) - 0.52,
                f"baseline {BASELINE_RELEVANCY:.2f}", fontsize=8,
                color=t["accent2"], va="top", ha="left")

        ax.set_yticks(ypos)
        ax.set_yticklabels([f"{lbl}   n={n}" for lbl, n, _, _ in REFUSAL],
                           fontsize=8.8, color=t["ink"])
        ax.set_xlim(0, 1.0)
        ax.set_ylim(-0.7, len(REFUSAL) - 0.3)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_xticklabels(["0", "0.25", "0.50", "0.75", "1.00"], fontsize=8,
                           color=t["ink_mute"])
        ax.xaxis.grid(True, color=t["grid"], linewidth=1)
        ax.set_axisbelow(True)
        _strip_axes(ax, t)
        ax.set_xlabel("RAGAS answer relevancy", fontsize=8.4, color=t["ink_soft"],
                      labelpad=8)

        fig.text(0.0, 1.10, "What refusing costs, and what it buys",
                 fontsize=11.5, fontweight="600", color=t["ink"], ha="left")
        fig.text(
            0.0, 1.012,
            "30 of 80 rows are correct refusals, which RAGAS scores at 0 relevancy by construction. The baseline scored higher by guessing.",
            fontsize=8.4, color=t["ink_mute"], ha="left",
        )
        _save(fig, "refusal", mode)


def main():
    for mode in ("light", "dark"):
        print(f"[{mode}]")
        chart_ablation(mode)
        chart_coverage(mode)
        chart_measurability(mode)
        chart_refusal(mode)
    print("\nDone.")


if __name__ == "__main__":
    main()
