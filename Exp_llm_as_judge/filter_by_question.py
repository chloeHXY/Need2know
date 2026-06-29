# -*- coding: utf-8 -*-
"""
Filter rows of A so that only rows whose ``extra_info["question"]`` also
appears in B are kept.

A: /group/40047/eiraxyhuang/workspace/fc/DataG/Exp_llm_as_judge/0_gt_ref.priv_llama.parquet
B: /group/40047/eiraxyhuang/workspace/fc/DataG/Exp_llm_as_judge/our.parquet

Usage:
    python filter_by_question.py
    python filter_by_question.py --a path/to/A.parquet --b path/to/B.parquet \
        --out path/to/out.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_A = Path(
    "/group/40047/eiraxyhuang/workspace/fc/DataG/Exp_llm_as_judge/"
    "0_gt_ref.priv_llama.parquet"
)
DEFAULT_B = Path(
    "/group/40047/eiraxyhuang/workspace/fc/DataG/Exp_llm_as_judge/our.parquet"
)
DEFAULT_OUT = Path(
    "/group/40047/eiraxyhuang/workspace/fc/DataG/Exp_llm_as_judge/"
    "0_gt_ref.priv_llama.aligned.parquet"
)


def get_question(extra: Any) -> str:
    """Pull ``question`` out of ``extra_info`` defensively."""
    if extra is None:
        return ""
    if isinstance(extra, dict):
        q = extra.get("question")
    else:
        # Some parquet readers return Mapping-like objects.
        try:
            q = dict(extra).get("question")
        except Exception:
            return ""
    if q is None:
        return ""
    return str(q).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default=str(DEFAULT_A), help="source parquet to filter")
    ap.add_argument("--b", default=str(DEFAULT_B), help="reference parquet for alignment")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output parquet path")
    args = ap.parse_args()

    a_path = Path(args.a)
    b_path = Path(args.b)
    out_path = Path(args.out)

    print(f"[info] reading A: {a_path}")
    df_a = pd.read_parquet(a_path)
    print(f"[info] A rows={len(df_a)} cols={list(df_a.columns)}")

    print(f"[info] reading B: {b_path}")
    df_b = pd.read_parquet(b_path)
    print(f"[info] B rows={len(df_b)} cols={list(df_b.columns)}")

    if "extra_info" not in df_a.columns:
        raise SystemExit("[error] A has no 'extra_info' column")
    if "extra_info" not in df_b.columns:
        raise SystemExit("[error] B has no 'extra_info' column")

    # Build the set of questions present in B.
    b_questions = df_b["extra_info"].apply(get_question)
    b_set = {q for q in b_questions.tolist() if q}
    print(f"[info] B unique non-empty questions: {len(b_set)}")

    # Compute A's questions and filter.
    a_questions = df_a["extra_info"].apply(get_question)
    mask = a_questions.isin(b_set) & a_questions.ne("")
    df_matched = df_a[mask].copy()
    df_matched["_question"] = a_questions[mask].values
    n_before_dedup = len(df_matched)

    # A may contain duplicate questions; keep only the first occurrence so
    # the output aligns 1-to-1 with B.
    df_filtered = (
        df_matched.drop_duplicates(subset="_question", keep="first")
        .drop(columns=["_question"])
        .reset_index(drop=True)
    )

    n_dup_dropped = n_before_dedup - len(df_filtered)
    print(
        f"[info] kept {len(df_filtered)} / {len(df_a)} rows from A "
        f"(matched={n_before_dedup}, dedup-dropped={n_dup_dropped}, "
        f"non-matched={len(df_a) - n_before_dedup})"
    )

    # Sanity diagnostics
    matched_qs = set(a_questions[mask].tolist())
    missing_in_a = b_set - matched_qs
    if missing_in_a:
        print(
            f"[warn] {len(missing_in_a)} questions in B have no match in A "
            f"(e.g. {next(iter(missing_in_a))[:80]!r})"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_filtered.to_parquet(out_path, index=False)
    print(f"[done] wrote {out_path}")


if __name__ == "__main__":
    main()
