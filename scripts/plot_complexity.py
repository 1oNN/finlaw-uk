# plot_complexity.py
import pandas as pd
import matplotlib.pyplot as plt
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: python plot_complexity.py <questions.csv> [out.png]")
        sys.exit(1)

    infile = sys.argv[1]
    outfile = sys.argv[2] if len(sys.argv) > 2 else "complexity_dist.png"

    df = pd.read_csv(infile)
    counts = df['complexity'].value_counts().reindex(
        ['basic', 'intermediate', 'advanced']
    ).fillna(0)

    plt.figure(figsize=(6, 4))
    plt.bar(counts.index, counts.values, color=["#4daf4a", "#377eb8", "#e41a1c"])

    for i, v in enumerate(counts.values):
        plt.text(i, v + 0.5, int(v), ha='center', fontsize=10)

    plt.title("Distribution of Evaluation Questions by Complexity Level")
    plt.ylabel("Number of Questions")
    plt.xlabel("Complexity Level")
    plt.tight_layout()
    plt.savefig(outfile, dpi=160)
    print(f"Saved plot to {outfile}")

if __name__ == "__main__":
    main()
