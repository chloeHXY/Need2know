"""Rewrite ``Question`` into ``Syn_Question`` using ``prompt2.py``.

Reads a labels JSONL file (e.g. produced by ``label.py``), feeds each
record's ``Question`` field into the rewriting prompt defined in
``prompt2.py``, and writes a new JSONL file where every original record
is preserved verbatim and additionally annotated with:

  * ``Syn_Question`` -- the rewritten question text (str).
  * ``syn_question_raw`` -- raw model output (kept for debugging).
  * ``syn_endpoint`` / ``syn_usage`` / ``syn_ok`` / ``syn_error``.

At the end we print the LLM usage & USD cost report and persist it
alongside the output JSONL as ``<output>.usage.json``.

Usage
-----

    # rewrite the first 100 questions in the labels file (concurrency 8)
    python -m data.o1.synthesize_question \\
        --input data/o1/labels/labels_gpt-4o_start0_n500_20260515_101049.jsonl \\
        --n 100

    # rewrite ALL records (n=-1 means "everything")
    python -m data.o1.synthesize_question --n -1

Environment
-----------
``ENV_VENUS_OPENAPI_SECRET_ID`` must be exported before running.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make the repo root importable so ``synth.llm_client`` resolves regardless
# of how this script is launched.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from synth.llm_client import (  # noqa: E402  (import after sys.path tweak)
    LLMClient,
    ModelEndpoint,
    format_usage_table,
)

# The rewriting prompt template (single ``{{Question}}`` placeholder).
from data.o1.prompt2 import input as PROMPT_TEMPLATE  # noqa: E402


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_INPUT = (
    Path(__file__).parent
    / "labels"
    / "labels_gpt-4o_start0_n500_20260515_101049.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "syn_questions"

# GPT-4o via the in-house Venus proxy. Same shape as ``label.py``.
DEFAULT_ENDPOINT = ModelEndpoint(
    name="gpt-4o",
    model="gpt-4o",
    provider="venus",
    base_url="http://v2.open.venus.oa.com/llmproxy/chat/completions",
    api_key_env="ENV_VENUS_OPENAPI_SECRET_ID",
    temperature=0.7,   # a touch of variety for the synthetic PII
    max_tokens=1200,
    weight=1.0,
    timeout=120.0,
)


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------

def render_prompt(question: str) -> str:
    """Substitute ``{{Question}}`` in the prompt2 template."""
    return PROMPT_TEMPLATE.replace("{{Question}}", str(question or ""))


# ---------------------------------------------------------------------------
# Output cleanup
# ---------------------------------------------------------------------------

def clean_model_output(text: str) -> str:
    """Strip stray markdown fences / leading 'Output:' lines from the model.

    The prompt explicitly says "Return only the rewritten question", but
    GPT models sometimes still wrap the answer in ``` fences or prepend a
    short header. This keeps the result usable downstream without
    discarding anything important.
    """
    if not text:
        return ""
    s = text.strip()
    # Strip fenced code blocks like ```text ... ``` or ``` ... ```.
    if s.startswith("```"):
        # remove first fence line
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[: -3]
        s = s.strip()
    # Drop a leading "Output:" / "Rewritten question:" preface, if any.
    for prefix in ("Output:", "OUTPUT:", "Rewritten question:", "Rewritten Question:"):
        if s.startswith(prefix):
            s = s[len(prefix):].lstrip(" \n\t-")
            break
    return s.strip()


# ---------------------------------------------------------------------------
# Per-item worker
# ---------------------------------------------------------------------------

async def rewrite_one(
    client: LLMClient,
    record: Dict[str, Any],
    pos: int,
    semaphore: asyncio.Semaphore,
) -> Dict[str, Any]:
    question = record.get("Question", "")
    user_prompt = render_prompt(question)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a careful medical question rewriting assistant. "
                "Follow the user's rules exactly and return only the "
                "rewritten question text, with no commentary or markdown."
            ),
        },
        {"role": "user", "content": user_prompt},
    ]
    out_record = dict(record)  # shallow copy; preserves all original fields
    async with semaphore:
        try:
            out = await client.chat(messages)
            raw_text = out.get("text", "") or ""
            syn_q = clean_model_output(raw_text)
            out_record["Syn_Question"] = syn_q
            out_record["syn_question_raw"] = raw_text
            out_record["syn_endpoint"] = out.get("endpoint")
            out_record["syn_usage"] = out.get("usage")
            out_record["syn_ok"] = bool(syn_q)
            out_record["syn_error"] = None if syn_q else "empty_output"
        except Exception as exc:  # noqa: BLE001
            out_record["Syn_Question"] = None
            out_record["syn_question_raw"] = None
            out_record["syn_endpoint"] = None
            out_record["syn_usage"] = None
            out_record["syn_ok"] = False
            out_record["syn_error"] = f"{type(exc).__name__}: {exc}"
    out_record["_pos"] = pos
    return out_record


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(
                    f"[syn] WARN: skipping malformed line {ln}: {e}",
                    file=sys.stderr,
                )
    return out


async def run(
    input_path: Path,
    output_path: Path,
    n: int,
    start: int,
    concurrency: int,
    model: str,
    provider: str,
    base_url: Optional[str],
    api_key_env: Optional[str],
    temperature: float,
    max_tokens: int,
) -> None:
    # ---- load dataset -----------------------------------------------------
    records = load_jsonl(input_path)
    total = len(records)
    end = min(total, start + n) if n > 0 else total
    records_slice = records[start:end]
    print(
        f"[syn] input={input_path.name} total={total} "
        f"slice=[{start}:{end}) -> rewriting {len(records_slice)} items "
        f"with model={model} provider={provider} concurrency={concurrency}",
        flush=True,
    )
    if not records_slice:
        print("[syn] nothing to do.", flush=True)
        return

    # ---- build the LLM client --------------------------------------------
    ep = ModelEndpoint(
        name=model,
        model=model,
        provider=provider,
        base_url=base_url or DEFAULT_ENDPOINT.base_url,
        api_key_env=api_key_env or DEFAULT_ENDPOINT.api_key_env,
        temperature=temperature,
        max_tokens=max_tokens,
        weight=1.0,
        timeout=180.0,
    )
    client = LLMClient([ep], max_retries=5, retry_base_delay=1.0)

    # ---- launch all tasks concurrently (bounded by semaphore) -------------
    sem = asyncio.Semaphore(max(1, concurrency))
    tasks = [
        asyncio.create_task(rewrite_one(client, rec, start + i, sem))
        for i, rec in enumerate(records_slice)
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    ok_count = 0
    fail_count = 0
    # Collect results then re-sort by original position to keep the output
    # order stable (asyncio.as_completed gives whichever finishes first).
    results: List[Dict[str, Any]] = []
    try:
        for fut in asyncio.as_completed(tasks):
            rec = await fut
            results.append(rec)
            if rec.get("syn_ok"):
                ok_count += 1
            else:
                fail_count += 1
            done = ok_count + fail_count
            if done % 10 == 0 or done == len(records_slice):
                print(
                    f"[syn] {done}/{len(records_slice)} done "
                    f"(ok={ok_count}, fail={fail_count})",
                    flush=True,
                )
    finally:
        await client.aclose()

    results.sort(key=lambda r: r.get("_pos", 0))
    with output_path.open("w", encoding="utf-8") as fout:
        for rec in results:
            rec.pop("_pos", None)
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")

    dt = time.time() - t0
    print(
        f"[syn] finished in {dt:.1f}s -> {output_path} "
        f"(ok={ok_count}, fail={fail_count})",
        flush=True,
    )

    # ---- LLM usage & cost report -----------------------------------------
    usage = client.usage_summary()
    print("\n=== LLM usage & cost ===")
    print(format_usage_table(usage))
    usage_path = output_path.with_suffix(".usage.json")
    with usage_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "model": model,
                "provider": provider,
                "input": str(input_path),
                "output": str(output_path),
                "n_requested": len(records_slice),
                "n_ok": ok_count,
                "n_fail": fail_count,
                "elapsed_seconds": round(dt, 2),
                "usage": usage,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"[syn] usage report written to {usage_path}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Rewrite the `Question` field of a labels JSONL file into "
            "`Syn_Question` using prompt2.py, and write a new JSONL."
        )
    )
    p.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help=f"Input labels JSONL. Default: {DEFAULT_INPUT}",
    )
    p.add_argument(
        "--output", type=Path, default=None,
        help=(
            "Output JSONL path. Default: "
            f"{DEFAULT_OUTPUT_DIR}/syn_<input-stem>_n<N>_<timestamp>.jsonl"
        ),
    )
    p.add_argument(
        "--n", type=int, required=True,
        help="Number of items to rewrite this run (use -1 for all).",
    )
    p.add_argument(
        "--start", type=int, default=0,
        help="Start index into the input JSONL (default: 0).",
    )
    p.add_argument(
        "--concurrency", type=int, default=8,
        help="Max concurrent in-flight requests (default: 8).",
    )
    # Model / endpoint knobs.
    p.add_argument("--model", default="gpt-4o")
    p.add_argument(
        "--provider", default="venus", choices=["venus", "openai"],
    )
    p.add_argument("--base-url", default=None)
    p.add_argument("--api-key-env", default=None)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=1200)
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.output is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        n_tag = "all" if args.n is None or args.n < 0 else str(args.n)
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        args.output = DEFAULT_OUTPUT_DIR / (
            f"syn_{args.input.stem}_start{args.start}_n{n_tag}_{ts}.jsonl"
        )

    key_env = args.api_key_env or DEFAULT_ENDPOINT.api_key_env
    if not os.environ.get(key_env):
        print(
            f"[syn] ERROR: env var {key_env} is not set. "
            "Export it (e.g. ENV_VENUS_OPENAPI_SECRET_ID) and retry.",
            file=sys.stderr,
        )
        sys.exit(2)

    asyncio.run(
        run(
            input_path=args.input,
            output_path=args.output,
            n=args.n,
            start=args.start,
            concurrency=args.concurrency,
            model=args.model,
            provider=args.provider,
            base_url=args.base_url,
            api_key_env=args.api_key_env,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    )


if __name__ == "__main__":
    main()
