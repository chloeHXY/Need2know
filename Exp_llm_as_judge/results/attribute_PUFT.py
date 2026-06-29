# -*- coding: utf-8 -*-
"""
PUFT root-cause attribution analysis.

Compared to other rewriters, PUFT has the worst verdict mix
(good 19.0%, bad 62.8%) and a uniquely low utility_score (mean=0.50).
Privacy is actually fine (mean reid_risk=0.047, similar to papillon).
=> PUFT fails on the *utility* side, not the privacy side.

This script digs into:
  1. Length / compression statistics (original question vs priv_query).
  2. Per-issue counts and the most common `lost_constraint` reasons / spans.
  3. Correlation between rewrite length and utility/verdict.
  4. Sample exemplars: cases where PUFT collapsed utility to near zero.
  5. Comparison summary between PUFT and the other three systems.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RESULTS_DIR = Path(
    "/group/40047/eiraxyhuang/workspace/fc/DataG/Exp_llm_as_judge/results"
)
OUT_DIR = RESULTS_DIR / "analysis" / "PUFT"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DATASETS = ["our", "papillon", "prediax", "PUFT"]


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


def _safe_list(parsed: Optional[dict], key: str) -> List[dict]:
    if not isinstance(parsed, dict):
        return []
    v = parsed.get(key)
    if not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, dict)]


# ---------------------------------------------------------------------------
# 1. Length / compression statistics
# ---------------------------------------------------------------------------
WORD_RE = re.compile(r"\w+", re.UNICODE)


def n_words(s: str) -> int:
    if not s:
        return 0
    return len(WORD_RE.findall(s))


def length_stats(all_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in DATASETS:
        sub = all_df[all_df["dataset"] == name]
        q_chars = sub["question"].astype(str).str.len()
        q_words = sub["question"].astype(str).map(n_words)
        r_chars = sub["priv_query"].astype(str).str.len()
        r_words = sub["priv_query"].astype(str).map(n_words)
        ratio_c = (r_chars / q_chars.replace(0, np.nan)).dropna()
        ratio_w = (r_words / q_words.replace(0, np.nan)).dropna()
        rows.append({
            "dataset": name,
            "n": len(sub),
            "q_chars_mean": round(float(q_chars.mean()), 2),
            "q_words_mean": round(float(q_words.mean()), 2),
            "rewrite_chars_mean": round(float(r_chars.mean()), 2),
            "rewrite_words_mean": round(float(r_words.mean()), 2),
            "char_ratio_mean": round(float(ratio_c.mean()), 3),
            "char_ratio_median": round(float(ratio_c.median()), 3),
            "word_ratio_mean": round(float(ratio_w.mean()), 3),
            "word_ratio_median": round(float(ratio_w.median()), 3),
            "rewrites_shorter_than_50pct": int((ratio_w < 0.5).sum()),
            "rewrites_shorter_than_30pct": int((ratio_w < 0.3).sum()),
        })
    tab = pd.DataFrame(rows)
    tab.to_csv(OUT_DIR / "len_stats.csv", index=False)
    return tab


# ---------------------------------------------------------------------------
# 2. Lost-constraint span / reason mining for PUFT
# ---------------------------------------------------------------------------
STOPWORDS = set("""
a an the of in on at to for from by with and or but if then so as is are was were be been being
this that these those it its their there here which who whom whose what when where why how
i you we they me him her us them my your our his hers ours theirs do does did done
not no yes very more most less least also any all some each every other another such same
""".split())


def normalize_token(t: str) -> str:
    t = t.lower().strip()
    t = re.sub(r"[^\w\s\-/]", "", t)
    return t


def topk_tokens(strs: List[str], k: int = 30, min_len: int = 3) -> List:
    cnt = Counter()
    for s in strs:
        for w in WORD_RE.findall(str(s).lower()):
            if len(w) < min_len or w in STOPWORDS:
                continue
            cnt[w] += 1
    return cnt.most_common(k)


def lost_constraint_mining(all_df: pd.DataFrame) -> Dict[str, Any]:
    spans_by_ds: Dict[str, List[str]] = {n: [] for n in DATASETS}
    reasons_by_ds: Dict[str, List[str]] = {n: [] for n in DATASETS}
    n_lost_per_row: Dict[str, List[int]] = {n: [] for n in DATASETS}

    for _, r in all_df.iterrows():
        ds = r["dataset"]
        items = _safe_list(r["parsed"], "utility_issues")
        n_lost = 0
        for it in items:
            t = str(it.get("type") or "").strip().lower()
            if t == "lost_constraint":
                n_lost += 1
                spans_by_ds[ds].append(str(it.get("span") or ""))
                reasons_by_ds[ds].append(str(it.get("reason") or ""))
        n_lost_per_row[ds].append(n_lost)

    rows = []
    for n in DATASETS:
        arr = np.array(n_lost_per_row[n])
        rows.append({
            "dataset": n,
            "samples": len(arr),
            "samples_with_lost_constraint": int((arr > 0).sum()),
            "samples_with_lost_constraint_pct": round(
                100.0 * (arr > 0).mean(), 2),
            "total_lost_constraint_instances": int(arr.sum()),
            "mean_lost_per_sample": round(float(arr.mean()), 3),
            "max_lost_per_sample": int(arr.max() if len(arr) else 0),
        })
    counts_tab = pd.DataFrame(rows)
    counts_tab.to_csv(OUT_DIR / "lost_constraint_counts.csv", index=False)

    # distribution of n_lost_per_row for PUFT
    fig, ax = plt.subplots(figsize=(7, 4))
    for n in DATASETS:
        arr = np.array(n_lost_per_row[n])
        bins = np.arange(0, max(arr.max() + 2, 8))
        ax.hist(arr, bins=bins, alpha=0.45, label=n)
    ax.set_xlabel("number of lost_constraint instances per sample")
    ax.set_ylabel("count")
    ax.set_title("Per-sample count of lost_constraint")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "lost_constraint_per_sample.png", dpi=140)
    plt.close(fig)

    # token frequencies of dropped spans (PUFT vs others)
    puft_top = topk_tokens(spans_by_ds["PUFT"], k=40)
    others = [s for n in DATASETS if n != "PUFT" for s in spans_by_ds[n]]
    others_top = topk_tokens(others, k=40)

    pd.DataFrame(puft_top, columns=["token", "count"]).to_csv(
        OUT_DIR / "lost_span_tokens_PUFT.csv", index=False)
    pd.DataFrame(others_top, columns=["token", "count"]).to_csv(
        OUT_DIR / "lost_span_tokens_others.csv", index=False)

    # top reasons (raw, just first 80 chars after lower-casing) — quick clustering
    def cluster_reason(s: str) -> str:
        s = s.lower()
        # naive: keep first 6 informative tokens after stopword removal
        toks = [w for w in WORD_RE.findall(s)
                if w not in STOPWORDS and len(w) > 2]
        return " ".join(toks[:6])

    puft_reason_counter = Counter(cluster_reason(s) for s in reasons_by_ds["PUFT"])
    pd.DataFrame(puft_reason_counter.most_common(40),
                 columns=["reason_prefix", "count"]).to_csv(
        OUT_DIR / "lost_reason_clusters_PUFT.csv", index=False)

    return {
        "counts_tab": counts_tab,
        "puft_top_tokens": puft_top,
        "others_top_tokens": others_top,
        "puft_reason_top": puft_reason_counter.most_common(20),
    }


# ---------------------------------------------------------------------------
# 3. Length vs utility correlation
# ---------------------------------------------------------------------------
def length_vs_utility(all_df: pd.DataFrame) -> Dict[str, Any]:
    rows = []
    for n in DATASETS:
        sub = all_df[all_df["dataset"] == n].copy()
        sub["q_words"] = sub["question"].astype(str).map(n_words)
        sub["r_words"] = sub["priv_query"].astype(str).map(n_words)
        sub["word_ratio"] = sub["r_words"] / sub["q_words"].replace(0, np.nan)
        sub["util"] = pd.to_numeric(sub["judge_utility_score"], errors="coerce")
        sub["risk"] = pd.to_numeric(sub["judge_reid_risk"], errors="coerce")

        m = sub["word_ratio"].notna() & sub["util"].notna()
        if m.sum() >= 3:
            corr_p_util = float(np.corrcoef(sub.loc[m, "word_ratio"],
                                            sub.loc[m, "util"])[0, 1])
        else:
            corr_p_util = float("nan")
        m2 = sub["word_ratio"].notna() & sub["risk"].notna()
        if m2.sum() >= 3:
            corr_p_risk = float(np.corrcoef(sub.loc[m2, "word_ratio"],
                                            sub.loc[m2, "risk"])[0, 1])
        else:
            corr_p_risk = float("nan")

        # bucket by word_ratio
        bins = [0, 0.3, 0.5, 0.8, 1.0, np.inf]
        labels = ["<0.3", "0.3-0.5", "0.5-0.8", "0.8-1.0", ">=1.0"]
        sub["bucket"] = pd.cut(sub["word_ratio"], bins=bins, labels=labels)
        bucket_tab = sub.groupby("bucket", observed=True).agg(
            n=("util", "count"),
            mean_util=("util", "mean"),
            mean_risk=("risk", "mean"),
            bad_pct=("judge_verdict",
                     lambda s: round(100.0 * (s == "bad").mean(), 2)),
        ).reset_index()
        bucket_tab["dataset"] = n
        rows.append({
            "dataset": n,
            "pearson_word_ratio_vs_util": round(corr_p_util, 4),
            "pearson_word_ratio_vs_risk": round(corr_p_risk, 4),
        })
        bucket_tab.to_csv(OUT_DIR / f"length_buckets_{n}.csv", index=False)

    pd.DataFrame(rows).to_csv(OUT_DIR / "length_corr.csv", index=False)

    # plot scatter for PUFT
    sub = all_df[all_df["dataset"] == "PUFT"].copy()
    sub["q_words"] = sub["question"].astype(str).map(n_words)
    sub["r_words"] = sub["priv_query"].astype(str).map(n_words)
    sub["word_ratio"] = sub["r_words"] / sub["q_words"].replace(0, np.nan)
    sub["util"] = pd.to_numeric(sub["judge_utility_score"], errors="coerce")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.scatter(sub["word_ratio"], sub["util"], s=14, alpha=0.45,
               color="#d62728")
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8)
    ax.axvline(1.0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_xlabel("rewrite_length / original_length (in words)")
    ax.set_ylabel("utility_score")
    ax.set_title("PUFT: rewrite length ratio vs utility")
    ax.set_xlim(0, max(2.5, float(sub["word_ratio"].quantile(0.99))))
    fig.tight_layout()
    fig.savefig(OUT_DIR / "PUFT_len_vs_util.png", dpi=140)
    plt.close(fig)

    return {"rows": rows}


# ---------------------------------------------------------------------------
# 4. Sample exemplars (severe collapse)
# ---------------------------------------------------------------------------
def truncate(s: str, n: int = 600) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[:n] + " ..."


def case_studies(all_df: pd.DataFrame) -> None:
    sub = all_df[all_df["dataset"] == "PUFT"].copy()
    sub["util"] = pd.to_numeric(sub["judge_utility_score"], errors="coerce")
    # select severe collapse with good privacy: util<=0.3 and reid_risk<=0.2
    sub["risk"] = pd.to_numeric(sub["judge_reid_risk"], errors="coerce")
    collapse = sub[(sub["util"] <= 0.3) & (sub["risk"] <= 0.2)].sort_values("util")

    md = ["# PUFT case studies — utility collapse with low privacy risk\n",
          f"_total such cases: {len(collapse)}_\n"]
    for i, (_, r) in enumerate(collapse.head(10).iterrows(), 1):
        p = r["parsed"] or {}
        priv_issues = _safe_list(p, "privacy_issues")
        util_issues = _safe_list(p, "utility_issues")
        md.append(f"## Case {i} — verdict=`{r['judge_verdict']}` "
                  f"util={r['judge_utility_score']} risk={r['judge_reid_risk']}\n")
        md.append(f"- **question** ({n_words(r['question'])}w): "
                  f"{truncate(r['question'], 700)}")
        md.append(f"- **priv_query** ({n_words(r['priv_query'])}w): "
                  f"{truncate(str(r['priv_query']), 700)}")
        if util_issues:
            md.append("- **utility_issues**:")
            for it in util_issues[:6]:
                md.append(f"    - `{it.get('type')}` "
                          f"span=`{truncate(str(it.get('span') or ''), 150)}` "
                          f"reason: {truncate(str(it.get('reason') or ''), 220)}")
        if priv_issues:
            md.append("- **privacy_issues**:")
            for it in priv_issues[:3]:
                md.append(f"    - `{it.get('type')}` "
                          f"span=`{truncate(str(it.get('span') or ''), 150)}` "
                          f"reason: {truncate(str(it.get('reason') or ''), 220)}")
        md.append("")

    (OUT_DIR / "PUFT_collapse_cases.md").write_text("\n".join(md), encoding="utf-8")

    # Also: best PUFT cases (good verdict)
    good = sub[sub["judge_verdict"] == "good"].sort_values(
        "util", ascending=False).head(5)
    md2 = ["# PUFT — examples of `good` verdicts\n"]
    for i, (_, r) in enumerate(good.iterrows(), 1):
        md2.append(f"## Case {i} — util={r['judge_utility_score']} "
                   f"risk={r['judge_reid_risk']}\n")
        md2.append(f"- **question** ({n_words(r['question'])}w): "
                   f"{truncate(r['question'], 700)}")
        md2.append(f"- **priv_query** ({n_words(r['priv_query'])}w): "
                   f"{truncate(str(r['priv_query']), 700)}\n")
    (OUT_DIR / "PUFT_good_cases.md").write_text("\n".join(md2), encoding="utf-8")


# ---------------------------------------------------------------------------
# 5. Verdict-conditioned summary
# ---------------------------------------------------------------------------
def puft_summary(all_df: pd.DataFrame) -> pd.DataFrame:
    sub = all_df[all_df["dataset"] == "PUFT"].copy()
    sub["util"] = pd.to_numeric(sub["judge_utility_score"], errors="coerce")
    sub["risk"] = pd.to_numeric(sub["judge_reid_risk"], errors="coerce")
    sub["q_words"] = sub["question"].astype(str).map(n_words)
    sub["r_words"] = sub["priv_query"].astype(str).map(n_words)
    sub["word_ratio"] = sub["r_words"] / sub["q_words"].replace(0, np.nan)

    def n_issues(p, key):
        return len(_safe_list(p, key))

    sub["n_priv"] = sub["parsed"].apply(lambda p: n_issues(p, "privacy_issues"))
    sub["n_util"] = sub["parsed"].apply(lambda p: n_issues(p, "utility_issues"))

    grp = sub.groupby("judge_verdict").agg(
        n=("util", "count"),
        mean_util=("util", "mean"),
        mean_risk=("risk", "mean"),
        mean_word_ratio=("word_ratio", "mean"),
        median_word_ratio=("word_ratio", "median"),
        mean_q_words=("q_words", "mean"),
        mean_r_words=("r_words", "mean"),
        mean_n_priv_issues=("n_priv", "mean"),
        mean_n_util_issues=("n_util", "mean"),
    ).round(3).reset_index()
    grp.to_csv(OUT_DIR / "PUFT_by_verdict.csv", index=False)
    return grp


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    all_df = pd.concat([load_one(n) for n in DATASETS], ignore_index=True)
    print(f"[info] loaded total rows: {len(all_df)}")

    print("[step 1] length statistics ...")
    len_tab = length_stats(all_df)
    print(len_tab.to_string(index=False))

    print("\n[step 2] lost_constraint mining ...")
    lc = lost_constraint_mining(all_df)
    print(lc["counts_tab"].to_string(index=False))
    print("\nPUFT top dropped span tokens (top 20):")
    for tok, c in lc["puft_top_tokens"][:20]:
        print(f"  {tok}: {c}")
    print("\nPUFT top reason clusters (top 10):")
    for r, c in lc["puft_reason_top"][:10]:
        print(f"  [{c}] {r}")

    print("\n[step 3] length vs utility correlation ...")
    length_vs_utility(all_df)

    print("[step 4] case studies ...")
    case_studies(all_df)

    print("[step 5] PUFT summary by verdict ...")
    grp = puft_summary(all_df)
    print(grp.to_string(index=False))

    print(f"\n[done] outputs written to: {OUT_DIR}")
    for p in sorted(OUT_DIR.iterdir()):
        print(" -", p.name)


if __name__ == "__main__":
    main()
