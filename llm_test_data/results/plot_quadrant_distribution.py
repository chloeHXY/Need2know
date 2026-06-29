"""Plot the quadrant distribution of the privacy-utility trade-off.

Quadrant definition (consistent with analyze_judged.py and the paper):
    Ideal           : utility_score >  0.7 AND reid_risk <= 0.5
    High-U / High-R : utility_score >  0.7 AND reid_risk >  0.5
    Low-U  / Low-R  : utility_score <= 0.7 AND reid_risk <= 0.5
    Worst           : utility_score <= 0.7 AND reid_risk >  0.5

Inputs
------
- 05_tradeoff_paper_quadrants.csv : the 3-system aggregate already produced by
  analyze_judged.py
- (optional) the per-sample parquet files under results/, used only when the
  CSV is missing, in which case we recompute quadrants from raw scores.

Outputs
-------
- analysis/08_quadrant_distribution.png
- analysis/08_quadrant_distribution.pdf
- analysis/08_quadrant_distribution.csv  (tidy long-format table)
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
ANALYSIS_DIR = ROOT / "analysis"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

PAPER_CSV = ANALYSIS_DIR / "05_tradeoff_paper_quadrants.csv"

OUT_PNG = ANALYSIS_DIR / "08_quadrant_distribution.png"
OUT_PDF = ANALYSIS_DIR / "08_quadrant_distribution.pdf"
OUT_CSV = ANALYSIS_DIR / "08_quadrant_distribution.csv"

# ---------------------------------------------------------------------------
# Publication-quality matplotlib defaults
# ---------------------------------------------------------------------------
# Use a serif font similar to LaTeX's default (Times) for camera-ready papers.
# If a TeX installation is available, set ``text.usetex`` to True for crispest
# math typography; we keep mathtext as a safe fallback for sandboxed envs.
mpl.rcParams.update({
    "font.family":        "serif",
    "font.serif":         ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset":   "stix",
    "axes.titlesize":     10,
    "axes.labelsize":     10,
    "xtick.labelsize":    9,
    "ytick.labelsize":    9,
    "legend.fontsize":    9,
    "axes.linewidth":     0.8,
    "xtick.major.width":  0.8,
    "ytick.major.width":  0.8,
    "xtick.major.size":   3,
    "ytick.major.size":   3,
    "pdf.fonttype":       42,   # embed TrueType so reviewers can copy text
    "ps.fonttype":        42,
})

# Column order in the final figure (left -> right within each group)
QUADRANTS = [
    ("Ideal\n(high $U$, low $R$)",  "ideal_pct"),
    ("High-$U$ / High-$R$",         "high_u_high_r_pct"),
    ("Low-$U$ / Low-$R$",           "low_u_low_r_pct"),
    ("Worst\n(low $U$, high $R$)",  "worst_pct"),
]

SYSTEM_ORDER = ["Ours", "Papillon", "Prediax"]

# Muted, color-blind-friendly palette (Okabe-Ito inspired). "Ours" uses the
# vermillion/red so that it pops against the cool baselines.
SYSTEM_COLORS = {
    "Ours":     "#D7263D",  # vermillion red - our method
    "Papillon": "#1B6CA8",  # steel blue
    "Prediax":  "#2E8B57",  # sea green
}
SYSTEM_HATCH = {
    "Ours":     "",     # solid - draw the eye
    "Papillon": "//",
    "Prediax":  "xx",
}

# Light background tints: green for the "good" Ideal column, red for the
# "bad" Worst column.  These cues make the take-away readable at a glance.
QUAD_BG = {
    0: "#E8F5E9",   # Ideal      - very light green
    1: None,
    2: None,
    3: "#FDECEA",   # Worst      - very light red
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_quadrants() -> pd.DataFrame:
    """Load the per-system quadrant percentages.

    Returns a DataFrame with columns:
        system, ideal_pct, high_u_high_r_pct, low_u_low_r_pct, worst_pct
    """
    if not PAPER_CSV.exists():
        raise FileNotFoundError(
            f"Expected {PAPER_CSV}. Run analyze_judged.py first."
        )

    df = pd.read_csv(PAPER_CSV)
    # Normalize the system column to title case ("Ours" / "Papillon" / "Prediax")
    df["system"] = df["system"].astype(str).str.strip().str.title()
    df = df.set_index("system").loc[SYSTEM_ORDER].reset_index()
    return df


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def plot_quadrants(df: pd.DataFrame) -> None:
    quad_labels = [q[0] for q in QUADRANTS]
    quad_cols   = [q[1] for q in QUADRANTS]

    n_quad   = len(QUADRANTS)
    n_system = len(SYSTEM_ORDER)

    x = np.arange(n_quad, dtype=float)
    group_w = 0.74                 # total group width
    bar_w   = group_w / n_system

    # Single-column friendly aspect ratio (golden-ratio-ish)
    fig, ax = plt.subplots(figsize=(7.0, 3.6))

    # --- Background bands to flag "good" / "bad" quadrants ----------------
    y_top_pre = float(df[quad_cols].values.max()) * 1.30
    for qi, color in QUAD_BG.items():
        if color is None:
            continue
        ax.axvspan(
            x[qi] - 0.5, x[qi] + 0.5,
            ymin=0, ymax=1,
            color=color, zorder=0,
        )

    # --- Bars --------------------------------------------------------------
    all_max = 0.0
    for i, system in enumerate(SYSTEM_ORDER):
        row = df[df["system"] == system].iloc[0]
        values = [float(row[c]) for c in quad_cols]
        all_max = max(all_max, max(values))
        offsets = (i - (n_system - 1) / 2.0) * bar_w
        bars = ax.bar(
            x + offsets,
            values,
            width=bar_w * 0.92,        # small gap between adjacent bars
            label=system,
            color=SYSTEM_COLORS[system],
            edgecolor="black",
            linewidth=0.7,
            hatch=SYSTEM_HATCH[system],
            zorder=3,
        )
        # Value labels on top of each bar
        for b, v in zip(bars, values):
            ax.text(
                b.get_x() + b.get_width() / 2.0,
                b.get_height() + all_max * 0.015 + 0.05,
                f"{v:.1f}",
                ha="center",
                va="bottom",
                fontsize=8,
                color="#222222",
            )

    # --- Axes cosmetics ----------------------------------------------------
    ax.set_xticks(x)
    ax.set_xticklabels(quad_labels)
    ax.set_xlim(-0.5, n_quad - 0.5)
    ax.set_ylabel("Share of samples (\\%)" if mpl.rcParams["text.usetex"]
                  else "Share of samples (%)")

    y_top = max(all_max * 1.28, 16.0)
    ax.set_ylim(0, y_top)

    # Subtle horizontal grid only
    ax.yaxis.grid(True, linestyle=":", linewidth=0.6, color="#888888", alpha=0.7)
    ax.set_axisbelow(True)

    # Clean spines: keep left & bottom only
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color("#444444")
    ax.spines["bottom"].set_color("#444444")

    ax.tick_params(axis="x", which="both", length=0, pad=4)
    ax.tick_params(axis="y", which="both", color="#444444")

    # --- Legend on top, horizontal, frameless -----------------------------
    leg = ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.14),
        ncol=n_system,
        frameon=False,
        handlelength=1.6,
        handletextpad=0.5,
        columnspacing=1.6,
    )
    leg.set_zorder(5)

    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=400, bbox_inches="tight", transparent=False)
    fig.savefig(OUT_PDF,            bbox_inches="tight", transparent=False)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Tidy CSV export (one row per (system, quadrant))
# ---------------------------------------------------------------------------
def export_tidy(df: pd.DataFrame) -> None:
    rows = []
    for _, r in df.iterrows():
        for label, col in QUADRANTS:
            rows.append(
                {
                    "system":   r["system"],
                    "quadrant": label.replace("\n", " "),
                    "pct":      round(float(r[col]), 2),
                }
            )
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)


def main() -> None:
    df = load_quadrants()
    plot_quadrants(df)
    export_tidy(df)
    print("Saved:")
    print(f"  - {OUT_PNG}")
    print(f"  - {OUT_PDF}")
    print(f"  - {OUT_CSV}")


if __name__ == "__main__":
    main()
