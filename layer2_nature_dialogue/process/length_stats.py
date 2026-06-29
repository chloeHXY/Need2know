"""One-off length distribution diagnostic for the WildChat single-turn pool.

Run:
    python length_stats.py

Reports word-count percentiles for:
  (A) full S0 dump  -> 00_loaded.jsonl  (no length filter)
      sub-restriction: turn==1, language=='English', toxic==False, redacted==False
      -> this is the natural single-turn English prompt distribution
  (B) post-S1 pool  -> 01_struct.jsonl  (already 25..250 word-clipped)

Only uses the cached `user_words` field. No re-tokenization.
"""

from __future__ import annotations
import json
import os
import statistics
from collections import Counter

STAGES_DIR = os.path.join(os.path.dirname(__file__), "stages_full")
LOADED = os.path.join(STAGES_DIR, "00_loaded.jsonl")
STRUCT = os.path.join(STAGES_DIR, "01_struct.jsonl")

PCTS = [1, 5, 10, 25, 50, 75, 90, 95, 99]


def collect_words(path: str, *, restrict_natural_singleturn_en: bool) -> list[int]:
    out: list[int] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if restrict_natural_singleturn_en:
                if r.get("turn") != 1:
                    continue
                if r.get("language") != "English":
                    continue
                if r.get("toxic"):
                    continue
                if r.get("redacted"):
                    continue
                if not (r.get("first_user") or "").strip():
                    continue
            n = int(r.get("user_words", 0))
            if n > 0:
                out.append(n)
    return out


def percentile(sorted_vals: list[int], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def report(name: str, vals: list[int]) -> None:
    print(f"\n=== {name} ===")
    print(f"  N        = {len(vals):,}")
    if not vals:
        return
    s = sorted(vals)
    print(f"  mean     = {statistics.fmean(s):.1f}")
    print(f"  median   = {statistics.median(s):.0f}")
    print(f"  stdev    = {statistics.pstdev(s):.1f}")
    print(f"  min,max  = {s[0]}, {s[-1]}")
    print("  percentiles:")
    for p in PCTS:
        print(f"    p{p:<3}  = {percentile(s, p):8.1f}")
    # share inside the 25..250 window
    in_win = sum(1 for v in s if 25 <= v <= 250)
    print(f"  share in [25,250] = {in_win:,} / {len(s):,} = {in_win/len(s)*100:.2f}%")
    # coarse histogram
    bins = [0, 10, 25, 50, 100, 150, 200, 250, 350, 500, 750, 1000, 1500, 2500, 10**9]
    labels = [f"[{a},{b})" for a, b in zip(bins[:-1], bins[1:])]
    c = Counter()
    for v in s:
        for i, b in enumerate(bins[1:]):
            if v < b:
                c[labels[i]] += 1
                break
    print("  histogram:")
    for lab in labels:
        n = c.get(lab, 0)
        bar = "#" * int(60 * n / max(1, len(s)))
        print(f"    {lab:>12s}  {n:>8,}  {bar}")


def main() -> None:
    if not os.path.exists(LOADED):
        raise SystemExit(f"missing: {LOADED}")
    if not os.path.exists(STRUCT):
        raise SystemExit(f"missing: {STRUCT}")

    natural = collect_words(LOADED, restrict_natural_singleturn_en=True)
    report("Natural single-turn English (turn=1, lang=en, toxic=F, redacted=F)", natural)

    raw = collect_words(LOADED, restrict_natural_singleturn_en=False)
    report("Raw S0 (no language/turn filter)", raw)

    kept = collect_words(STRUCT, restrict_natural_singleturn_en=False)
    report("After S1 (01_struct.jsonl, already clipped to 25..250)", kept)


if __name__ == "__main__":
    main()
