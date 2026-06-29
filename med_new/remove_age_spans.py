"""
Remove age-related strings from extra_info.key_spans in
med.anonymized.cleaned.with_answer_label.parquet.

An "age-related" string is one whose text contains an age expression like:
    "xx-year-old", "xx year old", "xx-day-old", "xx month old",
    "xx yr old", "xx years old", ...
matched (case-insensitive) by the regex:
    (year|month|week|day|hour|minute|yr|mo|wk|hr|min)s?[\s\-]*old

A backup of the original file is written next to it as `*.bak.parquet`
before overwriting.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd


INPUT_PATH = Path(
    "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/"
    "med.anonymized.cleaned.with_answer_label.parquet"
)
BACKUP_PATH = INPUT_PATH.with_suffix(".bak.parquet")

EXTRA_INFO_FIELD = "extra_info"
KEY_SPANS_FIELD = "key_spans"

AGE_PATTERN = re.compile(
    r"(year|month|week|day|hour|minute|yr|mo|wk|hr|min)s?[\s\-]*old",
    re.IGNORECASE,
)


def is_age_string(s) -> bool:
    if not isinstance(s, str):
        return False
    return AGE_PATTERN.search(s) is not None


def to_mutable_dict(obj) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    if isinstance(obj, np.ndarray):
        try:
            return dict(obj.tolist())
        except Exception:
            pass
    try:
        return dict(obj)
    except Exception:
        return {}


def filter_key_spans(extra_info) -> tuple[dict, int]:
    """Return (new_extra_info_dict, removed_count)."""
    d = to_mutable_dict(extra_info)
    ks = d.get(KEY_SPANS_FIELD)
    if ks is None:
        return d, 0

    try:
        items = list(ks)
    except Exception:
        return d, 0

    kept: list[str] = []
    removed = 0
    for item in items:
        if is_age_string(item):
            removed += 1
            continue
        kept.append(item)

    # store back as plain python list (parquet/pyarrow handles list[str] fine)
    d[KEY_SPANS_FIELD] = kept
    return d, removed


def main() -> None:
    if not INPUT_PATH.is_file():
        print(f"[ERROR] input not found: {INPUT_PATH}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading: {INPUT_PATH}", file=sys.stderr)
    df = pd.read_parquet(INPUT_PATH)
    n = len(df)
    print(f"  rows={n}", file=sys.stderr)

    if EXTRA_INFO_FIELD not in df.columns:
        print(f"[ERROR] '{EXTRA_INFO_FIELD}' column not found.", file=sys.stderr)
        sys.exit(2)

    new_extras: list[dict] = []
    total_removed = 0
    rows_affected = 0
    sample_removed: list[str] = []

    # We also want a quick view of what will be removed for verification.
    for ei in df[EXTRA_INFO_FIELD].tolist():
        d = to_mutable_dict(ei)
        ks = d.get(KEY_SPANS_FIELD)
        before = list(ks) if ks is not None else []
        new_d, removed = filter_key_spans(ei)
        new_extras.append(new_d)
        if removed > 0:
            rows_affected += 1
            total_removed += removed
            for s in before:
                if is_age_string(s) and len(sample_removed) < 10:
                    sample_removed.append(s)

    df[EXTRA_INFO_FIELD] = new_extras

    print(
        f"  removed {total_removed} age-related key_spans "
        f"across {rows_affected} rows",
        file=sys.stderr,
    )
    if sample_removed:
        print("  sample removed strings:", file=sys.stderr)
        for s in sample_removed:
            print(f"    - {s!r}", file=sys.stderr)

    # backup once
    if not BACKUP_PATH.exists():
        print(f"Backup -> {BACKUP_PATH}", file=sys.stderr)
        shutil.copy2(INPUT_PATH, BACKUP_PATH)
    else:
        print(f"Backup already exists, keeping it: {BACKUP_PATH}", file=sys.stderr)

    print(f"Writing: {INPUT_PATH}", file=sys.stderr)
    df.to_parquet(INPUT_PATH, index=False)

    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
