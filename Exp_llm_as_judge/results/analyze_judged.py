# -*- coding: utf-8 -*-
"""
Analyze LLM-as-Judge outputs for privacy-rewrite quality.

Inputs (under llm_test_data/results/):
    - our_judged.parquet
    - papillon_judged.parquet
    - prediax_judged.parquet
    - PUFT_judged.parquet

Each row contains:
    - extra_info["question"]            : original question
    - priv_query                        : privacy-rewritten query
    - judge_parsed                      : JSON string with the evaluator output
    - judge_verdict / judge_reid_risk / judge_utility_score / judge_confidence

Outputs (written to llm_test_data/results/analysis/):
    - summary tables (CSV)
    - visualizations (PNG)
    - case studies (Markdown)
    - findings.md (concise written findings)
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RESULTS_DIR = Path("/group/40047/eiraxyhuang/workspace/fc/DataG/Exp_llm_as_judge/results")
OUT_DIR = RESULTS_DIR / "analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DATASETS = ["our", "papillon", "prediax","PUFT"]

PRIVACY_TYPES = ["direct_leak", "semantic_leak", "inferential_leak", "combination_leak"]
UTILITY_TYPES = [
    "lost_constraint", "weakened_constraint",
    "over_generalization", "task_drift", "added_constraint",
]
VERDICTS = ["good", "acceptable", "bad"]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_one(name: str) -> pd.DataFrame:
    df = pd.read_parquet(RESULTS_DIR / f"{name}_judged.parquet")
    df = df[df["judge_ok"] == True].reset_index(drop=True).copy()  # noqa: E712

    parsed: List[Optional[dict]] = []
    questions: List[str] = []
    for _, row in df.iterrows():
        try:
            p = json.loads(row["judge_parsed"]) if row.get("judge_parsed") else None
        except Exception:
            p = None
        parsed.append(p if isinstance(p, dict) else None)

        extra = row.get("extra_info") or {}
        if not isinstance(extra, dict):
            try:
                extra = dict(extra)
            except Exception:
                extra = {}
        questions.append(str(extra.get("question") or ""))

    df["parsed"] = parsed
    df["question"] = questions
    df["dataset"] = name
    return df


def load_all() -> pd.DataFrame:
    parts = [load_one(n) for n in DATASETS]
    return pd.concat(parts, ignore_index=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_list(parsed: Optional[dict], key: str) -> List[dict]:
    if not isinstance(parsed, dict):
        return []
    v = parsed.get(key)
    if not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, dict)]


def issue_types(parsed: Optional[dict], key: str) -> List[str]:
    out: List[str] = []
    for it in _safe_list(parsed, key):
        t = it.get("type")
        if isinstance(t, str) and t.strip():
            out.append(t.strip().lower())
    return out


# ---------------------------------------------------------------------------
# 1. Overall statistics
# ---------------------------------------------------------------------------
def overall_stats(df: pd.DataFrame) -> Dict[str, Any]:
    rows = []
    for name, sub in [("ALL", df)] + [(n, df[df["dataset"] == n]) for n in DATASETS]:
        vc = sub["judge_verdict"].value_counts(dropna=False)
        total = len(sub)
        row = {"dataset": name, "n": total}
        for v in VERDICTS:
            row[f"verdict_{v}"] = int(vc.get(v, 0))
            row[f"verdict_{v}_pct"] = round(100.0 * vc.get(v, 0) / max(total, 1), 2)

        for col in ["judge_reid_risk", "judge_utility_score", "judge_confidence"]:
            s = pd.to_numeric(sub[col], errors="coerce").dropna()
            row[f"{col}_mean"] = round(float(s.mean()), 4) if len(s) else None
            row[f"{col}_median"] = round(float(s.median()), 4) if len(s) else None
            row[f"{col}_std"] = round(float(s.std()), 4) if len(s) else None

        a = pd.to_numeric(sub["judge_reid_risk"], errors="coerce")
        b = pd.to_numeric(sub["judge_utility_score"], errors="coerce")
        mask = a.notna() & b.notna()
        if mask.sum() >= 3:
            corr_p = float(np.corrcoef(a[mask], b[mask])[0, 1])
            corr_s = float(pd.Series(a[mask]).corr(pd.Series(b[mask]), method="spearman"))
        else:
            corr_p = corr_s = float("nan")
        row["pearson_reid_vs_util"] = round(corr_p, 4)
        row["spearman_reid_vs_util"] = round(corr_s, 4)
        rows.append(row)

    table = pd.DataFrame(rows)
    table.to_csv(OUT_DIR / "01_overall_stats.csv", index=False)

    # --- Visualizations ---
    fig, ax = plt.subplots(figsize=(7, 4))
    width = 0.25
    x = np.arange(len(VERDICTS))
    for i, name in enumerate(DATASETS):
        sub = df[df["dataset"] == name]
        vals = [(sub["judge_verdict"] == v).mean() * 100 for v in VERDICTS]
        ax.bar(x + (i - 1) * width, vals, width, label=name)
    ax.set_xticks(x)
    ax.set_xticklabels(VERDICTS)
    ax.set_ylabel("percent of samples (%)")
    ax.set_title("Verdict distribution by dataset")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "01_verdict_distribution.png", dpi=140)
    plt.close(fig)

    # Histograms of reid_risk and utility_score
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for name in DATASETS:
        sub = df[df["dataset"] == name]
        axes[0].hist(pd.to_numeric(sub["judge_reid_risk"], errors="coerce").dropna(),
                     bins=20, alpha=0.45, label=name)
        axes[1].hist(pd.to_numeric(sub["judge_utility_score"], errors="coerce").dropna(),
                     bins=20, alpha=0.45, label=name)
    axes[0].set_title("reid_risk distribution")
    axes[0].set_xlabel("reid_risk"); axes[0].set_ylabel("count"); axes[0].legend()
    axes[1].set_title("utility_score distribution")
    axes[1].set_xlabel("utility_score"); axes[1].set_ylabel("count"); axes[1].legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "01_score_histograms.png", dpi=140)
    plt.close(fig)

    return {"table": table}


# ---------------------------------------------------------------------------
# 2. Privacy issue analysis
# ---------------------------------------------------------------------------
def privacy_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    rows = []
    # frequency table per dataset
    for name in ["ALL"] + DATASETS:
        sub = df if name == "ALL" else df[df["dataset"] == name]
        n = len(sub)
        all_types: List[str] = []
        per_row_types: List[List[str]] = []
        for p in sub["parsed"]:
            ts = issue_types(p, "privacy_issues")
            per_row_types.append(ts)
            all_types.extend(ts)

        cnt = Counter(all_types)
        row = {"dataset": name, "n_samples": n, "n_issue_instances": len(all_types)}
        for t in PRIVACY_TYPES:
            row[t] = int(cnt.get(t, 0))
            # samples containing at least one issue of this type
            row[f"{t}_sample_pct"] = round(
                100.0 * sum(1 for ts in per_row_types if t in ts) / max(n, 1), 2)

        # any privacy issue
        any_issue = sum(1 for ts in per_row_types if ts)
        multi_issue = sum(1 for ts in per_row_types if len(set(ts)) >= 2)
        row["any_issue_pct"] = round(100.0 * any_issue / max(n, 1), 2)
        row["multi_issue_pct"] = round(100.0 * multi_issue / max(n, 1), 2)
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(OUT_DIR / "02_privacy_issue_counts.csv", index=False)

    # average reid_risk by privacy issue type (using ALL data, sample-level)
    avg_rows = []
    for t in PRIVACY_TYPES:
        mask = df["parsed"].apply(lambda p: t in issue_types(p, "privacy_issues"))
        s = pd.to_numeric(df.loc[mask, "judge_reid_risk"], errors="coerce").dropna()
        avg_rows.append({
            "issue_type": t,
            "n_samples_with_type": int(mask.sum()),
            "mean_reid_risk": round(float(s.mean()), 4) if len(s) else None,
            "median_reid_risk": round(float(s.median()), 4) if len(s) else None,
        })
    # baseline: no privacy issues
    no_issue_mask = df["parsed"].apply(
        lambda p: len(issue_types(p, "privacy_issues")) == 0)
    s = pd.to_numeric(df.loc[no_issue_mask, "judge_reid_risk"],
                      errors="coerce").dropna()
    avg_rows.append({
        "issue_type": "(no privacy issue)",
        "n_samples_with_type": int(no_issue_mask.sum()),
        "mean_reid_risk": round(float(s.mean()), 4) if len(s) else None,
        "median_reid_risk": round(float(s.median()), 4) if len(s) else None,
    })
    avg_table = pd.DataFrame(avg_rows)
    avg_table.to_csv(OUT_DIR / "02_privacy_issue_reid_risk.csv", index=False)

    # Visualization: per-dataset bar chart of issue rates
    fig, ax = plt.subplots(figsize=(8, 4.5))
    width = 0.25
    x = np.arange(len(PRIVACY_TYPES))
    for i, name in enumerate(DATASETS):
        sub = df[df["dataset"] == name]
        n = len(sub)
        per_row_types = [issue_types(p, "privacy_issues") for p in sub["parsed"]]
        vals = [100.0 * sum(1 for ts in per_row_types if t in ts) / max(n, 1)
                for t in PRIVACY_TYPES]
        ax.bar(x + (i - 1) * width, vals, width, label=name)
    ax.set_xticks(x)
    ax.set_xticklabels(PRIVACY_TYPES, rotation=20)
    ax.set_ylabel("samples with this issue (%)")
    ax.set_title("Privacy issue prevalence by dataset")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "02_privacy_issue_rates.png", dpi=140)
    plt.close(fig)

    # avg reid_risk per type
    fig, ax = plt.subplots(figsize=(7, 4))
    labels = [r["issue_type"] for r in avg_rows]
    vals = [r["mean_reid_risk"] or 0 for r in avg_rows]
    ax.bar(labels, vals, color="#c0504d")
    ax.set_ylabel("mean reid_risk")
    ax.set_title("Mean reid_risk by privacy issue type (ALL)")
    plt.xticks(rotation=20)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "02_privacy_issue_mean_reid.png", dpi=140)
    plt.close(fig)

    return {"table": table, "avg_table": avg_table}


# ---------------------------------------------------------------------------
# 3. Utility issue analysis
# ---------------------------------------------------------------------------
def utility_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    rows = []
    for name in ["ALL"] + DATASETS:
        sub = df if name == "ALL" else df[df["dataset"] == name]
        n = len(sub)
        all_types: List[str] = []
        per_row_types: List[List[str]] = []
        for p in sub["parsed"]:
            ts = issue_types(p, "utility_issues")
            per_row_types.append(ts)
            all_types.extend(ts)
        cnt = Counter(all_types)
        row = {"dataset": name, "n_samples": n, "n_issue_instances": len(all_types)}
        for t in UTILITY_TYPES:
            row[t] = int(cnt.get(t, 0))
            row[f"{t}_sample_pct"] = round(
                100.0 * sum(1 for ts in per_row_types if t in ts) / max(n, 1), 2)
        any_issue = sum(1 for ts in per_row_types if ts)
        multi_issue = sum(1 for ts in per_row_types if len(set(ts)) >= 2)
        row["any_issue_pct"] = round(100.0 * any_issue / max(n, 1), 2)
        row["multi_issue_pct"] = round(100.0 * multi_issue / max(n, 1), 2)
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(OUT_DIR / "03_utility_issue_counts.csv", index=False)

    # avg utility_score per type
    avg_rows = []
    for t in UTILITY_TYPES:
        mask = df["parsed"].apply(lambda p: t in issue_types(p, "utility_issues"))
        s = pd.to_numeric(df.loc[mask, "judge_utility_score"],
                          errors="coerce").dropna()
        avg_rows.append({
            "issue_type": t,
            "n_samples_with_type": int(mask.sum()),
            "mean_utility": round(float(s.mean()), 4) if len(s) else None,
            "median_utility": round(float(s.median()), 4) if len(s) else None,
        })
    no_issue_mask = df["parsed"].apply(
        lambda p: len(issue_types(p, "utility_issues")) == 0)
    s = pd.to_numeric(df.loc[no_issue_mask, "judge_utility_score"],
                      errors="coerce").dropna()
    avg_rows.append({
        "issue_type": "(no utility issue)",
        "n_samples_with_type": int(no_issue_mask.sum()),
        "mean_utility": round(float(s.mean()), 4) if len(s) else None,
        "median_utility": round(float(s.median()), 4) if len(s) else None,
    })
    avg_table = pd.DataFrame(avg_rows)
    avg_table.to_csv(OUT_DIR / "03_utility_issue_utility_score.csv", index=False)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    width = 0.25
    x = np.arange(len(UTILITY_TYPES))
    for i, name in enumerate(DATASETS):
        sub = df[df["dataset"] == name]
        n = len(sub)
        per_row_types = [issue_types(p, "utility_issues") for p in sub["parsed"]]
        vals = [100.0 * sum(1 for ts in per_row_types if t in ts) / max(n, 1)
                for t in UTILITY_TYPES]
        ax.bar(x + (i - 1) * width, vals, width, label=name)
    ax.set_xticks(x)
    ax.set_xticklabels(UTILITY_TYPES, rotation=20)
    ax.set_ylabel("samples with this issue (%)")
    ax.set_title("Utility issue prevalence by dataset")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "03_utility_issue_rates.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    labels = [r["issue_type"] for r in avg_rows]
    vals = [r["mean_utility"] or 0 for r in avg_rows]
    ax.bar(labels, vals, color="#4f81bd")
    ax.set_ylabel("mean utility_score")
    ax.set_title("Mean utility_score by utility issue type (ALL)")
    plt.xticks(rotation=20)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "03_utility_issue_mean_util.png", dpi=140)
    plt.close(fig)

    return {"table": table, "avg_table": avg_table}


# ---------------------------------------------------------------------------
# 4. New sensitive
# ---------------------------------------------------------------------------
# very lightweight categorization
CATEGORY_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("location/place", re.compile(
        r"\b(city|street|district|province|state|country|region|address|"
        r"village|town|county|location)\b", re.I)),
    ("demographic/age/gender", re.compile(
        r"\b(age|year[- ]?old|gender|male|female|man|woman|boy|girl|"
        r"teen|elderly|young|old)\b", re.I)),
    ("medical/health", re.compile(
        r"\b(disease|symptom|diagnos|cancer|diabet|depress|anxiety|"
        r"medication|prescrip|hospital|clinic|patient|surgery|illness|"
        r"medical|HIV|pregnan)\b", re.I)),
    ("financial", re.compile(
        r"\b(salary|income|bank|account|loan|debt|credit|tax|payment|"
        r"\$|USD|EUR|RMB)\b", re.I)),
    ("occupation/role", re.compile(
        r"\b(engineer|doctor|teacher|lawyer|nurse|manager|developer|"
        r"student|professor|ceo|officer|employee|worker|profession|job|"
        r"role|occupation)\b", re.I)),
    ("organization/company", re.compile(
        r"\b(company|corp|inc\.|ltd|llc|university|school|college|"
        r"hospital|organization|institute|firm)\b", re.I)),
    ("relationship/family", re.compile(
        r"\b(wife|husband|spouse|partner|girlfriend|boyfriend|mother|"
        r"father|son|daughter|sibling|brother|sister|family|friend|"
        r"colleague)\b", re.I)),
    ("religion/ethnicity", re.compile(
        r"\b(christian|muslim|jewish|buddhis|hindu|atheist|asian|black|"
        r"white|hispanic|latino|ethnic|race|religion)\b", re.I)),
    ("contact/identifier", re.compile(
        r"\b(email|phone|@|\.com|number|id\b|passport|ssn|license)\b", re.I)),
    ("date/time-specific", re.compile(
        r"\b(20\d{2}|19\d{2}|january|february|march|april|may|june|july|"
        r"august|september|october|november|december|monday|tuesday)\b", re.I)),
]


def categorize_sensitive(span: str) -> str:
    if not span:
        return "other"
    for label, pat in CATEGORY_PATTERNS:
        if pat.search(span):
            return label
    return "other"


def new_sensitive_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    rows = []
    cat_counter = Counter()
    sample_with_new = 0
    total_new_items = 0
    for _, r in df.iterrows():
        items = _safe_list(r["parsed"], "new_sensitive")
        if items:
            sample_with_new += 1
        for it in items:
            total_new_items += 1
            span = str(it.get("span") or "").strip()
            cat = categorize_sensitive(span)
            cat_counter[cat] += 1
            rows.append({
                "dataset": r["dataset"],
                "category": cat,
                "span": span[:200],
                "reason": str(it.get("reason") or "")[:300],
                "verdict": r["judge_verdict"],
                "reid_risk": r["judge_reid_risk"],
                "utility_score": r["judge_utility_score"],
            })

    items_df = pd.DataFrame(rows)
    items_df.to_csv(OUT_DIR / "04_new_sensitive_items.csv", index=False)

    cat_df = pd.DataFrame(
        sorted(cat_counter.items(), key=lambda x: -x[1]),
        columns=["category", "count"],
    )
    cat_df["pct_of_items"] = (cat_df["count"] / max(total_new_items, 1) * 100).round(2)
    cat_df.to_csv(OUT_DIR / "04_new_sensitive_category_counts.csv", index=False)

    summary = {
        "n_samples_with_new_sensitive": int(sample_with_new),
        "pct_samples_with_new_sensitive": round(
            100.0 * sample_with_new / max(len(df), 1), 2),
        "total_new_sensitive_items": int(total_new_items),
        "categories": cat_counter.most_common(),
    }
    pd.Series(summary).to_json(OUT_DIR / "04_new_sensitive_summary.json", indent=2)

    # Visualization
    if not cat_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.bar(cat_df["category"], cat_df["count"], color="#9bbb59")
        ax.set_title("Newly introduced sensitive attributes by category (ALL)")
        ax.set_ylabel("count")
        plt.xticks(rotation=25, ha="right")
        fig.tight_layout()
        fig.savefig(OUT_DIR / "04_new_sensitive_categories.png", dpi=140)
        plt.close(fig)

    # Per-dataset rate
    fig, ax = plt.subplots(figsize=(6, 3.5))
    rates = []
    for name in DATASETS:
        sub = df[df["dataset"] == name]
        c = sub["parsed"].apply(lambda p: len(_safe_list(p, "new_sensitive")) > 0).sum()
        rates.append(100.0 * c / max(len(sub), 1))
    ax.bar(DATASETS, rates, color="#8064a2")
    ax.set_ylabel("samples with new_sensitive (%)")
    ax.set_title("New sensitive attribute rate per dataset")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "04_new_sensitive_rate.png", dpi=140)
    plt.close(fig)

    return {"summary": summary, "cat_df": cat_df}


# ---------------------------------------------------------------------------
# 5. Tradeoff scatter
# ---------------------------------------------------------------------------
def tradeoff_scatter(df: pd.DataFrame) -> Dict[str, Any]:
    n_ds = len(DATASETS)
    fig, axes = plt.subplots(1, n_ds, figsize=(5 * n_ds, 4.5),
                             sharex=True, sharey=True)
    if n_ds == 1:
        axes = [axes]
    for ax, name in zip(axes, DATASETS):
        sub = df[df["dataset"] == name]
        x = pd.to_numeric(sub["judge_reid_risk"], errors="coerce")
        y = pd.to_numeric(sub["judge_utility_score"], errors="coerce")
        verdict = sub["judge_verdict"].fillna("?")
        color_map = {"good": "#2ca02c", "acceptable": "#ff7f0e", "bad": "#d62728"}
        cs = verdict.map(color_map).fillna("gray")
        # jitter for visualization (these scores often cluster on grid points)
        rng = np.random.default_rng(0)
        jx = rng.normal(0, 0.012, size=len(x))
        jy = rng.normal(0, 0.012, size=len(y))
        ax.scatter(x + jx, y + jy, c=cs, s=14, alpha=0.65, edgecolors="none")

        # Highlight quadrants
        ax.axvline(0.5, color="gray", linestyle="--", linewidth=0.8)
        ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8)
        ax.set_title(f"{name} (n={len(sub)})")
        ax.set_xlabel("reid_risk")
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)
    axes[0].set_ylabel("utility_score")
    # legend
    handles = [
        plt.Line2D([0], [0], marker="o", color="w",
                   markerfacecolor="#2ca02c", label="good", markersize=7),
        plt.Line2D([0], [0], marker="o", color="w",
                   markerfacecolor="#ff7f0e", label="acceptable", markersize=7),
        plt.Line2D([0], [0], marker="o", color="w",
                   markerfacecolor="#d62728", label="bad", markersize=7),
    ]
    axes[-1].legend(handles=handles, loc="lower left", fontsize=8)
    fig.suptitle("Privacy-utility tradeoff (jittered)", y=1.02)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "05_tradeoff_scatter.png", dpi=140, bbox_inches="tight")
    plt.close(fig)

    # quadrant counts
    rows = []
    for name in ["ALL"] + DATASETS:
        sub = df if name == "ALL" else df[df["dataset"] == name]
        x = pd.to_numeric(sub["judge_reid_risk"], errors="coerce")
        y = pd.to_numeric(sub["judge_utility_score"], errors="coerce")
        m = x.notna() & y.notna()
        n = int(m.sum())
        # Q1: high util high risk; Q2: high util low risk (best);
        # Q3: low util low risk; Q4: low util high risk (worst).
        hu_hr = int(((y > 0.7) & (x > 0.5))[m].sum())
        hu_lr = int(((y > 0.7) & (x <= 0.5))[m].sum())
        lu_lr = int(((y <= 0.5) & (x <= 0.5))[m].sum())
        lu_hr = int(((y <= 0.5) & (x > 0.5))[m].sum())
        rows.append({
            "dataset": name, "n_scored": n,
            "high_util_high_risk": hu_hr,
            "high_util_high_risk_pct": round(100.0 * hu_hr / max(n, 1), 2),
            "high_util_low_risk_(ideal)": hu_lr,
            "high_util_low_risk_pct": round(100.0 * hu_lr / max(n, 1), 2),
            "low_util_low_risk": lu_lr,
            "low_util_low_risk_pct": round(100.0 * lu_lr / max(n, 1), 2),
            "low_util_high_risk_(worst)": lu_hr,
            "low_util_high_risk_pct": round(100.0 * lu_hr / max(n, 1), 2),
        })
    qtab = pd.DataFrame(rows)
    qtab.to_csv(OUT_DIR / "05_tradeoff_quadrants.csv", index=False)
    return {"quadrants": qtab}


# ---------------------------------------------------------------------------
# 6. Case studies
# ---------------------------------------------------------------------------
def truncate(s: str, n: int = 500) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[:n] + " ..."


def find_examples(df: pd.DataFrame, predicate, k: int = 3,
                  sort_by: Optional[str] = None,
                  ascending: bool = False) -> List[pd.Series]:
    mask = df["parsed"].apply(lambda p: predicate(p))
    sub = df[mask]
    if sort_by and sort_by in sub.columns:
        sub = sub.sort_values(sort_by, ascending=ascending)
    return [row for _, row in sub.head(k).iterrows()]


def has_priv_type(t: str):
    def _f(p):
        return t in issue_types(p, "privacy_issues")
    return _f


def has_util_type(t: str):
    def _f(p):
        return t in issue_types(p, "utility_issues")
    return _f


def case_studies(df: pd.DataFrame) -> str:
    sections: List[Tuple[str, List[pd.Series], str]] = []

    # 1) semantic_leak: high reid + this type
    sections.append((
        "Semantic privacy leaks",
        find_examples(df, has_priv_type("semantic_leak"), k=3,
                      sort_by="judge_reid_risk", ascending=False),
        "Paraphrased entities still expose the original sensitive content.",
    ))

    # 2) inferential_leak: highest reid
    sections.append((
        "Inferential privacy leaks",
        find_examples(df, has_priv_type("inferential_leak"), k=3,
                      sort_by="judge_reid_risk", ascending=False),
        "Combined or partial details still allow inferring identity.",
    ))

    # 3) over_generalization: lowest utility
    sections.append((
        "Over-generalization (utility loss)",
        find_examples(df, has_util_type("over_generalization"), k=3,
                      sort_by="judge_utility_score", ascending=True),
        "Rewrites became too vague and lost the constraints needed to answer.",
    ))

    # 4) task_drift
    sections.append((
        "Task drift",
        find_examples(df, has_util_type("task_drift"), k=3,
                      sort_by="judge_utility_score", ascending=True),
        "Rewrite changed what the user is actually asking for.",
    ))

    # 5) Severe utility collapse
    def _is_collapse(p: Optional[dict]) -> bool:
        if not isinstance(p, dict):
            return False
        u = p.get("utility_score")
        return isinstance(u, (int, float)) and float(u) <= 0.3
    sections.append((
        "Severe utility collapse (utility_score <= 0.3)",
        find_examples(df, _is_collapse, k=3,
                      sort_by="judge_utility_score", ascending=True),
        "Rewrite is essentially unusable for the original task.",
    ))

    md = ["# Case studies\n"]
    for title, rows, note in sections:
        md.append(f"## {title}\n")
        md.append(f"_{note}_\n")
        if not rows:
            md.append("(no matching examples found)\n")
            continue
        for i, r in enumerate(rows, 1):
            p = r["parsed"] or {}
            priv_issues = _safe_list(p, "privacy_issues")
            util_issues = _safe_list(p, "utility_issues")
            md.append(f"### Example {i} — dataset=`{r['dataset']}` "
                      f"verdict=`{r['judge_verdict']}` "
                      f"reid_risk={r['judge_reid_risk']} "
                      f"utility={r['judge_utility_score']}\n")
            md.append(f"- **question**: {truncate(r['question'], 600)}")
            md.append(f"- **priv_query**: {truncate(r['priv_query'], 600)}")
            if priv_issues:
                md.append("- **privacy_issues**:")
                for it in priv_issues[:5]:
                    md.append(f"    - `{it.get('type')}` "
                              f"span=`{truncate(str(it.get('span') or ''), 120)}` "
                              f"reason: {truncate(str(it.get('reason') or ''), 200)}")
            if util_issues:
                md.append("- **utility_issues**:")
                for it in util_issues[:5]:
                    md.append(f"    - `{it.get('type')}` "
                              f"span=`{truncate(str(it.get('span') or ''), 120)}` "
                              f"reason: {truncate(str(it.get('reason') or ''), 200)}")
            new_sens = _safe_list(p, "new_sensitive")
            if new_sens:
                md.append("- **new_sensitive**:")
                for it in new_sens[:3]:
                    md.append(f"    - span=`{truncate(str(it.get('span') or ''), 120)}` "
                              f"reason: {truncate(str(it.get('reason') or ''), 200)}")
            md.append("")
    out = "\n".join(md)
    (OUT_DIR / "06_case_studies.md").write_text(out, encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# 7. Failure pattern analysis
# ---------------------------------------------------------------------------
def failure_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Map abstract failure patterns onto concrete issue types and report rates."""
    n = len(df)
    patterns = {
        "preserving overly specific descriptors":
            lambda p: ("direct_leak" in issue_types(p, "privacy_issues")
                       or "semantic_leak" in issue_types(p, "privacy_issues")),
        "still-identifiable paraphrases (semantic leak)":
            lambda p: "semantic_leak" in issue_types(p, "privacy_issues"),
        "inferable from retained clues (inferential / combination)":
            lambda p: ("inferential_leak" in issue_types(p, "privacy_issues")
                       or "combination_leak" in issue_types(p, "privacy_issues")),
        "excessive abstraction causing intent loss":
            lambda p: ("over_generalization" in issue_types(p, "utility_issues")
                       or "lost_constraint" in issue_types(p, "utility_issues")),
        "introducing unrelated sensitive attributes":
            lambda p: len(_safe_list(p, "new_sensitive")) > 0,
        "task drift / wrong task":
            lambda p: "task_drift" in issue_types(p, "utility_issues"),
        "weakened-but-not-lost constraint":
            lambda p: "weakened_constraint" in issue_types(p, "utility_issues"),
        "added unnecessary constraint":
            lambda p: "added_constraint" in issue_types(p, "utility_issues"),
    }

    rows = []
    for name in ["ALL"] + DATASETS:
        sub = df if name == "ALL" else df[df["dataset"] == name]
        nn = len(sub)
        row = {"dataset": name, "n_samples": nn}
        for label, pred in patterns.items():
            c = int(sub["parsed"].apply(pred).sum())
            row[label] = c
            row[f"{label} %"] = round(100.0 * c / max(nn, 1), 2)
        rows.append(row)
    tab = pd.DataFrame(rows)
    tab.to_csv(OUT_DIR / "07_failure_patterns.csv", index=False)

    # Visualization (ALL only)
    all_row = tab[tab["dataset"] == "ALL"].iloc[0]
    labels = list(patterns.keys())
    vals = [all_row[f"{l} %"] for l in labels]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.barh(labels, vals, color="#c0504d")
    ax.set_xlabel("samples affected (%)")
    ax.set_title("Failure pattern prevalence (ALL)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "07_failure_patterns.png", dpi=140)
    plt.close(fig)

    return tab


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------
def write_findings(df: pd.DataFrame,
                   overall: Dict[str, Any],
                   privacy: Dict[str, Any],
                   utility: Dict[str, Any],
                   newsens: Dict[str, Any],
                   tradeoff: Dict[str, Any],
                   patterns: pd.DataFrame) -> None:
    overall_tbl = overall["table"]
    all_row = overall_tbl[overall_tbl["dataset"] == "ALL"].iloc[0]
    by_ds = {n: overall_tbl[overall_tbl["dataset"] == n].iloc[0] for n in DATASETS}

    pri_tbl = privacy["table"]
    pri_all = pri_tbl[pri_tbl["dataset"] == "ALL"].iloc[0]
    util_tbl = utility["table"]
    util_all = util_tbl[util_tbl["dataset"] == "ALL"].iloc[0]
    quads = tradeoff["quadrants"]
    quads_all = quads[quads["dataset"] == "ALL"].iloc[0]

    lines: List[str] = []
    lines.append("# Privacy-rewrite evaluator: findings\n")
    per_ds_counts = ", ".join(f"{n}={int(by_ds[n]['n'])}" for n in DATASETS)
    lines.append(f"- Total samples scored: **{int(all_row['n'])}** "
                 f"({per_ds_counts})\n")

    lines.append("## 1. Overall verdict and scores\n")
    lines.append(
        f"- Verdict mix (ALL): "
        f"good {all_row['verdict_good_pct']}%, "
        f"acceptable {all_row['verdict_acceptable_pct']}%, "
        f"bad {all_row['verdict_bad_pct']}%.")
    lines.append(
        f"- Mean reid_risk: **{all_row['judge_reid_risk_mean']}** "
        f"(median {all_row['judge_reid_risk_median']}, "
        f"std {all_row['judge_reid_risk_std']}).")
    lines.append(
        f"- Mean utility_score: **{all_row['judge_utility_score_mean']}** "
        f"(median {all_row['judge_utility_score_median']}, "
        f"std {all_row['judge_utility_score_std']}).")
    lines.append(
        f"- Pearson(reid, utility) = **{all_row['pearson_reid_vs_util']}**, "
        f"Spearman = **{all_row['spearman_reid_vs_util']}**.")
    lines.append("- Per-dataset verdict breakdown:")
    for n in DATASETS:
        r = by_ds[n]
        lines.append(
            f"    - **{n}**: good {r['verdict_good_pct']}%, "
            f"acceptable {r['verdict_acceptable_pct']}%, "
            f"bad {r['verdict_bad_pct']}%; "
            f"reid mean={r['judge_reid_risk_mean']}, "
            f"util mean={r['judge_utility_score_mean']}.")
    lines.append("")

    lines.append("## 2. Privacy issues (ALL)\n")
    lines.append(
        f"- Samples with at least one privacy issue: **{pri_all['any_issue_pct']}%**, "
        f"with multiple distinct privacy issues: **{pri_all['multi_issue_pct']}%**.")
    for t in PRIVACY_TYPES:
        lines.append(
            f"    - `{t}`: in **{pri_all[f'{t}_sample_pct']}%** of samples "
            f"({int(pri_all[t])} instances).")
    lines.append("- Mean reid_risk by privacy issue type: see "
                 "`02_privacy_issue_reid_risk.csv`.")
    lines.append("")

    lines.append("## 3. Utility issues (ALL)\n")
    lines.append(
        f"- Samples with at least one utility issue: **{util_all['any_issue_pct']}%**, "
        f"with multiple distinct utility issues: **{util_all['multi_issue_pct']}%**.")
    for t in UTILITY_TYPES:
        lines.append(
            f"    - `{t}`: in **{util_all[f'{t}_sample_pct']}%** of samples "
            f"({int(util_all[t])} instances).")
    lines.append("- Mean utility_score by utility issue type: see "
                 "`03_utility_issue_utility_score.csv`.")
    lines.append("")

    lines.append("## 4. New sensitive attributes\n")
    s = newsens["summary"]
    lines.append(
        f"- Samples introducing new sensitive details: "
        f"**{s['n_samples_with_new_sensitive']}** "
        f"({s['pct_samples_with_new_sensitive']}%).")
    lines.append(f"- Total new_sensitive items: **{s['total_new_sensitive_items']}**.")
    if s["categories"]:
        lines.append("- Top categories (by item count):")
        for cat, cnt in s["categories"][:6]:
            lines.append(f"    - {cat}: {cnt}")
    lines.append("")

    lines.append("## 5. Privacy-utility tradeoff\n")
    lines.append(
        f"- High-utility & low-risk (ideal, util>0.7 & risk<=0.5): "
        f"**{quads_all['high_util_low_risk_pct']}%**.")
    lines.append(
        f"- High-utility & high-risk: "
        f"**{quads_all['high_util_high_risk_pct']}%**.")
    lines.append(
        f"- Low-utility & high-risk (worst case): "
        f"**{quads_all['low_util_high_risk_pct']}%**.")
    lines.append(
        f"- Low-utility & low-risk: "
        f"**{quads_all['low_util_low_risk_pct']}%**.")
    lines.append("")

    lines.append("## 6. Failure patterns (ALL)\n")
    p_all = patterns[patterns["dataset"] == "ALL"].iloc[0]
    pattern_keys = [c for c in patterns.columns
                    if c not in ("dataset", "n_samples") and not c.endswith(" %")]
    pairs = sorted(
        [(k, p_all[f"{k} %"]) for k in pattern_keys],
        key=lambda x: -x[1],
    )
    for k, v in pairs:
        lines.append(f"- {k}: **{v}%**")
    lines.append("")

    lines.append("## 7. Headline takeaways\n")
    # Build qualitative takeaways
    takeaways: List[str] = []

    # which dataset is best / worst?
    best = max(DATASETS, key=lambda n: by_ds[n]["verdict_good_pct"])
    worst = max(DATASETS, key=lambda n: by_ds[n]["verdict_bad_pct"])
    takeaways.append(
        f"`{best}` has the highest rate of `good` verdicts "
        f"({by_ds[best]['verdict_good_pct']}%), while `{worst}` has the most "
        f"`bad` verdicts ({by_ds[worst]['verdict_bad_pct']}%).")

    # tradeoff sign
    rho = all_row["pearson_reid_vs_util"]
    if not (isinstance(rho, float) and math.isnan(rho)):
        if rho > 0.1:
            takeaways.append(
                "reid_risk and utility_score are positively correlated "
                f"(Pearson={rho}) — keeping more useful detail also keeps "
                "more identifying detail, the classic tradeoff.")
        elif rho < -0.1:
            takeaways.append(
                "reid_risk and utility_score are negatively correlated "
                f"(Pearson={rho}) — heavier anonymization helps privacy but "
                "hurts utility.")
        else:
            takeaways.append(
                "reid_risk and utility_score are only weakly correlated "
                f"(Pearson={rho}) — leakage and utility loss are largely "
                "independent failure modes.")

    # dominant privacy failure
    pri_rank = sorted(
        [(t, pri_all[f"{t}_sample_pct"]) for t in PRIVACY_TYPES],
        key=lambda x: -x[1],
    )
    takeaways.append(
        f"Dominant privacy failure mode: `{pri_rank[0][0]}` "
        f"({pri_rank[0][1]}% of samples), followed by "
        f"`{pri_rank[1][0]}` ({pri_rank[1][1]}%).")

    # dominant utility failure
    util_rank = sorted(
        [(t, util_all[f"{t}_sample_pct"]) for t in UTILITY_TYPES],
        key=lambda x: -x[1],
    )
    takeaways.append(
        f"Dominant utility failure mode: `{util_rank[0][0]}` "
        f"({util_rank[0][1]}% of samples), followed by "
        f"`{util_rank[1][0]}` ({util_rank[1][1]}%).")

    if s["pct_samples_with_new_sensitive"] >= 5:
        takeaways.append(
            f"Hallucinated/new sensitive details appear in "
            f"{s['pct_samples_with_new_sensitive']}% of rewrites — non-trivial "
            "and worth fixing in prompts.")

    for t in takeaways:
        lines.append(f"- {t}")

    (OUT_DIR / "findings.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print(f"[info] reading from {RESULTS_DIR}")
    df = load_all()
    print(f"[info] total rows: {len(df)}")

    overall = overall_stats(df)
    privacy = privacy_analysis(df)
    utility = utility_analysis(df)
    newsens = new_sensitive_analysis(df)
    tradeoff = tradeoff_scatter(df)
    patterns = failure_patterns(df)
    case_studies(df)
    write_findings(df, overall, privacy, utility, newsens, tradeoff, patterns)

    print(f"[done] outputs written to: {OUT_DIR}")
    for p in sorted(OUT_DIR.iterdir()):
        print(" -", p.name)


if __name__ == "__main__":
    main()
