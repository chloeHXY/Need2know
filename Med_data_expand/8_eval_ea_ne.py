"""
Input parquet : /group/40047/eiraxyhuang/workspace/fc/DataG/wild/wild_with_priv_query.parquet
Goal          : measure how `priv_query` performs against the rewriter's two
                training-time signals stored in `extra_info`:

    extra_info["ne"]  -- non-essential items. These MUST NOT appear in
                         priv_query. Any leak counts as a privacy violation.
    extra_info["ea"]  -- essential items. These SHOULD still be expressed in
                         priv_query (utility retention).

This script intentionally ignores `question_pii_entities`; the only ground
truth used here are `ea` and `ne` from `extra_info`.

Leak / retention is judged with the same primitives used at training time
(`/group/40047/eiraxyhuang/workspace/fc/DataG/z_eval/eval_privacy/com_privacy_score.py`):
combining Jaccard-style coverage and BERTScore rescaled precision.

Reported metrics
----------------
- Sample-level leak rate     : fraction of samples with >=1 ne item leaked.
- ne item leak rate          : leaked ne items / total ne items.
- ea item retention rate     : retained ea items / total ea items.

新增了"无泄漏子集"的输出
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import pandas as pd
from tqdm import tqdm

# Reuse the exact reward-side primitives so leak detection is aligned with
# training-time reward (com_privacy_score.compute_score).
sys.path.insert(
    0,
    "/group/40047/eiraxyhuang/workspace/fc/DataG/z_eval/eval_privacy",
)
from com_privacy_score import (  # noqa: E402
    coverage,
    _bert_p_rescaled,
    _to_str_list,
    _get_bert_scorer,
)


# ---------------------------------------------------------------------------
# Defaults / thresholds
# ---------------------------------------------------------------------------
DEFAULT_INPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/Med_data_expand/med_with_priv_query.parquet"
)
DEFAULT_OUTPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/Med_data_expand/tem.parquet"
)
DEFAULT_NOLEAK_OUTPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/Med_data_expand/tem.parquet"
)

# Same thresholds as com_privacy_score.compute_score / training-time reward.
# `ne` leak: cov >= 1.0 (literal/lexical) OR BERTScore P_rs > 0.3 (semantic).
NE_COV_THRESHOLD = 1.0
NE_BERT_THRESHOLD = 0.3

# `ea` retention (utility branch): cov >= 0.5 OR BERTScore P_rs > 0.3.
EA_COV_THRESHOLD = 0.5
EA_BERT_THRESHOLD = 0.3

PRIV_QUERY_COL = "priv_query"
EXTRA_INFO_COL = "extra_info"


# ---------------------------------------------------------------------------
# extra_info helpers
# ---------------------------------------------------------------------------
def _get(extra_info: Any, key: str, default: Any = None) -> Any:
    if extra_info is None:
        return default
    if isinstance(extra_info, dict):
        return extra_info.get(key, default)
    try:
        return extra_info[key]
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Leak / retention detection
# ---------------------------------------------------------------------------
def _detect_ne_leaks(
    items: list[str],
    priv_query: str,
    use_bert: bool,
) -> tuple[list[bool], list[float], list[float | None]]:
    """For each ne item C, decide whether C is leaked into priv_query.

    Leak criterion (mirrors training reward):
        cov(priv_query, C) >= 1.0  OR  BERTScore P_rs(C, priv_query) > 0.3.
    """
    n = len(items)
    if n == 0 or not priv_query:
        return [False] * n, [0.0] * n, [None] * n

    cov_list = [coverage(priv_query, c) for c in items]
    cov_flags = [c >= NE_COV_THRESHOLD for c in cov_list]

    bert_list: list[float | None] = [None] * n
    bert_flags = [False] * n
    if use_bert:
        scores = _bert_p_rescaled(items, priv_query)
        if scores is not None:
            bert_list = [float(s) for s in scores]
            bert_flags = [s > NE_BERT_THRESHOLD for s in scores]

    leak_flags = [a or b for a, b in zip(cov_flags, bert_flags)]
    return leak_flags, cov_list, bert_list


def _detect_ea_hits(
    items: list[str],
    priv_query: str,
    use_bert: bool,
) -> tuple[list[bool], list[float], list[float | None]]:
    """For each ea item E, decide whether E is retained in priv_query.

    Retention criterion (mirrors training reward utility branch):
        cov(priv_query, E) >= 0.5  OR  BERTScore P_rs(E, priv_query) > 0.3.
    """
    n = len(items)
    if n == 0 or not priv_query:
        return [False] * n, [0.0] * n, [None] * n

    cov_list = [coverage(priv_query, e) for e in items]
    cov_flags = [c >= EA_COV_THRESHOLD for c in cov_list]

    bert_list: list[float | None] = [None] * n
    bert_flags = [False] * n
    if use_bert:
        scores = _bert_p_rescaled(items, priv_query)
        if scores is not None:
            bert_list = [float(s) for s in scores]
            bert_flags = [s > EA_BERT_THRESHOLD for s in scores]

    hit_flags = [a or b for a, b in zip(cov_flags, bert_flags)]
    return hit_flags, cov_list, bert_list


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate priv_query vs extra_info['ne'] (leak) and "
            "extra_info['ea'] (retention). Ignores question_pii_entities."
        )
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--noleak_output", default=DEFAULT_NOLEAK_OUTPUT,
        help="Where to save rows with n_ne_leak == 0 (set '' to skip).",
    )
    parser.add_argument(
        "--no_bert", action="store_true",
        help="Disable BERTScore (only Jaccard-based detection).",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Only score the first N rows (0 = all).",
    )
    args = parser.parse_args()

    print(f"[load] reading parquet: {args.input}")
    df = pd.read_parquet(args.input)
    print(f"[load] rows={len(df)} cols={df.columns.tolist()}")

    for col in (PRIV_QUERY_COL, EXTRA_INFO_COL):
        if col not in df.columns:
            raise KeyError(f"input parquet missing required column: {col}")

    n = len(df)
    if args.limit and args.limit < n:
        df = df.iloc[: args.limit].copy()
        n = len(df)
    print(f"[plan] scoring {n} rows")

    # Warm up BERTScorer once so per-row calls are cheap and we fail loud
    # early if it's unavailable.
    use_bert = not args.no_bert
    if use_bert:
        scorer = _get_bert_scorer()
        if scorer is None:
            print("[warn] BERTScorer unavailable -> falling back to Jaccard only")
            use_bert = False

    rows: list[dict[str, Any]] = []

    # Aggregates across the whole dataset.
    ne_total = 0
    ne_leaked = 0
    ea_total = 0
    ea_hit = 0
    sample_leaked = 0
    sample_with_ne = 0  # samples that have at least 1 ne item

    for i in tqdm(range(n), desc="scoring"):
        r = df.iloc[i]
        priv_q = r[PRIV_QUERY_COL] if isinstance(r[PRIV_QUERY_COL], str) else ""
        ei = r[EXTRA_INFO_COL]
        question = _get(ei, "question", "") or ""
        ne_list = _to_str_list(_get(ei, "ne"))
        ea_list = _to_str_list(_get(ei, "key_spans"))

        ne_flags, ne_cov, ne_bert = _detect_ne_leaks(ne_list, priv_q, use_bert)
        ea_flags, ea_cov, ea_bert = _detect_ea_hits(ea_list, priv_q, use_bert)

        n_ne = len(ne_list)
        n_ea = len(ea_list)
        n_ne_leak = sum(ne_flags)
        n_ea_hit = sum(ea_flags)

        sample_leak = n_ne_leak > 0

        ne_total += n_ne
        ne_leaked += n_ne_leak
        ea_total += n_ea
        ea_hit += n_ea_hit
        if n_ne > 0:
            sample_with_ne += 1
            if sample_leak:
                sample_leaked += 1

        rows.append({
            "index": int(_get(ei, "index", i) or i),
            "question": question,
            "priv_query": priv_q,
            "ne_items": ne_list,
            "ne_leak_flags": ne_flags,
            "ne_coverage": ne_cov,
            "ne_bert_p": ne_bert,
            "n_ne": n_ne,
            "n_ne_leak": n_ne_leak,
            "ea_items": ea_list,
            "ea_hit_flags": ea_flags,
            "ea_coverage": ea_cov,
            "ea_bert_p": ea_bert,
            "n_ea": n_ea,
            "n_ea_hit": n_ea_hit,
            "sample_leak": sample_leak,
        })

    # ------------------------- aggregate metrics -------------------------
    sample_rate_full = sample_leaked / n if n else 0.0
    sample_rate_eligible = (
        sample_leaked / sample_with_ne if sample_with_ne else 0.0
    )
    ne_rate = ne_leaked / ne_total if ne_total else 0.0
    ea_retention = ea_hit / ea_total if ea_total else 0.0

    print("\n=== ea / ne evaluation (question_pii_entities ignored) ===")
    print(f"  total samples                     : {n}")
    print(f"  samples with >=1 ne item          : {sample_with_ne}")
    print(f"  leaked samples                    : {sample_leaked}")
    print(
        f"  sample-level leak rate (full)     : {sample_rate_full:.4f}"
        f"  ({sample_leaked}/{n})"
    )
    print(
        f"  sample-level leak rate (eligible) : {sample_rate_eligible:.4f}"
        f"  ({sample_leaked}/{sample_with_ne})"
    )
    print(
        f"  ne item leak rate                 : {ne_rate:.4f}"
        f"  ({ne_leaked}/{ne_total})"
    )
    print(
        f"  ea item retention rate            : {ea_retention:.4f}"
        f"  ({ea_hit}/{ea_total})"
    )
    print(
        f"  ne leak thresholds                : "
        f"cov>={NE_COV_THRESHOLD}, bertP>{NE_BERT_THRESHOLD}"
    )
    print(
        f"  ea retention thresholds           : "
        f"cov>={EA_COV_THRESHOLD}, bertP>{EA_BERT_THRESHOLD}"
    )
    print(f"  bertscore enabled                 : {use_bert}")

    # ------------------------------ persist ------------------------------
    out_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    out_df.to_parquet(args.output, index=False)
    print(f"\n[save] per-row results -> {args.output}")

    # Subset: samples with no ne leak at all (n_ne_leak == 0).
    if args.noleak_output:
        noleak_df = out_df[out_df["n_ne_leak"] == 0].reset_index(drop=True)
        os.makedirs(os.path.dirname(args.noleak_output), exist_ok=True)
        noleak_df.to_parquet(args.noleak_output, index=False)
        print(
            f"[save] no-leak subset ({len(noleak_df)}/{len(out_df)} rows) -> "
            f"{args.noleak_output}"
        )


if __name__ == "__main__":
    main()
