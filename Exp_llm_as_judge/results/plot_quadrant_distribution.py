"""Plot the quadrant distribution of the privacy-utility trade-off.

Adapted for ``Exp_llm_as_judge/results/`` where the source CSV produced by
``analyze_judged.py`` is ``05_tradeoff_quadrants.csv`` and uses the column
schema:

    dataset, n_scored,
    high_util_high_risk,        high_util_high_risk_pct,
    high_util_low_risk_(ideal), high_util_low_risk_pct,
    low_util_low_risk,          low_util_low_risk_pct,
    low_util_high_risk_(worst), low_util_high_risk_pct

Quadrant definition (kept consistent with ``analyze_judged.py``):
    Ideal           : utility_score >  0.7 AND reid_risk <= 0.5
    High-U / High-R : utility_score >  0.7 AND reid_risk >  0.5
    Low-U  / Low-R  : utility_score <= 0.5 AND reid_risk <= 0.5
    Worst           : utility_score <= 0.5 AND reid_risk >  0.5

Inputs
------
- analysis/05_tradeoff_quadrants.csv  (produced by analyze_judged.py)

Outputs
-------
- analysis/08_quadrant_distribution.png
- analysis/08_quadrant_distribution.pdf
- analysis/08_quadrant_distribution.csv  (tidy long-format table)
"""

from __future__ import annotations

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

QUAD_CSV = ANALYSIS_DIR / "05_tradeoff_quadrants.csv"

OUT_PNG = ANALYSIS_DIR / "08_quadrant_distribution.png"
OUT_PDF = ANALYSIS_DIR / "08_quadrant_distribution.pdf"
OUT_CSV = ANALYSIS_DIR / "08_quadrant_distribution.csv"

# ---------------------------------------------------------------------------
# Publication-quality matplotlib defaults
# ---------------------------------------------------------------------------
mpl.rcParams.update({
    "font.family":        "serif",
    "font.serif":         ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset":   "stix",
    "axes.titlesize":     14,
    "axes.labelsize":     14,
    "xtick.labelsize":    13,
    "ytick.labelsize":    13,
    "legend.fontsize":    13,
    "axes.linewidth":     1.0,
    "xtick.major.width":  1.0,
    "ytick.major.width":  1.0,
    "xtick.major.size":   4,
    "ytick.major.size":   4,
    "pdf.fonttype":       42,
    "ps.fonttype":        42,
})

# Column order in the final figure (left -> right within each group).
# Each tuple is (display label, column name in 05_tradeoff_quadrants.csv).
QUADRANTS = [
    ("Ideal\n(high $U$, low $R$)",  "high_util_low_risk_pct"),
    ("High-$U$ / High-$R$",         "high_util_high_risk_pct"),
    ("Low-$U$ / Low-$R$",           "low_util_low_risk_pct"),
    ("Worst\n(low $U$, high $R$)",  "low_util_high_risk_pct"),
]

# Mapping from the raw ``dataset`` column in the CSV to the camera-ready
# system name shown in the legend.  Order here defines plotting order.
SYSTEM_ORDER = [
    ("our",      "Ours"),
    ("papillon", "Papillon"),
    ("prediax",  "Presidio"),
    ("PUFT",     "PUFT"),
]

# Muted, color-blind-friendly palette. "Ours" uses the vermillion red so
# it pops against the cool baselines; PUFT gets a warm goldenrod.
SYSTEM_COLORS = {
    "Ours":     "#D7263D",  # vermillion red - our method
    "Papillon": "#1B6CA8",  # steel blue
    "Presidio": "#2E8B57",  # sea green
    "PUFT":     "#E1A100",  # goldenrod
}
SYSTEM_HATCH = {
    "Ours":     "",
    "Papillon": "//",
    "Presidio": "xx",
    "PUFT":     "..",
}

# Light background tints: green for the "good" Ideal column, red for the
# "bad" Worst column.
QUAD_BG = {
    0: "#E8F5E9",   # Ideal - very light green
    1: None,
    2: None,
    3: "#FDECEA",   # Worst - very light red
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_quadrants() -> pd.DataFrame:
    """Load the per-system quadrant percentages.

    Returns a DataFrame indexed by display name (Ours/Papillon/Prediax/PUFT)
    with columns matching ``QUADRANTS`` (``*_pct``).
    """
    if not QUAD_CSV.exists():
        raise FileNotFoundError(
            f"Expected {QUAD_CSV}. Run analyze_judged.py first."
        )

    df = pd.read_csv(QUAD_CSV)
    # Drop the aggregate row; we only show per-system bars.
    df = df[df["dataset"] != "ALL"].copy()
    df["dataset"] = df["dataset"].astype(str).str.strip()

    # Re-index by display name in the desired order; tolerate missing systems.
    raw_to_display = dict(SYSTEM_ORDER)
    df = df[df["dataset"].isin(raw_to_display.keys())]
    df["system"] = df["dataset"].map(raw_to_display)
    df = df.set_index("system")
    ordered = [d for _, d in SYSTEM_ORDER if d in df.index]
    df = df.loc[ordered].reset_index()
    return df


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def plot_quadrants(df: pd.DataFrame) -> None:
    quad_labels = [q[0] for q in QUADRANTS]
    quad_cols   = [q[1] for q in QUADRANTS]

    systems = df["system"].tolist()
    n_quad   = len(QUADRANTS)
    n_system = len(systems)

    x = np.arange(n_quad, dtype=float)
    group_w = 0.78                 # total group width
    bar_w   = group_w / n_system

    # Slightly wider canvas to accommodate the 4th system.
    fig, ax = plt.subplots(figsize=(9.5, 4.6))

    # --- Background bands to flag "good" / "bad" quadrants ----------------
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
    for i, system in enumerate(systems):
        row = df[df["system"] == system].iloc[0]
        values = [float(row[c]) for c in quad_cols]
        all_max = max(all_max, max(values))
        offsets = (i - (n_system - 1) / 2.0) * bar_w
        bars = ax.bar(
            x + offsets,
            values,
            width=bar_w * 0.92,        # small gap between adjacent bars
            label=system,
            color=SYSTEM_COLORS.get(system, "#888888"),
            edgecolor="black",
            linewidth=0.7,
            hatch=SYSTEM_HATCH.get(system, ""),
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
                fontsize=11,
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
        bbox_to_anchor=(0.5, 1.16),
        ncol=n_system,
        frameon=False,
        handlelength=1.8,
        handletextpad=0.6,
        columnspacing=2.0,
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
