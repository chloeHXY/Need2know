# -*- coding: utf-8 -*-
"""
Privacy-leak rate evaluation.

Goal
----
Evaluate how often the model-generated `priv_query` (the only payload sent to
an untrusted remote LLM) leaks private content from the original `question`.

Two complementary metrics are computed:

1. NE-leak rate (reuses the training reward logic in com_privacy_score.py)
   For every sample, for every C in extra_info["ne"]:
       leak(C) := coverage(priv_query, C) >= 1.0
                  OR BERTScore_rescaled P(C -> priv_query) > 0.3
   - sample-level leak: the sample is "leaked" if ANY ne is leaked.
   - ne-level leak    : leaks_C / total_ne_C across the whole set.

2. PII-leak rate (regex-based, more interpretable)
   Extract concrete PII tokens from the original `question` (email, phone,
   SSN, driver-license-like ID, credit-card-like number, URLs, long digit
   blocks). For each PII piece, check whether it still appears in
   priv_query (case-insensitive substring).
   - sample-level leak: at least one PII still appears in priv_query.
   - pii-level leak   : leaked_pii / total_pii.

Inputs
------
    --input  : parquet with cols [priv_query, extra_info] where
               extra_info has keys {question, ne, origin_ea, ...}
               default = inference/test_with_priv_query.parquet

Outputs
-------
    --output : parquet with per-sample metrics
    stdout   : aggregate leak rates
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any, Iterable

import pandas as pd
from tqdm import tqdm

# Reuse the reward-side primitives so the NE-leak metric is exactly aligned
# with what the model was trained against.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from com_privacy_score import (  # noqa: E402
    coverage,
    _bert_p_rescaled,
    _to_str_list,
    _get_bert_scorer,
)


# ---------------------------------------------------------------------------
# defaults
# ---------------------------------------------------------------------------
DEFAULT_INPUT = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/test_with_priv_query.parquet"
DEFAULT_OUTPUT = "/group/40047/eiraxyhuang/workspace/fc/DataG/z_eval/eval_privacy/eval_privacy_result.parquet"

# Same thresholds as compute_score / training reward.
COV_THRESHOLD = 1.0      # >= 1.0 -> literal leak
BERT_THRESHOLD = 0.3     # >  0.3 -> semantic leak


# ---------------------------------------------------------------------------
# PII extraction (regex-based, deliberately conservative -> high precision)
# ---------------------------------------------------------------------------
# Order matters: more specific patterns first so they "claim" the substring.
PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("url", re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)),
    # SSN: 3-2-4 digits with optional spaces / dashes
    ("ssn", re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b")),
    # International / US phone numbers, fairly permissive
    ("phone", re.compile(
        r"(?:\+\d{1,3}[\s\-.]?)?(?:\(?\d{2,4}\)?[\s\-.]?)?\d{3}[\s\-.]?\d{3,4}"
    )),
    # Credit-card-like 13-19 digit groups
    ("credit_card", re.compile(r"\b(?:\d[ \-]?){13,19}\b")),
    # Driver-license-ish: 6-10 chars mixing letters & digits, all upper
    # (matches dataset values like "JU2KHVMG", "68MMJG0W").
    ("driver_license", re.compile(r"\b(?=[A-Z0-9]{6,10}\b)(?=.*[A-Z])(?=.*\d)[A-Z0-9]{6,10}\b")),
    # Long bare digit sequences (e.g., 7+ digits) -- catch-all numeric IDs
    ("number", re.compile(r"\b\d{7,}\b")),
]


def extract_pii(text: str) -> list[tuple[str, str]]:
    """Return list of (pii_type, pii_value) found in text.

    Earlier matches "claim" their span so we don't double-count e.g. a phone
    number that overlaps with a generic long-digit match.
    """
    if not text:
        return []
    claimed: list[tuple[int, int]] = []
    found: list[tuple[str, str]] = []
    for ptype, pat in PII_PATTERNS:
        for m in pat.finditer(text):
            s, e = m.span()
            if any(not (e <= cs or s >= ce) for cs, ce in claimed):
                continue  # overlaps with already-claimed span
            value = m.group(0).strip()
            if not value:
                continue
            claimed.append((s, e))
            found.append((ptype, value))
    return found


def pii_in_text(pii_value: str, text: str) -> bool:
    """Case-insensitive substring check; tolerant to whitespace differences."""
    if not pii_value or not text:
        return False
    norm_v = re.sub(r"\s+", " ", pii_value).strip().lower()
    norm_t = re.sub(r"\s+", " ", text).lower()
    if norm_v in norm_t:
        return True
    # also try a "digits-only" match for phone / SSN-like values: if the
    # rewriter kept the same digit run with different formatting it is still
    # leaked.
    digits = re.sub(r"\D", "", pii_value)
    if len(digits) >= 7:
        if digits in re.sub(r"\D", "", text):
            return True
    return False


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
# core scoring
# ---------------------------------------------------------------------------
def score_ne_leak(
    priv_query: str,
    ne_list: list[str],
    use_bert: bool = True,
) -> dict[str, Any]:
    """NE-leak detection that mirrors com_privacy_score.compute_score.

    Returns per-NE coverage / bert P, plus aggregated flags.
    """
    out: dict[str, Any] = {
        "n_ne": len(ne_list),
        "ne_max_coverage": 0.0,
        "ne_argmax_coverage": None,
        "ne_max_p_rescaled": None,
        "ne_argmax_p_rescaled": None,
        "ne_leak_count_cov": 0,    # how many NEs leaked literally
        "ne_leak_count_bert": 0,   # how many NEs leaked semantically
        "ne_leak_count_any": 0,    # union of the two
        "ne_leak_any": False,      # boolean: this sample leaked at all
    }
    if not priv_query or not ne_list:
        return out

    # Coverage / Jaccard
    cov_flags = []
    max_cov, argmax_cov = 0.0, None
    for c in ne_list:
        cov = coverage(priv_query, c)
        cov_flags.append(cov >= COV_THRESHOLD)
        if cov > max_cov:
            max_cov, argmax_cov = cov, c
    out["ne_max_coverage"] = max_cov
    out["ne_argmax_coverage"] = argmax_cov
    out["ne_leak_count_cov"] = sum(cov_flags)

    # BERTScore (rescaled precision); skip if not available
    bert_flags = [False] * len(ne_list)
    if use_bert:
        scores = _bert_p_rescaled(ne_list, priv_query)
        if scores is not None:
            max_p = max(scores)
            out["ne_max_p_rescaled"] = max_p
            out["ne_argmax_p_rescaled"] = ne_list[scores.index(max_p)]
            bert_flags = [p > BERT_THRESHOLD for p in scores]
            out["ne_leak_count_bert"] = sum(bert_flags)

    any_flags = [a or b for a, b in zip(cov_flags, bert_flags)]
    out["ne_leak_count_any"] = sum(any_flags)
    out["ne_leak_any"] = any(any_flags)
    return out


def score_pii_leak(question: str, priv_query: str) -> dict[str, Any]:
    """Regex-based PII leak detection over the original question."""
    piis = extract_pii(question or "")
    leaked: list[tuple[str, str]] = []
    for ptype, val in piis:
        if pii_in_text(val, priv_query or ""):
            leaked.append((ptype, val))
    return {
        "pii_total": len(piis),
        "pii_leaked": len(leaked),
        "pii_items": piis,
        "pii_leaked_items": leaked,
        "pii_leak_any": len(leaked) > 0,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Privacy-leak rate eval.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--no_bert", action="store_true",
                        help="Disable BERTScore (only Jaccard-based leak).")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only score the first N rows (0 = all)")
    args = parser.parse_args()

    print(f"[load] {args.input}")
    df = pd.read_parquet(args.input)
    print(f"[load] rows={len(df)} cols={df.columns.tolist()}")

    if "priv_query" not in df.columns:
        raise KeyError("input parquet missing column: priv_query")
    if "extra_info" not in df.columns:
        raise KeyError("input parquet missing column: extra_info")

    n = len(df)
    if args.limit and args.limit < n:
        df = df.iloc[: args.limit].copy()
        n = len(df)
    print(f"[plan] scoring {n} rows")

    # Warm up BERTScorer once so the per-row call is cheap (and we can fail
    # loudly early if the model isn't available).
    use_bert = not args.no_bert
    if use_bert:
        scorer = _get_bert_scorer()
        if scorer is None:
            print("[warn] BERTScorer unavailable -> falling back to Jaccard only")
            use_bert = False

    rows: list[dict[str, Any]] = []
    for i in tqdm(range(n), desc="scoring"):
        r = df.iloc[i]
        priv_q = r["priv_query"] if isinstance(r["priv_query"], str) else ""
        ei = r["extra_info"]
        question = _get(ei, "question", "") or ""
        ne_list = _to_str_list(_get(ei, "ne"))
        origin_ea = _to_str_list(_get(ei, "origin_ea"))

        ne_metrics = score_ne_leak(priv_q, ne_list, use_bert=use_bert)
        pii_metrics = score_pii_leak(question, priv_q)

        rows.append({
            "index": int(_get(ei, "index", i) or i),
            "question": question,
            "priv_query": priv_q,
            "ne": ne_list,
            "origin_ea": origin_ea,
            **ne_metrics,
            **pii_metrics,
        })

    res = pd.DataFrame(rows)

    # ----------------------------- aggregate -----------------------------
    n_total = len(res)
    n_with_ne = int((res["n_ne"] > 0).sum())
    n_with_pii = int((res["pii_total"] > 0).sum())

    # Sample-level NE leak rate over samples that actually have NE
    ne_sample_leak_rate = (
        res.loc[res["n_ne"] > 0, "ne_leak_any"].mean() if n_with_ne else 0.0
    )
    # NE-element-level leak rate
    total_ne = int(res["n_ne"].sum())
    total_ne_leaked = int(res["ne_leak_count_any"].sum())
    ne_elem_leak_rate = total_ne_leaked / total_ne if total_ne else 0.0
    total_ne_leaked_cov = int(res["ne_leak_count_cov"].sum())
    total_ne_leaked_bert = int(res["ne_leak_count_bert"].sum())

    # Sample-level PII leak rate over samples that have any PII
    pii_sample_leak_rate = (
        res.loc[res["pii_total"] > 0, "pii_leak_any"].mean() if n_with_pii else 0.0
    )
    # PII-element-level leak rate
    total_pii = int(res["pii_total"].sum())
    total_pii_leaked = int(res["pii_leaked"].sum())
    pii_elem_leak_rate = total_pii_leaked / total_pii if total_pii else 0.0

    print("\n=== Privacy-leak evaluation ===")
    print(f"total samples                       : {n_total}")
    print(f"samples with at least one NE        : {n_with_ne}")
    print(f"samples with at least one PII (regex): {n_with_pii}")
    print()
    print("-- NE-leak (reward-aligned) --")
    print(f"  total NE elements                 : {total_ne}")
    print(f"  NE elements leaked (literal cov)  : {total_ne_leaked_cov}")
    print(f"  NE elements leaked (BERTScore)    : {total_ne_leaked_bert}")
    print(f"  NE elements leaked (any)          : {total_ne_leaked}")
    print(f"  ELEMENT-level NE-leak rate        : {ne_elem_leak_rate:.4f}")
    print(f"  SAMPLE-level NE-leak rate         : {ne_sample_leak_rate:.4f}")
    print()
    print("-- PII-leak (regex) --")
    print(f"  total PII elements                : {total_pii}")
    print(f"  PII elements leaked               : {total_pii_leaked}")
    print(f"  ELEMENT-level PII-leak rate       : {pii_elem_leak_rate:.4f}")
    print(f"  SAMPLE-level PII-leak rate        : {pii_sample_leak_rate:.4f}")

    # ----------------------------- save -----------------------------
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    # Cast non-parquet-friendly cols (lists of tuples) to string lists.
    res_to_save = res.copy()
    res_to_save["pii_items"] = res_to_save["pii_items"].apply(
        lambda xs: [f"{t}::{v}" for t, v in xs]
    )
    res_to_save["pii_leaked_items"] = res_to_save["pii_leaked_items"].apply(
        lambda xs: [f"{t}::{v}" for t, v in xs]
    )
    res_to_save.to_parquet(args.output, index=False)
    print(f"\n[save] wrote per-sample results to: {args.output}")


if __name__ == "__main__":
    main()
