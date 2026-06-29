#!/usr/bin/env python3
"""Offline smoke test -- no network calls.

Verifies that taxonomy / value_bank / sampler / prompts / judge parser all
work together. Prints a few sample specs and what the generator/judge prompts
would look like.

Usage:
    python scripts/dryrun_offline.py --n 3
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from synth.judge import compute_consistency, parse_judge_output
from synth.prompts import (
    build_generator_messages,
    build_judge_messages,
    build_reformulator_messages,
)
from synth.sampler import Sampler, SamplerConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    sampler = Sampler(SamplerConfig(), random.Random(args.seed))
    for i in range(args.n):
        print("=" * 80)
        print(f"sample #{i+1}")
        spec = sampler.sample()
        print(json.dumps({
            "domain": spec.domain,
            "task": spec.task,
            "subject": spec.subject,
            "embedding_style": spec.embedding_style,
            "tone": spec.tone,
            "confusion_kind": spec.confusion_kind,
            "essential_info": [a.to_dict() for a in spec.essential_info],
            "nonessential_sensitive_info": [
                a.to_dict() for a in spec.nonessential_sensitive_info
            ],
        }, indent=2))

        msgs = build_generator_messages(spec)
        print("\n--- generator user prompt (truncated) ---")
        print(msgs[1]["content"][:600] + ("…" if len(msgs[1]["content"]) > 600 else ""))

        # Round-trip the consistency checker against a synthetic "perfect"
        # judge output to make sure the score == 1.
        fake_judge = {
            "primary_context": ["dummy"],
            "essential_attributes": [a.value for a in spec.essential_info],
            "nonessential_attributes": [a.value for a in spec.nonessential_sensitive_info],
        }
        cons = compute_consistency(spec, fake_judge)
        print(f"\nconsistency-vs-perfect-judge: status={cons.status} "
              f"E_recall={cons.essential_recall:.2f} NE_recall={cons.nonessential_recall:.2f}")

        # Show the judge prompt structure on a stub raw_prompt.
        stub_raw = "I am [STUB]. Please help with [STUB]."
        jmsgs = build_judge_messages(stub_raw)
        print("\n--- judge user prompt (head 200 chars) ---")
        print(jmsgs[1]["content"][:200] + "…")

        # Test parse_judge_output on a malformed sample.
        parsed = parse_judge_output(
            'Some preamble {"primary_context": ["x"], "essential_attributes": ["y"], '
            '"nonessential_attributes": ["z"]} trailing text'
        )
        assert parsed["essential_attributes"] == ["y"], parsed
        print("\nparse_judge_output: OK (handles preambles/trailers)")

    print("=" * 80)
    print("offline dryrun OK")


if __name__ == "__main__":
    main()
