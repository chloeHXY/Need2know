#!/usr/bin/env python
"""Quickly inspect samples from any stage of the natural-anchor pipeline.

Usage::

    python nature_data_syn/scripts/inspect_anchor.py \
        nature_data_syn/data/stages/06_concord.jsonl --n 5

    # only show rows where consensus has at least one non_essential span
    python nature_data_syn/scripts/inspect_anchor.py \
        nature_data_syn/data/stages/07_unified.jsonl --n 5 --has-ne
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from typing import Any, Dict, List


def _ensure_pkg_on_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.abspath(os.path.join(here, "..", ".."))
    if parent not in sys.path:
        sys.path.insert(0, parent)


def _truncate(s: str, n: int = 600) -> str:
    return s if len(s) <= n else s[:n] + " ...[truncated]"


def _print_record(rec: Dict[str, Any]) -> None:
    spec = rec.get("spec") or {}
    print("-" * 80)
    print(f"id: {rec.get('id')}  source: {rec.get('source','?')}  "
          f"status: {(rec.get('consistency') or {}).get('status', 'n/a')}")
    if spec:
        print(f"domain={spec.get('domain')}  task={spec.get('task')}  "
              f"policy={spec.get('essential_policy')}  subject={spec.get('subject')}")
        print(f"primary: {spec.get('primary_context')}")
        for tier in ("essential_info", "helpful_info", "nonessential_sensitive_info"):
            items = spec.get(tier) or []
            if items:
                print(f"  [{tier}]")
                for it in items:
                    extras = []
                    if it.get("source_subject"):
                        extras.append(f"subject={it['source_subject']}")
                    if it.get("recommended_action"):
                        extras.append(f"act={it['recommended_action']}")
                    print(f"    - ({it.get('attribute')}) {it.get('value')}"
                          + (f"   [{', '.join(extras)}]" if extras else ""))
    print(f"raw: {_truncate(rec.get('raw_prompt') or rec.get('first_user') or '')}")
    if rec.get("gold_reformulation"):
        print(f"gold: {_truncate(rec['gold_reformulation'])}")


def main() -> int:
    _ensure_pkg_on_path()
    p = argparse.ArgumentParser()
    p.add_argument("path")
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--has-ne", action="store_true",
                   help="only show rows whose unified spec has at least one non_essential entry")
    p.add_argument("--status", default=None, help="filter consistency.status")
    args = p.parse_args()

    rows: List[Dict[str, Any]] = []
    with open(args.path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if args.has_ne:
                ne = ((rec.get("spec") or {}).get("nonessential_sensitive_info") or [])
                if not ne:
                    continue
            if args.status and (rec.get("consistency") or {}).get("status") != args.status:
                continue
            rows.append(rec)

    print(f"matched: {len(rows)} rows in {args.path}")
    rng = random.Random(args.seed)
    sample = rows if len(rows) <= args.n else rng.sample(rows, args.n)
    for rec in sample:
        _print_record(rec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
