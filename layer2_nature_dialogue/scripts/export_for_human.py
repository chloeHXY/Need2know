#!/usr/bin/env python
"""Export a sample of unified rows into a human-annotation worksheet.

The output JSONL has the unified fields plus blank ``review_*`` slots that a
human annotator should fill in. Two annotators per row + a third for tie-
breaks is the standard practice (see paper §5).

Usage::

    python nature_data_syn/scripts/export_for_human.py \
        --input nature_data_syn/data/final/wildchat_anchor.eval.jsonl \
        --n 120 \
        --output nature_data_syn/data/final/human_review_input.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from typing import Any, Dict, List


def _read(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _write(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _stratify(
    rows: List[Dict[str, Any]], n_target: int, seed: int = 0,
) -> List[Dict[str, Any]]:
    """Pick n_target rows with at least one example from every domain that has
    at least one row, then fill the rest by uniform sampling."""
    by_domain = defaultdict(list)
    for r in rows:
        d = ((r.get("spec") or {}).get("domain")) or "Other"
        by_domain[d].append(r)
    rng = random.Random(seed)
    chosen: List[Dict[str, Any]] = []
    for d, group in sorted(by_domain.items()):
        rng.shuffle(group)
        chosen.append(group[0])
    remaining = [r for r in rows if r not in chosen]
    rng.shuffle(remaining)
    chosen.extend(remaining[: max(0, n_target - len(chosen))])
    return chosen[:n_target]


def _build_review_skeleton(rec: Dict[str, Any]) -> Dict[str, Any]:
    spec = rec.get("spec") or {}
    spans_for_review = []
    for tier in ("essential_info", "helpful_info", "nonessential_sensitive_info"):
        for s in spec.get(tier, []) or []:
            spans_for_review.append({
                "tier_predicted": tier.replace("_info", "").replace("_sensitive", ""),
                "value":          s.get("value"),
                "attribute":      s.get("attribute"),
                "subject":        s.get("source_subject"),
                "necessity_predicted": s.get("necessity"),
                "review_necessity_correct": None,   # true | false | uncertain
                "review_necessity_correction": None,  # essential | helpful | non_essential
                "review_subject_correct": None,
                "review_notes": "",
            })
    return {
        "id": rec.get("id"),
        "source": rec.get("source"),
        "raw_prompt": rec.get("raw_prompt"),
        "primary_context_predicted": spec.get("primary_context"),
        "domain_predicted": spec.get("domain"),
        "task_predicted": spec.get("task"),
        "spans": spans_for_review,
        "review_missing_disclosure": [],   # filled by annotator: missed NE spans
        "review_over_label": [],           # filled by annotator: spans incorrectly flagged
        "review_reformulation_quality": {
            "privacy_score_1to5": None,
            "utility_score_1to5": None,
            "naturalness_1to5": None,
            "free_text": "",
        },
        "review_overall_agree": None,      # true | false
        "review_annotator_id": None,
        "gold_reformulation_predicted": rec.get("gold_reformulation"),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--n", type=int, default=120)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    rows = _read(args.input)
    sample = _stratify(rows, args.n, seed=args.seed)
    out = [_build_review_skeleton(r) for r in sample]
    _write(args.output, out)
    print(f"wrote {len(out)} review skeletons -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
