"""
Build a *filtered* parquet that keeps ONLY the rows which would be aggregated
by ``0_eval_by_ability_excl_wild_top50.py``.

That eval-time filter drops rows whose ability == ``wild`` AND match one of
the top-50 entries in ``wild_pii_leak_sorted.json``. Matching is done via:
  - (question, priv_query) text pair (after normalization), OR
  - question text alone, OR
  - row_index (positional index in the input parquet).

This script produces ``test_with_priv_query_kept.parquet`` containing only
the rows that survive the same filter on
``test_with_priv_query.parquet``.
"""

from __future__ import annotations

import json
import os
import re

import pandas as pd

INPUT  = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/test_with_priv_query.parquet"
EXCL_J = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/wild_pii_leak_sorted.json"
OUTPUT = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/test_with_priv_query_kept.parquet"
DROPPED = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/test_with_priv_query_dropped.parquet"
TOP_K  = 50
WILD   = "wild"

_WS_RE = re.compile(r"\s+")


def _norm_key(s) -> str:
    if s is None:
        return ""
    return _WS_RE.sub(" ", str(s).strip().lower())


def _get(d, k, default=None):
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


def main() -> None:
    print(f"[load] {INPUT}")
    df = pd.read_parquet(INPUT)
    print(f"[load] rows={len(df)} cols={df.columns.tolist()}")
    print(f"[load] ability counts:\n{df['ability'].value_counts()}")

    with open(EXCL_J, "r", encoding="utf-8") as f:
        data = json.load(f)
    take = data[: TOP_K]
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
    print(
        f"[excl] top_k={TOP_K}  row_index keys={len(idx_set)}  "
        f"question keys={len(q_set)}  (q,p) pairs={len(qp_set)}"
    )

    keep_mask = []
    drop_reasons = []
    n_drop = 0
    by_reason = {"match:question+priv_query": 0,
                 "match:question": 0,
                 "match:row_index": 0}
    for i in range(len(df)):
        r = df.iloc[i]
        ability = str(r["ability"]) if r["ability"] is not None else ""
        if ability != WILD:
            keep_mask.append(True)
            drop_reasons.append("")
            continue

        priv_q = r["priv_query"] if isinstance(r["priv_query"], str) else ""
        ei = r["extra_info"]
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
    print(f"[filter] kept ability counts:\n{kept_df['ability'].value_counts()}")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    kept_df.to_parquet(OUTPUT, index=False)
    print(f"\n[save] kept    -> {OUTPUT}")
    dropped_df.to_parquet(DROPPED, index=False)
    print(f"[save] dropped -> {DROPPED}")


if __name__ == "__main__":
    main()
