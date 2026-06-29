# -*- coding: utf-8 -*-
"""
Render Table 4-style privacy-leak rate table from existing analysis results.

Source data:
    analysis/02_privacy_issue_counts.csv

Outputs (under analysis/):
    - 09_privacy_leak_table.csv     : tidy CSV with the 6 columns
    - 09_privacy_leak_table.md      : Markdown rendering
    - 09_privacy_leak_table.tex     : LaTeX booktabs rendering
    - 09_privacy_leak_table.png/pdf : matplotlib figure rendering of the table
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

RESULTS_DIR = Path("/group/40047/eiraxyhuang/workspace/fc/DataG/Exp_llm_as_judge/results")
ANALYSIS_DIR = RESULTS_DIR / "analysis"
SRC_CSV = ANALYSIS_DIR / "02_privacy_issue_counts.csv"

# Order of systems as they should appear in the table.
SYSTEM_ORDER: List[str] = ["papillon", "prediax", "PUFT", "our"]
# Display names (column "System") for the rendered tables.
DISPLAY_NAMES = {
    "our": "Ours",
    "papillon": "PAPILLON",
    "prediax": "PrediaX",
    "PUFT": "PUFT",
}

COLUMNS = ["System", "direct", "semantic", "infer.", "comb.", r"$\geq 1$", r"$\geq 2$"]


def build_table() -> pd.DataFrame:
    src = pd.read_csv(SRC_CSV)
    src = src.set_index("dataset")

    rows = []
    for sys_key in SYSTEM_ORDER:
        if sys_key not in src.index:
            continue
        r = src.loc[sys_key]
        rows.append({
            "System": DISPLAY_NAMES.get(sys_key, sys_key),
            "direct": float(r["direct_leak_sample_pct"]),
            "semantic": float(r["semantic_leak_sample_pct"]),
            "infer.": float(r["inferential_leak_sample_pct"]),
            "comb.": float(r["combination_leak_sample_pct"]),
            ">=1": float(r["any_issue_pct"]),
            ">=2": float(r["multi_issue_pct"]),
        })
    return pd.DataFrame(rows)


def fmt_pct(x: float) -> str:
    # one decimal place, like the paper.
    return f"{x:.1f}"


def write_csv(df: pd.DataFrame, path: Path) -> None:
    out = df.copy()
    for col in ["direct", "semantic", "infer.", "comb.", ">=1", ">=2"]:
        out[col] = out[col].map(fmt_pct)
    out.to_csv(path, index=False)


def write_markdown(df: pd.DataFrame, path: Path) -> None:
    headers = ["System", "direct", "semantic", "infer.", "comb.", "≥1", "≥2"]
    lines = []
    lines.append(
        "**Table 4: Privacy-leak rates (%) by category.** Direct, semantic, "
        "inferential, and combination leaks denote verbatim retention, "
        "recoverable paraphrase, contextual inference, and re-identification "
        "from combined cues, respectively. ≥1 / ≥2 denote rewrites with at "
        "least one / two leak categories."
    )
    lines.append("")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, r in df.iterrows():
        lines.append(
            "| " + r["System"] + " | "
            + fmt_pct(r["direct"]) + " | "
            + fmt_pct(r["semantic"]) + " | "
            + fmt_pct(r["infer."]) + " | "
            + fmt_pct(r["comb."]) + " | "
            + fmt_pct(r[">=1"]) + " | "
            + fmt_pct(r[">=2"]) + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_latex(df: pd.DataFrame, path: Path) -> None:
    body_lines = []
    for _, r in df.iterrows():
        body_lines.append(
            f"{r['System']} & {fmt_pct(r['direct'])} & {fmt_pct(r['semantic'])} "
            f"& {fmt_pct(r['infer.'])} & {fmt_pct(r['comb.'])} "
            f"& {fmt_pct(r['>=1'])} & {fmt_pct(r['>=2'])} \\\\"
        )
    tex = (
        "\\begin{table}[t]\n"
        "\\centering\n"
        "\\small\n"
        "\\caption{Privacy-leak rates (\\%) by category. Direct, semantic, "
        "inferential, and combination leaks denote verbatim retention, "
        "recoverable paraphrase, contextual inference, and re-identification "
        "from combined cues, respectively. $\\geq 1$ / $\\geq 2$ denote "
        "rewrites with at least one / two leak categories.}\n"
        "\\label{tab:privacy_leak}\n"
        "\\begin{tabular}{lcccccc}\n"
        "\\toprule\n"
        "System & direct & semantic & infer. & comb. & $\\geq 1$ & $\\geq 2$ \\\\\n"
        "\\midrule\n"
        + "\n".join(body_lines) + "\n"
        "\\bottomrule\n"
        "\\end{tabular}\n"
        "\\end{table}\n"
    )
    path.write_text(tex, encoding="utf-8")


def render_figure(df: pd.DataFrame, png_path: Path, pdf_path: Path) -> None:
    headers = ["System", "direct", "semantic", "infer.", "comb.", r"$\geq 1$", r"$\geq 2$"]
    cell_text = []
    for _, r in df.iterrows():
        cell_text.append([
            r["System"],
            fmt_pct(r["direct"]),
            fmt_pct(r["semantic"]),
            fmt_pct(r["infer."]),
            fmt_pct(r["comb."]),
            fmt_pct(r[">=1"]),
            fmt_pct(r[">=2"]),
        ])

    n_rows = len(cell_text)
    fig_height = 1.0 + 0.45 * n_rows
    fig, ax = plt.subplots(figsize=(8.5, fig_height))
    ax.axis("off")

    title = (
        "Table 4: Privacy-leak rates (%) by category. Direct, semantic, "
        "inferential, and\ncombination leaks denote verbatim retention, "
        "recoverable paraphrase, contextual\ninference, and re-identification "
        "from combined cues, respectively.\n"
        r"$\geq 1$ / $\geq 2$ denote rewrites with at least one / two leak categories."
    )
    ax.set_title(title, fontsize=10, loc="left", pad=14)

    table = ax.table(
        cellText=cell_text,
        colLabels=headers,
        cellLoc="center",
        colLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.0, 1.5)

    n_cols = len(headers)
    # Style header row.
    for j in range(n_cols):
        c = table[(0, j)]
        c.set_text_props(weight="bold")
        c.set_facecolor("#f2f2f2")
        c.set_edgecolor("black")
    # Style body cells: only top/bottom borders to mimic booktabs look.
    for i in range(1, n_rows + 1):
        for j in range(n_cols):
            c = table[(i, j)]
            c.visible_edges = "horizontal"
            c.set_edgecolor("#999999")
            if j == 0:
                c.set_text_props(ha="left")
                c.PAD = 0.04

    # Find best (lowest) value per column among body rows for highlighting.
    body_arr = df[["direct", "semantic", "infer.", "comb.", ">=1", ">=2"]].values
    # Skip column 0 (System).
    for col_idx in range(body_arr.shape[1]):
        col_vals = body_arr[:, col_idx]
        min_val = col_vals.min()
        for i, v in enumerate(col_vals):
            if abs(v - min_val) < 1e-9:
                table[(i + 1, col_idx + 1)].set_text_props(weight="bold")

    fig.tight_layout()
    fig.savefig(png_path, dpi=200, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    df = build_table()
    print("[info] table data:")
    print(df.to_string(index=False))

    csv_path = ANALYSIS_DIR / "09_privacy_leak_table.csv"
    md_path = ANALYSIS_DIR / "09_privacy_leak_table.md"
    tex_path = ANALYSIS_DIR / "09_privacy_leak_table.tex"
    png_path = ANALYSIS_DIR / "09_privacy_leak_table.png"
    pdf_path = ANALYSIS_DIR / "09_privacy_leak_table.pdf"

    write_csv(df, csv_path)
    write_markdown(df, md_path)
    write_latex(df, tex_path)
    render_figure(df, png_path, pdf_path)

    print(f"[done] wrote: {csv_path}")
    print(f"[done] wrote: {md_path}")
    print(f"[done] wrote: {tex_path}")
    print(f"[done] wrote: {png_path}")
    print(f"[done] wrote: {pdf_path}")


if __name__ == "__main__":
    main()
