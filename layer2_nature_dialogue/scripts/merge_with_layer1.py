#!/usr/bin/env python
"""Merge Layer 1 (reverse-synthesis) jsonl with Layer 2 (WildChat anchor)
sanitized public jsonl into a single set ready for SFT / RL / benchmark use.

We allow you to pick the mixing ratio via --layer2-weight (between 0 and 1),
and emit per-row sampling weights that downstream training code can read::

    {
      ...all layer-1/layer-2 fields...,
      "_split": "train" | "dev" | "test",
      "_sample_weight": 1.0 | <ratio>
    }

The script also stratifies the test split by domain (so the rarest domains
get at least one test example whenever possible).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from typing import Any, Dict, List


def _ensure_pkg_on_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.abspath(os.path.join(here, "..", ".."))
    if parent not in sys.path:
        sys.path.insert(0, parent)


def _read(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _write(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _domain(r: Dict[str, Any]) -> str:
    return ((r.get("spec") or {}).get("domain")) or "Other"


def _stratified_split(
    rows: List[Dict[str, Any]],
    *,
    test_frac: float,
    dev_frac: float,
    seed: int,
) -> Dict[str, List[Dict[str, Any]]]:
    by_domain: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_domain[_domain(r)].append(r)
    rng = random.Random(seed)
    splits: Dict[str, List[Dict[str, Any]]] = {"train": [], "dev": [], "test": []}
    for d, group in by_domain.items():
        rng.shuffle(group)
        n = len(group)
        n_test = max(1, int(round(n * test_frac))) if n >= 3 else 0
        n_dev = max(1, int(round(n * dev_frac))) if n - n_test >= 2 else 0
        splits["test"].extend(group[:n_test])
        splits["dev"].extend(group[n_test:n_test + n_dev])
        splits["train"].extend(group[n_test + n_dev:])
    return splits


def main() -> int:
    _ensure_pkg_on_path()
    p = argparse.ArgumentParser()
    p.add_argument("--layer1", required=True,
                   help="Layer 1 reverse-synthesis jsonl (e.g. data/layer1_v1.jsonl)")
    p.add_argument("--layer2", required=True,
                   help="Layer 2 sanitized public jsonl "
                        "(nature_data_syn/data/final/wildchat_anchor.public.jsonl)")
    p.add_argument("--out-dir", required=True)
    # Mixing strategy. Three splits use different ratios:
    #   train : Layer 1 dominant, Layer 2 small (drift-correction)
    #   dev   : 70/30
    #   test  : 30/70 (real data dominant for benchmark credibility)
    p.add_argument("--train-l2-frac", type=float, default=0.10)
    p.add_argument("--dev-l2-frac",   type=float, default=0.30)
    p.add_argument("--test-l2-frac",  type=float, default=0.70)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    l1 = _read(args.layer1)
    l2 = _read(args.layer2)
    print(f"loaded: layer1={len(l1)}, layer2={len(l2)}")

    # Filter Layer 1 to PASS-only rows (consistency.status).
    l1_pass = [r for r in l1 if (r.get("consistency") or {}).get("status") == "PASS"]
    print(f"layer1 PASS-only: {len(l1_pass)}")

    rng = random.Random(args.seed)
    rng.shuffle(l1_pass)
    rng.shuffle(l2)

    # Stratified split for Layer 2 by domain (it's the smaller / more precious set).
    l2_splits = _stratified_split(
        l2, test_frac=0.5, dev_frac=0.2, seed=args.seed,
    )

    def _draw_l1(n: int) -> List[Dict[str, Any]]:
        nonlocal l1_pass
        out, l1_pass = l1_pass[:n], l1_pass[n:]
        return out

    # Per split target sizes -- aim to use ALL of Layer 2 since it's small,
    # then top up Layer 1 to match the requested ratio.
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    for split, frac in [("train", args.train_l2_frac),
                        ("dev",   args.dev_l2_frac),
                        ("test",  args.test_l2_frac)]:
        l2_part = l2_splits[split]
        if frac <= 0 or not l2_part:
            n_l1 = max(1, len(l2_part))
        else:
            # n_l1 such that l2_part / (n_l1 + l2_part) = frac
            n_l1 = max(0, int(round(len(l2_part) * (1.0 - frac) / max(frac, 1e-6))))
        l1_part = _draw_l1(n_l1)

        merged: List[Dict[str, Any]] = []
        for r in l1_part:
            r = dict(r)
            r["_split"] = split
            r["_sample_weight"] = 1.0
            merged.append(r)
        for r in l2_part:
            r = dict(r)
            r["_split"] = split
            r["_sample_weight"] = 1.0
            merged.append(r)
        rng.shuffle(merged)
        path = os.path.join(out_dir, f"merged_{split}.jsonl")
        _write(path, merged)
        print(f"[{split}] L1={len(l1_part)} L2={len(l2_part)}  -> {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
