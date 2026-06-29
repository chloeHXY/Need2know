"""
Drop the top-50 high-leak ``wild`` rows (per ``wild_pii_leak_sorted.json``)
from a target parquet file.

Matching mirrors ``0_eval_by_ability_excl_wild_top50.py``: a row is removed
iff ``ability == 'wild'`` AND it matches one of the top-K entries via any of:
  * (question, priv_query) text pair (after normalization), OR
  * question text alone, OR
  * row_index (positional index in the input parquet).

Edit the constants below to point at the desired input/output parquet.
No CLI args -- just run ``python 6_drop_top50.py``.
"""

from __future__ import annotations

import json
import os
import re

import pandas as pd

# ---------------------------------------------------------------------------
# >>> EDIT ME <<<
# ---------------------------------------------------------------------------
INPUT_PARQUET = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_protectfrom_qwen7b.parquet"
)
OUTPUT_PARQUET = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_.parquet"
)
# INPUT_PARQUET = (
#     "/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/0_.parquet"
# )
# OUTPUT_PARQUET = (
#     "/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/0_.parquet"
# )

DROPPED_PARQUET = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/"
    "test_with_priv_query_dropped.parquet"
)
EXCLUDE_JSON = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/"
    "wild_pii_leak_sorted.json"
)
TOP_K = 50

# Column names (match 0_eval.py defaults).
ABILITY_COL = "ability"
PRIV_QUERY_COL = "priv_query"
EXTRA_INFO_COL = "extra_info"
WILD_ABILITY = "wild"
# ---------------------------------------------------------------------------


_WS_RE = re.compile(r"\s+")


def _norm_key(s) -> str:
    if s is None:
        return ""
    return _WS_RE.sub(" ", str(s).strip().lower())


def _get(d, k, default=None):
    """Robust getter for dict / pandas Series / namespace-ish objects."""
    if d is None:
        return default
    if isinstance(d, dict):
        return d.get(k, default)
    try:
        return d[k]
    except Exception:
        try:
            return getattr(d, k, default)
        except Exception:
            return default


def _load_exclude_keys(json_path: str, top_k: int):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(
            f"expected top-level list in {json_path}, got {type(data)}"
        )
    take = data[: max(0, int(top_k))]
    idx_set: set[int] = set()
    q_set: set[str] = set()
    qp_set: set[tuple[str, str]] = set()
    for entry in take:
        ri = entry.get("row_index")
        if isinstance(ri, int):
            idx_set.add(ri)
        q = _norm_key(entry.get("question", ""))
        p = _norm_key(entry.get("priv_query", ""))
        if q:
            q_set.add(q)
        if q and p:
            qp_set.add((q, p))
    return idx_set, q_set, qp_set


def main() -> None:
    print(f"[load] {INPUT_PARQUET}")
    df = pd.read_parquet(INPUT_PARQUET)
    print(f"[load] rows={len(df)} cols={df.columns.tolist()}")
    if ABILITY_COL in df.columns:
        print(f"[load] ability counts:\n{df[ABILITY_COL].value_counts()}")
    else:
        raise KeyError(
            f"input parquet missing required column: {ABILITY_COL!r}"
        )
    for col in (PRIV_QUERY_COL, EXTRA_INFO_COL):
        if col not in df.columns:
            raise KeyError(f"input parquet missing required column: {col!r}")

    idx_set, q_set, qp_set = _load_exclude_keys(EXCLUDE_JSON, TOP_K)
    print(
        f"[excl] top_k={TOP_K}  row_index keys={len(idx_set)}  "
        f"question keys={len(q_set)}  (q,p) pairs={len(qp_set)}"
    )

    keep_mask: list[bool] = []
    drop_reasons: list[str] = []
    by_reason = {
        "match:question+priv_query": 0,
        "match:question": 0,
        "match:row_index": 0,
    }
    n_drop = 0
    for i in range(len(df)):
        r = df.iloc[i]
        ability = str(r[ABILITY_COL]) if r[ABILITY_COL] is not None else ""
        if ability != WILD_ABILITY:
            keep_mask.append(True)
            drop_reasons.append("")
            continue

        priv_q = (
            r[PRIV_QUERY_COL] if isinstance(r[PRIV_QUERY_COL], str) else ""
        )
        ei = r[EXTRA_INFO_COL]
        question = _get(ei, "question", "") or ""
        qn = _norm_key(question)
        pn = _norm_key(priv_q)

        reason = ""
        if (qn, pn) in qp_set:
            reason = "match:question+priv_query"
        elif qn and qn in q_set:
            reason = "match:question"
        elif i in idx_set:
            reason = "match:row_index"

        if reason:
            keep_mask.append(False)
            drop_reasons.append(reason)
            by_reason[reason] += 1
            n_drop += 1
        else:
            keep_mask.append(True)
            drop_reasons.append("")

    kept_df = df[keep_mask].reset_index(drop=True)
    dropped_df = df[[not m for m in keep_mask]].copy()
    dropped_df["__exclude_reason"] = [
        dr for dr, m in zip(drop_reasons, keep_mask) if not m
    ]
    dropped_df = dropped_df.reset_index(drop=True)

    print(f"\n[filter] dropped {n_drop} rows; kept {len(kept_df)} rows")
    for k, v in by_reason.items():
        print(f"  - {k}: {v}")
    if ABILITY_COL in kept_df.columns:
        print(
            f"[filter] kept ability counts:\n"
            f"{kept_df[ABILITY_COL].value_counts()}"
        )

    out_dir = os.path.dirname(OUTPUT_PARQUET)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    kept_df.to_parquet(OUTPUT_PARQUET, index=False)
    print(f"\n[save] kept    -> {OUTPUT_PARQUET}")

    if DROPPED_PARQUET:
        drop_dir = os.path.dirname(DROPPED_PARQUET)
        if drop_dir:
            os.makedirs(drop_dir, exist_ok=True)
        dropped_df.to_parquet(DROPPED_PARQUET, index=False)
        print(f"[save] dropped -> {DROPPED_PARQUET}")


if __name__ == "__main__":
    main()
