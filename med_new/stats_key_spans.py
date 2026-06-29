"""Statistics for `extra_info['key_spans']` in the cleaned parquet.

For every span we measure:
  * char_len  -- len(span)
  * word_len  -- number of whitespace-separated tokens

We report:
  * total spans, total rows (with at least one span), avg spans per row
  * char-length distribution (min/p25/median/mean/p75/p90/p95/max + histogram)
  * word-length distribution (same set)
  * top 5 longest / shortest example spans
"""

import statistics
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

DEFAULT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.parquet"


def to_dict(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    try:
        return dict(obj)
    except Exception:
        return {}


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0
    if p <= 0:
        return sorted_vals[0]
    if p >= 100:
        return sorted_vals[-1]
    k = (len(sorted_vals) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def fmt_dist(name: str, vals: list[int]) -> None:
    if not vals:
        print(f"{name}: <empty>")
        return
    s = sorted(vals)
    print(f"{name} distribution (n={len(s)}):")
    print(f"  min   = {s[0]}")
    print(f"  p25   = {percentile(s, 25):.1f}")
    print(f"  median= {percentile(s, 50):.1f}")
    print(f"  mean  = {statistics.fmean(s):.2f}")
    print(f"  p75   = {percentile(s, 75):.1f}")
    print(f"  p90   = {percentile(s, 90):.1f}")
    print(f"  p95   = {percentile(s, 95):.1f}")
    print(f"  max   = {s[-1]}")


def char_histogram(vals: list[int]) -> None:
    """A coarse histogram for character lengths."""
    bins = [
        (0, 19), (20, 39), (40, 59), (60, 79), (80, 99),
        (100, 149), (150, 199), (200, 299), (300, 499),
        (500, 999), (1000, 10**9),
    ]
    counts = [0] * len(bins)
    for v in vals:
        for i, (lo, hi) in enumerate(bins):
            if lo <= v <= hi:
                counts[i] += 1
                break
    total = max(sum(counts), 1)
    print("\nchar_len histogram:")
    for (lo, hi), c in zip(bins, counts):
        label = f"{lo}-{hi}" if hi < 10**9 else f">={lo}"
        bar = "#" * int(round(40 * c / total))
        print(f"  {label:>10s} | {c:5d}  {bar}")


def main(path: str = DEFAULT_PATH) -> None:
    p = Path(path)
    if not p.is_file():
        print(f"[ERROR] not found: {p}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_parquet(p)
    print(f"rows           : {len(df)}")

    char_lens: list[int] = []
    word_lens: list[int] = []
    spans_with_idx: list[tuple[int, int, str]] = []  # (char_len, row_idx, text)
    rows_with_span = 0
    spans_per_row: list[int] = []

    for row_idx, ei in enumerate(df["extra_info"].tolist()):
        d = to_dict(ei)
        ks = d.get("key_spans")
        if ks is None:
            spans_per_row.append(0)
            continue
        try:
            ks_list = list(ks)
        except Exception:
            ks_list = []
        if ks_list:
            rows_with_span += 1
        spans_per_row.append(len(ks_list))
        for item in ks_list:
            it = to_dict(item)
            text = it.get("span", "") or ""
            text = str(text)
            cl = len(text)
            wl = len(text.split())
            char_lens.append(cl)
            word_lens.append(wl)
            spans_with_idx.append((cl, row_idx, text))

    print(f"rows_with_key_spans: {rows_with_span}")
    print(f"total spans        : {len(char_lens)}")
    if spans_per_row:
        print(
            "spans_per_row      : "
            f"min={min(spans_per_row)}, "
            f"mean={statistics.fmean(spans_per_row):.2f}, "
            f"median={statistics.median(spans_per_row)}, "
            f"max={max(spans_per_row)}"
        )
        # spans-per-row histogram
        cnt = Counter(spans_per_row)
        print("\nspans_per_row histogram:")
        for k in sorted(cnt):
            print(f"  {k:>3d} spans -> {cnt[k]} rows")

    print()
    fmt_dist("char_len", char_lens)
    print()
    fmt_dist("word_len", word_lens)
    char_histogram(char_lens)

    if spans_with_idx:
        spans_with_idx.sort(key=lambda x: x[0])
        print("\nshortest 5 spans (char_len, row_idx, text):")
        for cl, idx, t in spans_with_idx[:5]:
            print(f"  {cl:4d}  row={idx}  {t!r}")
        print("\nlongest 5 spans (char_len, row_idx, text):")
        for cl, idx, t in spans_with_idx[-5:][::-1]:
            preview = t if len(t) <= 200 else t[:200] + "..."
            print(f"  {cl:4d}  row={idx}  {preview!r}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    main(arg)
