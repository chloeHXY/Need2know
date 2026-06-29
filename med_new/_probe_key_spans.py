"""Probe the structure of `key_spans` in the cleaned parquet."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.parquet"


def to_dict(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    try:
        return dict(obj)
    except Exception:
        return {}


def main() -> None:
    df = pd.read_parquet(PATH)
    print("rows:", len(df))
    print("columns:", df.columns.tolist())

    # Look for key_spans at the top level.
    if "key_spans" in df.columns:
        print("[found] top-level column 'key_spans'")
        sample = df["key_spans"].iloc[0]
        print("sample type:", type(sample).__name__)
        print("sample value:", sample)
        return

    # Otherwise look inside extra_info.
    if "extra_info" not in df.columns:
        print("[not found] no 'extra_info' column either", file=sys.stderr)
        return

    # Walk a few rows to discover keys inside extra_info.
    seen_keys = set()
    sample_with_keyspans = None
    for ei in df["extra_info"].head(5).tolist():
        d = to_dict(ei)
        seen_keys.update(d.keys())
        if "key_spans" in d and sample_with_keyspans is None:
            sample_with_keyspans = d["key_spans"]
    print("extra_info keys (first 5 rows):", sorted(seen_keys))

    if sample_with_keyspans is not None:
        print("\n[found] extra_info['key_spans']")
        print("sample type:", type(sample_with_keyspans).__name__)
        try:
            lst = list(sample_with_keyspans)
        except Exception:
            lst = []
        print("len:", len(lst))
        if lst:
            first = lst[0]
            print("first item type:", type(first).__name__)
            print("first item:", first)
            # If dict-like, print its keys
            try:
                print("first item keys:", list(to_dict(first).keys()))
            except Exception:
                pass


if __name__ == "__main__":
    main()
