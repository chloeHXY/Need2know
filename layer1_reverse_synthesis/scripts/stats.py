#!/usr/bin/env python3
"""Print distribution statistics for a Layer 1 JSONL dataset.

Usage:
    python scripts/stats.py data/v1.jsonl
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from typing import Dict, List


def _bar(n: int, total: int, width: int = 30) -> str:
    if total == 0:
        return ""
    fill = int(round(width * n / total))
    return "█" * fill + "·" * (width - fill)


def report(rows: List[dict]) -> None:
    total = len(rows)
    if total == 0:
        print("(empty)")
        return

    status_c: Counter = Counter()
    domain_c: Counter = Counter()
    task_c: Counter = Counter()
    style_c: Counter = Counter()
    subj_c: Counter = Counter()
    tone_c: Counter = Counter()
    conf_c: Counter = Counter()
    e_attr_c: Counter = Counter()
    ne_attr_c: Counter = Counter()
    e_lens, ne_lens, prompt_lens, reform_lens = [], [], [], []
    e_recalls, ne_recalls = [], []

    err = 0
    for r in rows:
        if "error" in r:
            err += 1
            continue
        spec = r["spec"]
        cons = r["consistency"]
        status_c[cons["status"]] += 1
        domain_c[spec["domain"]] += 1
        task_c[spec["task"]] += 1
        style_c[spec["embedding_style"]] += 1
        subj_c[spec["subject"]] += 1
        tone_c[spec["tone"]] += 1
        conf_c[spec.get("confusion_kind") or "—"] += 1
        for a in spec["essential_info"]:
            e_attr_c[a["attribute"]] += 1
        for a in spec["nonessential_sensitive_info"]:
            ne_attr_c[a["attribute"]] += 1
        e_lens.append(len(spec["essential_info"]))
        ne_lens.append(len(spec["nonessential_sensitive_info"]))
        prompt_lens.append(len(r.get("raw_prompt", "").split()))
        reform_lens.append(len(r.get("gold_reformulation", "").split()))
        e_recalls.append(cons["essential_recall"])
        ne_recalls.append(cons["nonessential_recall"])

    def _avg(xs):
        return f"{statistics.mean(xs):.2f}" if xs else "—"

    def _section(title: str, c: Counter, normalizer: int) -> None:
        if not c:
            return
        print(f"\n{title}")
        for k, v in c.most_common():
            print(f"  {k:<32} {v:5d} ({100*v/normalizer:5.1f}%)  {_bar(v, normalizer)}")

    print(f"=== Layer 1 dataset stats ===")
    print(f"  total rows:        {total}")
    print(f"  errored rows:      {err}")
    valid = total - err

    print()
    print("Status mix:")
    for k, v in status_c.most_common():
        print(f"  {k:<10} {v:5d} ({100*v/max(1,valid):5.1f}%)  {_bar(v, max(1,valid))}")

    print()
    print(f"Avg essential count       : {_avg(e_lens)}")
    print(f"Avg non-essential count   : {_avg(ne_lens)}")
    print(f"Avg raw_prompt words      : {_avg(prompt_lens)}")
    print(f"Avg reformulation words   : {_avg(reform_lens)}")
    print(f"Avg essential recall      : {_avg(e_recalls)}")
    print(f"Avg non-essential recall  : {_avg(ne_recalls)}")

    _section("Domain mix",          domain_c, max(1, valid))
    _section("Task mix",            task_c,   max(1, valid))
    _section("Embedding style mix", style_c,  max(1, valid))
    _section("Subject mix",         subj_c,   max(1, valid))
    _section("Tone mix",            tone_c,   max(1, valid))
    _section("Confusion mix",       conf_c,   max(1, valid))
    _section("Essential attributes (counts)",     e_attr_c,  max(1, valid))
    _section("Non-essential attributes (counts)", ne_attr_c, max(1, valid))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    args = ap.parse_args()
    rows = []
    with open(args.path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    report(rows)


if __name__ == "__main__":
    main()
