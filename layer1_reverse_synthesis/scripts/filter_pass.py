#!/usr/bin/env python3
"""Filter a Layer 1 JSONL dataset, keeping only samples that passed judging.

By default, a sample is kept iff ``consistency.status == "PASS"``. You can
broaden the set of accepted statuses (e.g. include ``SOFT_FAIL``) or enforce
minimum essential / non-essential recall thresholds.

Examples:
    # Keep only PASS rows -> data/smoke.pass.jsonl
    python scripts/filter_pass.py data/smoke.jsonl

    # Explicit output path
    python scripts/filter_pass.py data/smoke.jsonl -o data/smoke.pass.jsonl

    # Keep PASS and SOFT_FAIL, and require essential_recall >= 1.0
    python scripts/filter_pass.py data/smoke.jsonl \
        --status PASS SOFT_FAIL --min-essential-recall 1.0

    # Print the kept rows to stdout instead of writing a file
    python scripts/filter_pass.py data/smoke.jsonl --stdout
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Set


def _iter_rows(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[warn] skip malformed line {lineno}: {e}", file=sys.stderr)


def _keep(
    row: dict,
    accepted: Set[str],
    min_e_recall: float,
    min_ne_recall: float,
) -> bool:
    if "error" in row:
        return False
    cons = row.get("consistency")
    if not isinstance(cons, dict):
        return False
    if cons.get("status") not in accepted:
        return False
    if float(cons.get("essential_recall", 0.0)) < min_e_recall:
        return False
    if float(cons.get("nonessential_recall", 0.0)) < min_ne_recall:
        return False
    return True


def _default_output(inp: Path) -> Path:
    # data/foo.jsonl -> data/foo.pass.jsonl
    return inp.with_suffix("").with_name(inp.stem + ".pass").with_suffix(".jsonl")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", type=Path, help="Input JSONL file")
    ap.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output JSONL path (default: <input_stem>.pass.jsonl beside the input)",
    )
    ap.add_argument(
        "--status", nargs="+", default=["PASS"],
        help="Accepted consistency.status values (default: PASS)",
    )
    ap.add_argument(
        "--min-essential-recall", type=float, default=0.0,
        help="Drop rows with essential_recall below this value (default: 0.0)",
    )
    ap.add_argument(
        "--min-nonessential-recall", type=float, default=0.0,
        help="Drop rows with nonessential_recall below this value (default: 0.0)",
    )
    ap.add_argument(
        "--stdout", action="store_true",
        help="Write kept rows to stdout instead of a file",
    )
    args = ap.parse_args()

    if not args.input.exists():
        print(f"[error] input not found: {args.input}", file=sys.stderr)
        sys.exit(2)

    accepted: Set[str] = {s.upper() for s in args.status}

    kept: List[dict] = []
    total = 0
    err = 0
    status_counts: dict = {}

    for row in _iter_rows(args.input):
        total += 1
        if "error" in row:
            err += 1
            continue
        status = (row.get("consistency") or {}).get("status", "—")
        status_counts[status] = status_counts.get(status, 0) + 1
        if _keep(row, accepted,
                 args.min_essential_recall,
                 args.min_nonessential_recall):
            kept.append(row)

    if args.stdout:
        for r in kept:
            sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n")
    else:
        out = args.output or _default_output(args.input)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            for r in kept:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[ok] wrote {len(kept)} / {total} rows -> {out}", file=sys.stderr)

    # Always print a short summary on stderr so it survives --stdout piping.
    print(f"[summary] total={total} errored={err} kept={len(kept)} "
          f"accepted={sorted(accepted)} "
          f"min_e_recall={args.min_essential_recall} "
          f"min_ne_recall={args.min_nonessential_recall}",
          file=sys.stderr)
    if status_counts:
        mix = ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items()))
        print(f"[status mix] {mix}", file=sys.stderr)


if __name__ == "__main__":
    main()
