#!/usr/bin/env python3
"""Main entry point for Layer 1 reverse synthesis.

Usage:
    python scripts/run_synth.py --config config/default.yaml --n 1000 --output data/v1.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
import time
from pathlib import Path

# Make ``synth`` importable when invoking the script directly.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # type: ignore

from synth.llm_client import (
    build_client_from_config,
    format_usage_table,
    merge_usage_summaries,
    build_embedding_client_from_config
)
from synth.pipeline import Pipeline, PipelineConfig
from synth.sampler import Sampler, SamplerConfig

def _load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _make_sampler(cfg: dict, seed: int) -> Sampler:
    s = cfg.get("sampling", {}) or {}
    return Sampler(
        SamplerConfig(
            num_essential_min=s.get("num_essential_min", 1),
            num_essential_max=s.get("num_essential_max", 2),
            num_nonessential_min=s.get("num_nonessential_min", 1),
            num_nonessential_max=s.get("num_nonessential_max", 4),
            confusion_rate=s.get("confusion_rate", 0.15),
            style_weights=s.get("style_weights"),
            subject_weights=s.get("subject_weights"),
            tone_weights=s.get("tone_weights"),
            domain_weights=s.get("domain_weights"),
            task_weights=s.get("task_weights"),
        ),
        rng=random.Random(seed),
    )


def _make_pipeline_config(cfg: dict) -> PipelineConfig:
    p = cfg.get("pipeline", {}) or {}
    return PipelineConfig(
        concurrency=p.get("concurrency", 16),
        write_soft_fail=p.get("write_soft_fail", True),
        write_hard_fail=p.get("write_hard_fail", False),
        judge_use_json_mode=p.get("judge_use_json_mode", True),
        pass_threshold=p.get("pass_threshold", 0.8),
        soft_fail_threshold=p.get("soft_fail_threshold", 0.5),
        max_generation_retries=p.get("max_generation_retries", 2),
        generator_temperature=p.get("generator_temperature"),
        reformulator_temperature=p.get("reformulator_temperature", 0.3),
        judge_temperature=p.get("judge_temperature", 0.0),
        matcher_token_threshold=p.get("matcher_token_threshold", 0.5),
        matcher_cosine_threshold=p.get("matcher_cosine_threshold", 0.65),
    )


async def amain() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="./layer1_reverse_synthesis/config/default.yaml")
    ap.add_argument("--n", type=int, default=1, help="number of samples")
    ap.add_argument("--output", default="./layer1_reverse_synthesis/data/v1.jsonl", help="output JSONL path")
    ap.add_argument("--start-idx", type=int, default=0)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    cfg = _load_yaml(args.config)

    sampler = _make_sampler(cfg, args.seed)
    generator = build_client_from_config(cfg["generator"])
    reformulator = build_client_from_config(cfg["reformulator"])
    judge = build_client_from_config(cfg["judge"])
    embedder = build_embedding_client_from_config(cfg.get("embeddings"))
    pcfg = _make_pipeline_config(cfg)

    pipe = Pipeline(sampler, generator, reformulator, judge, pcfg, embedder=embedder)
    if embedder is None:
        print("[info] embedding fallback disabled "
              "(judge consistency uses token-overlap only)", flush=True)
    else:
        print(f"[info] embedding fallback enabled: model={cfg['embeddings']['model']}", flush=True)


    t0 = time.time()
    last_print = t0

    counters: dict = {"PASS": 0, "SOFT_FAIL": 0, "HARD_FAIL": 0, "ERROR": 0, "DROPPED": 0}

    def progress(counters):
        nonlocal last_print
        now = time.time()
        if now - last_print < 2.0:
            return
        last_print = now
        total = sum(counters.values())
        elapsed = now - t0
        rate = total / max(1e-6, elapsed)
        eta = (args.n - total) / max(1e-6, rate)
        print(
            f"[{total}/{args.n}] PASS={counters['PASS']} "
            f"SOFT={counters['SOFT_FAIL']} HARD={counters['HARD_FAIL']} "
            f"ERR={counters['ERROR']} DROP={counters['DROPPED']} "
            f"({rate:.2f}/s, ETA {eta/60:.1f}m)",
            flush=True,
        )

    try:
        counters = await pipe.run(
            args.n, args.output, start_idx=args.start_idx, on_progress=progress
        )
    finally:
        # Snapshot token/$ usage *before* closing clients (aclose only closes
        # the underlying httpx session; usage dict itself persists, but we
        # collect here to be safe and to still print on crash).
        usage = merge_usage_summaries([
            ("generator", generator),
            ("reformulator", reformulator),
            ("judge", judge),
        ])
        await generator.aclose()
        await reformulator.aclose()
        await judge.aclose()
        if embedder is not None:
            await embedder.aclose()

    elapsed = time.time() - t0
    print()
    print(f"=== Layer-1 synthesis done in {elapsed:.1f}s ===")
    for k, v in counters.items():
        print(f"  {k:>10}: {v}")
    print(f"  output : {os.path.abspath(args.output)}")
    print()
    print("=== LLM usage & cost ===")
    print(format_usage_table(usage))


if __name__ == "__main__":
    asyncio.run(amain())
