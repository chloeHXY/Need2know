#!/usr/bin/env python3
"""Pretty-print random samples from a Layer 1 JSONL file (with ANSI colour).

Usage:
    python scripts/inspect_samples.py data/v1.jsonl --n 5
    python scripts/inspect_samples.py data/v1.jsonl --status SOFT_FAIL --n 10
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from typing import List, Optional


# ---- ANSI helpers ----------------------------------------------------------

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def colour(text: str, c: str) -> str:
    return f"{c}{text}{RESET}"


def highlight(prompt: str, essential: List[str], nonessential: List[str]) -> str:
    """Crude highlighter: paint essential values green, NE values red."""
    out = prompt
    # Sort by length desc so longer matches don't get gobbled by shorter ones.
    for v in sorted(set(nonessential), key=len, reverse=True):
        if v and v in out:
            out = out.replace(v, colour(v, RED + BOLD))
    for v in sorted(set(essential), key=len, reverse=True):
        if v and v in out:
            out = out.replace(v, colour(v, GREEN + BOLD))
    return out


def render(rec: dict) -> str:
    if "error" in rec:
        return f"{RED}ERROR{RESET}  {rec.get('id','?')}  {rec['error']}"

    spec = rec["spec"]
    cons = rec["consistency"]
    e_vals = [a["value"] for a in spec["essential_info"]]
    ne_vals = [a["value"] for a in spec["nonessential_sensitive_info"]]

    status_colour = {"PASS": GREEN, "SOFT_FAIL": YELLOW, "HARD_FAIL": RED}.get(
        cons["status"], DIM
    )

    lines = []
    lines.append(
        f"{BOLD}── {rec['id']} ──{RESET}  "
        f"{status_colour}{cons['status']}{RESET}  "
        f"E_recall={cons['essential_recall']:.2f}  "
        f"NE_recall={cons['nonessential_recall']:.2f}  "
        f"{DIM}({spec['domain']}/{spec['task']}, {spec['embedding_style']}, {spec['tone']}, "
        f"subj={spec['subject']}{', conf=' + spec['confusion_kind'] if spec.get('confusion_kind') else ''})"
        f"{RESET}"
    )
    lines.append(f"  {colour('essential', GREEN + BOLD)} :")
    for a in spec["essential_info"]:
        lines.append(f"    - [{a['attribute']}] {a['value']}")
    lines.append(f"  {colour('nonessential', RED + BOLD)} :")
    for a in spec["nonessential_sensitive_info"]:
        lines.append(f"    - [{a['attribute']}] {a['value']}")
    lines.append("")
    lines.append(f"  {BOLD}raw_prompt:{RESET}")
    lines.append("    " + highlight(rec["raw_prompt"], e_vals, ne_vals).replace("\n", "\n    "))
    lines.append("")
    lines.append(f"  {BOLD}gold_reformulation:{RESET}")
    lines.append(f"    {CYAN}{rec['gold_reformulation']}{RESET}")

    je = rec["judge_out"].get("essential_attributes", [])
    jne = rec["judge_out"].get("nonessential_attributes", [])
    extras = cons.get("extra_nonessential", [])
    lines.append("")
    lines.append(f"  {DIM}judge.E:  {je}{RESET}")
    lines.append(f"  {DIM}judge.NE: {jne}{RESET}")
    if extras:
        lines.append(f"  {DIM}extra NE found by judge: {extras}{RESET}")
    if cons.get("essential_misses"):
        lines.append(f"  {YELLOW}E missed by judge: {cons['essential_misses']}{RESET}")
    if cons.get("nonessential_misses"):
        lines.append(f"  {YELLOW}NE missed by judge: {cons['nonessential_misses']}{RESET}")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--status", choices=["PASS", "SOFT_FAIL", "HARD_FAIL", "ERROR"], default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rows = []
    with open(args.path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if args.status:
                if args.status == "ERROR" and "error" not in rec:
                    continue
                if args.status != "ERROR" and rec.get("consistency", {}).get("status") != args.status:
                    continue
            rows.append(rec)

    if not rows:
        print("(no rows match)", file=sys.stderr)
        return

    rng = random.Random(args.seed)
    sample = rows if len(rows) <= args.n else rng.sample(rows, args.n)
    for i, rec in enumerate(sample):
        if i:
            print()
        print(render(rec))


if __name__ == "__main__":
    main()
