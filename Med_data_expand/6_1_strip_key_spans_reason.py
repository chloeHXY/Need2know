"""Strip the `reason` field from `extra_info.key_spans`.

Reads /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_answer_label.parquet,
converts each row's ``extra_info["key_spans"]`` (originally a list of
``{"reason": ..., "span": ...}`` dicts) into a plain list of span strings,
and writes the result back to the same file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PATH = Path(
    "/group/40047/eiraxyhuang/workspace/fc/DataG/Med_data_expand/5_.parquet"
)


def _to_dict(obj: Any) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    try:
        return dict(obj)
    except Exception:
        return {}


def _to_list(obj: Any) -> list:
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    try:
        return list(obj)
    except Exception:
        return []


def _spans_only(key_spans: Any) -> list[str]:
    """Reduce ``key_spans`` to a flat list of span strings.

    Handles entries that are dicts with a ``span`` key, plain strings, or
    anything else (coerced via ``str``). ``None``/empty values are skipped.
    """
    out: list[str] = []
    for item in _to_list(key_spans):
        if isinstance(item, str):
            span = item
        else:
            d = _to_dict(item)
            if "span" in d:
                span = d["span"]
            else:
                # Fallback: stringify whatever it is.
                span = str(item)
        if span is None:
            continue
        span = str(span)
        if span == "":
            continue
        out.append(span)
    return out


def _transform_extra_info(extra_info: Any) -> dict:
    d = dict(_to_dict(extra_info))  # shallow copy
    if "key_spans" in d:
        d["key_spans"] = _spans_only(d["key_spans"])
    return d


def main() -> None:
    print(f"[load] {PATH}")
    df = pd.read_parquet(PATH)
    print(f"  rows={len(df)} columns={df.columns.tolist()}")

    if "extra_info" not in df.columns:
        raise SystemExit("[error] no 'extra_info' column in the parquet")

    # Sanity check on the first row before transforming.
    sample_before = _to_dict(df["extra_info"].iloc[0]).get("key_spans")
    print(f"[before] sample key_spans (row 0): {sample_before!r}")

    df["extra_info"] = df["extra_info"].apply(_transform_extra_info)

    sample_after = _to_dict(df["extra_info"].iloc[0]).get("key_spans")
    print(f"[after]  sample key_spans (row 0): {sample_after!r}")

    print(f"[save] {PATH}")
    df.to_parquet(PATH, index=False)
    print("[done]")


if __name__ == "__main__":
    main()
