# -*- coding: utf-8 -*-
"""
Lift `question_pii_entities` and `question_pii_entities_full` out of the
nested `extra_info` column to top-level columns in the parquet.

Default I/O:
    /group/40047/eiraxyhuang/workspace/fc/DataG/inference/1_privacy/test_with_priv_query_pp_with_pii.parquet
    --> overwrite the same file (a `.bak` copy is created the first time).

Usage:
    python 1_lift_pii_to_top.py
    python 1_lift_pii_to_top.py -i in.parquet -o out.parquet
    python 1_lift_pii_to_top.py --keep-in-extra        # also keep them inside extra_info
    python 1_lift_pii_to_top.py --no-backup            # skip writing the .bak file
"""

from __future__ import annotations

import argparse
import copy
import os
import shutil
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_PATH = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/1_privacy/"
    "test_with_priv_query_pp_with_pii.parquet"
)

EXTRA_INFO_COL = "extra_info"
LIFT_KEYS = ("question_pii_entities", "question_pii_entities_full")


def to_mutable_dict(extra_info: Any) -> dict:
    """Normalize an `extra_info` cell into a plain mutable dict.

    Mirrors the helper in 0_pii_note.py so the two scripts agree on shapes.
    """
    if extra_info is None:
        return {}
    if isinstance(extra_info, dict):
        return dict(extra_info)
    if isinstance(extra_info, np.ndarray):
        if extra_info.dtype.names:
            return {n: (extra_info[n].item() if hasattr(extra_info[n], "item")
                        else extra_info[n])
                    for n in extra_info.dtype.names}
        try:
            return dict(extra_info.tolist())
        except Exception:
            return {}
    if hasattr(extra_info, "items"):
        try:
            return dict(extra_info.items())
        except Exception:
            pass
    try:
        return copy.deepcopy(dict(extra_info))
    except Exception:
        return {}


def _coerce_value(val: Any, *, default):
    """Make sure the lifted value is JSON/parquet friendly (list-like)."""
    if val is None:
        return default
    if isinstance(val, np.ndarray):
        return val.tolist()
    if isinstance(val, list):
        return val
    if isinstance(val, tuple):
        return list(val)
    # Single dict for the *_full case shouldn't happen, but keep robust:
    return val


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lift question_pii_entities[_full] from extra_info to top-level columns."
    )
    parser.add_argument("--input", "-i", default=DEFAULT_PATH)
    parser.add_argument("--output", "-o", default=None,
                        help="Output parquet path (default: overwrite input).")
    parser.add_argument("--keep-in-extra", action="store_true",
                        help="Keep the two keys inside extra_info as well.")
    parser.add_argument("--no-backup", action="store_true",
                        help="Skip creating a .bak copy when overwriting.")
    args = parser.parse_args()

    in_path = args.input
    out_path = args.output or in_path
    overwrite = os.path.abspath(in_path) == os.path.abspath(out_path)

    print(f"[load] reading parquet: {in_path}", flush=True)
    df = pd.read_parquet(in_path)
    print(f"[load] rows={len(df)} cols={df.columns.tolist()}", flush=True)

    if EXTRA_INFO_COL not in df.columns:
        raise SystemExit(f"[ERROR] column '{EXTRA_INFO_COL}' not found.")

    # Backup once before overwriting
    if overwrite and not args.no_backup:
        bak = in_path + ".bak"
        if not os.path.exists(bak):
            shutil.copy2(in_path, bak)
            print(f"[backup] saved original to: {bak}", flush=True)
        else:
            print(f"[backup] reusing existing: {bak}", flush=True)

    extras = [to_mutable_dict(x) for x in df[EXTRA_INFO_COL].tolist()]

    # Defaults for each lifted column
    defaults = {
        "question_pii_entities": [],         # list[str]
        "question_pii_entities_full": [],    # list[dict]
    }

    lifted_cols: dict[str, list] = {k: [] for k in LIFT_KEYS}
    n_present = {k: 0 for k in LIFT_KEYS}

    for ei in extras:
        for k in LIFT_KEYS:
            if k in ei:
                n_present[k] += 1
                lifted_cols[k].append(_coerce_value(ei[k], default=defaults[k]))
            else:
                lifted_cols[k].append(copy.deepcopy(defaults[k]))
            if not args.keep_in_extra and k in ei:
                ei.pop(k, None)

    # Write back extra_info (cleaned) and add the lifted columns
    df[EXTRA_INFO_COL] = extras
    for k in LIFT_KEYS:
        df[k] = lifted_cols[k]

    # ---- stats ----
    n = len(df)
    n_with_pii = sum(1 for v in lifted_cols["question_pii_entities"] if v)
    n_items = sum(len(v) for v in lifted_cols["question_pii_entities"])
    print("\n=== lift summary ===")
    print(f"  total rows                            : {n}")
    for k in LIFT_KEYS:
        print(f"  rows that had '{k}' inside extra_info : {n_present[k]}")
    print(f"  rows with >=1 PII item                : {n_with_pii}")
    print(f"  total PII items                       : {n_items}")
    print(f"  keep-in-extra                         : {args.keep_in_extra}")

    print(f"\n[save] writing parquet: {out_path}", flush=True)
    df.to_parquet(out_path, index=False)
    print("[save] done.", flush=True)
    print(f"[cols] final columns: {df.columns.tolist()}", flush=True)


if __name__ == "__main__":
    main()
