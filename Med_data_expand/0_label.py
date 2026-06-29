"""Annotate ``medical_o1_sft_mcq.json`` with key-evidence-span labels.

For each item in the input dataset (which has the fields ``Question``,
``Complex_CoT`` and ``Response``), we:

  1. Render the prompt template from ``prompt.py`` with the three fields.
  2. Call GPT-4o (default, via the in-house Venus LLM proxy) to produce a
     JSON labelling object (``answer_summary`` + ``key_spans`` + ...).
  3. Parse the model output and append a record to a JSONL output file.
  4. At the end of the run, print a per-endpoint LLM usage & USD cost
     table using the bookkeeping built into ``synth.llm_client.LLMClient``.

Usage
-----

    # label the first 50 items, with 8 in-flight requests at a time
    python -m data.o1.label --n 50 --concurrency 8

    # label items [100, 200) instead of starting from 0
    python -m data.o1.label --n 100 --start 100

Environment
-----------
``ENV_VENUS_OPENAPI_SECRET_ID`` must be exported before running:

    export ENV_VENUS_OPENAPI_SECRET_ID=<your venus openapi secret id>

    修改该脚本，从/group/40047/eiraxyhuang/workspace/fc/DataG/Med_data_expand/medical_o1_sft_mcq.json捞取1000条数据进行annotate，但注意不能在/group/40047/eiraxyhuang/workspace/fc/DataG/Med_data_expand/labels_gpt-4o_start0_n500_20260515_101049.jsonl出现过
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make the repo root importable so ``synth.llm_client`` resolves regardless
# of how this script is launched (``python data/o1/label.py`` works too).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

sys.path.insert(
    0,
    "/group/40047/eiraxyhuang/workspace/fc/DataG/layer1_reverse_synthesis",
)
from synth.llm_client import (  # noqa: E402  (import after sys.path tweak)
    LLMClient,
    ModelEndpoint,
    format_usage_table,
)

# The prompt template file defines a module-level ``input`` string with
# ``{{Question}}``, ``{{Complex_CoT}}`` and ``{{Response}}`` placeholders.
from data.o1.prompt import input as PROMPT_TEMPLATE  # noqa: E402


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_INPUT = Path(__file__).parent / "medical_o1_sft_mcq.json"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "labels"

# When --exclude is not provided on the CLI, we still skip any items that
# already appear in the labels produced by previous runs sitting next to the
# input file (e.g. ``labels_gpt-4o_start0_n500_20260515_101049.jsonl``).
DEFAULT_EXCLUDE_FILES: List[Path] = [
    Path(__file__).parent
    / "labels_gpt-4o_start0_n500_20260515_101049.jsonl",
]

# GPT-4o via the in-house Venus proxy. Same endpoint shape as
# ``config/default.yaml``. If you want to point at the public OpenAI API
# instead, set provider="openai" and base_url="https://api.openai.com/v1".
DEFAULT_ENDPOINT = ModelEndpoint(
    name="gpt-4o",
    model="gpt-4o",
    provider="venus",
    base_url="http://v2.open.venus.oa.com/llmproxy/chat/completions",
    api_key_env="ENV_VENUS_OPENAPI_SECRET_ID",
    temperature=0.0,
    max_tokens=1200,
    weight=1.0,
    timeout=120.0,
)


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------

def render_prompt(item: Dict[str, Any]) -> str:
    """Substitute the three ``{{...}}`` placeholders in the prompt template."""
    return (
        PROMPT_TEMPLATE
        .replace("{{Question}}", str(item.get("Question", "")))
        .replace("{{Complex_CoT}}", str(item.get("Complex_CoT", "")))
        .replace("{{Response}}", str(item.get("Response", "")))
    )


# ---------------------------------------------------------------------------
# Robust JSON extraction (the prompt asks for "Output only ... JSON" but
# models occasionally wrap it in ```json fences or add a trailing comment).
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_label_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    candidates: List[str] = []
    m = _JSON_FENCE_RE.search(text)
    if m:
        candidates.append(m.group(1))
    candidates.append(text)
    m2 = _JSON_OBJECT_RE.search(text)
    if m2:
        candidates.append(m2.group(0))
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


# ---------------------------------------------------------------------------
# Exclusion handling: collect the set of already-labelled items so that we
# don't waste tokens (and money) re-annotating them.
# ---------------------------------------------------------------------------

def load_excluded_keys(
    exclude_paths: List[Path],
) -> tuple[set[int], set[str]]:
    """Return ``(excluded_indices, excluded_questions)`` from JSONL files.

    We dedupe on two keys:
      * ``index`` (fast path, only valid if the input dataset hasn't been
        reordered between runs);
      * ``Question`` text (robust to reorderings of the input array).
    """
    excluded_idx: set[int] = set()
    excluded_q: set[str] = set()
    for p in exclude_paths:
        if not p.exists():
            print(f"[label] exclude file not found, skipping: {p}", flush=True)
            continue
        n_lines = 0
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict):
                    continue
                idx = rec.get("index")
                if isinstance(idx, int):
                    excluded_idx.add(idx)
                q = rec.get("Question")
                if isinstance(q, str) and q:
                    excluded_q.add(q)
                n_lines += 1
        print(
            f"[label] loaded {n_lines} excluded records from {p.name}",
            flush=True,
        )
    return excluded_idx, excluded_q


# ---------------------------------------------------------------------------
# Per-item worker
# ---------------------------------------------------------------------------

async def label_one(
    client: LLMClient,
    item: Dict[str, Any],
    idx: int,
    semaphore: asyncio.Semaphore,
) -> Dict[str, Any]:
    user_prompt = render_prompt(item)
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert in medical exam question analysis and "
                "evidence-span annotation. Output ONLY the requested JSON "
                "object, with no surrounding prose or markdown fences."
            ),
        },
        {"role": "user", "content": user_prompt},
    ]
    async with semaphore:
        try:
            out = await client.chat(
                messages,
                response_format={"type": "json_object"},
            )
            raw_text = out.get("text", "")
            label = parse_label_json(raw_text)
            return {
                "index": idx,
                "Question": item.get("Question"),
                "Complex_CoT": item.get("Complex_CoT"),
                "Response": item.get("Response"),
                "label": label,
                "label_raw": raw_text,
                "endpoint": out.get("endpoint"),
                "usage": out.get("usage"),
                "ok": label is not None,
                "error": None if label is not None else "json_parse_failed",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "index": idx,
                "Question": item.get("Question"),
                "Complex_CoT": item.get("Complex_CoT"),
                "Response": item.get("Response"),
                "label": None,
                "label_raw": None,
                "endpoint": None,
                "usage": None,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

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
    exclude_paths: Optional[List[Path]] = None,
) -> None:
    # ---- load dataset -----------------------------------------------------
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{input_path} must contain a JSON array")
    total = len(data)

    # ---- load exclusion set ----------------------------------------------
    excluded_idx, excluded_q = load_excluded_keys(exclude_paths or [])
    n_excluded = len(excluded_idx) + len(excluded_q)
    if n_excluded:
        print(
            f"[label] exclusion: {len(excluded_idx)} indices, "
            f"{len(excluded_q)} unique questions to skip",
            flush=True,
        )

    # ---- select the next ``n`` items, scanning from ``start`` and skipping
    #      any item already present in the exclusion set ------------------
    items: List[Dict[str, Any]] = []
    item_indices: List[int] = []
    n_skipped = 0
    target = n if n is not None and n > 0 else total
    cursor = start
    while cursor < total and len(items) < target:
        it = data[cursor]
        q = it.get("Question") if isinstance(it, dict) else None
        if cursor in excluded_idx or (isinstance(q, str) and q in excluded_q):
            n_skipped += 1
        else:
            items.append(it)
            item_indices.append(cursor)
        cursor += 1
    end = cursor  # one past the last index we actually scanned

    print(
        f"[label] dataset={input_path.name} total={total} "
        f"scanned=[{start}:{end}) skipped_already_labelled={n_skipped} "
        f"-> labeling {len(items)} items "
        f"with model={model} provider={provider} concurrency={concurrency}",
        flush=True,
    )
    if len(items) < target:
        print(
            f"[label] WARNING: requested {target} items but only "
            f"{len(items)} new (un-excluded) items remain in the dataset "
            f"from start={start}.",
            flush=True,
        )
    if not items:
        print("[label] nothing to do.", flush=True)
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
        asyncio.create_task(label_one(client, it, item_indices[i], sem))
        for i, it in enumerate(items)
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    ok_count = 0
    fail_count = 0
    try:
        with output_path.open("w", encoding="utf-8") as fout:
            for fut in asyncio.as_completed(tasks):
                rec = await fut
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fout.flush()
                if rec.get("ok"):
                    ok_count += 1
                else:
                    fail_count += 1
                done = ok_count + fail_count
                if done % 10 == 0 or done == len(items):
                    print(
                        f"[label] {done}/{len(items)} done "
                        f"(ok={ok_count}, fail={fail_count})",
                        flush=True,
                    )
    finally:
        await client.aclose()

    dt = time.time() - t0
    print(
        f"[label] finished in {dt:.1f}s -> {output_path} "
        f"(ok={ok_count}, fail={fail_count})",
        flush=True,
    )

    # ---- LLM usage & cost report -----------------------------------------
    usage = client.usage_summary()
    print("\n=== LLM usage & cost ===")
    print(format_usage_table(usage))
    # Also persist the usage report next to the JSONL output for later
    # auditing.
    usage_path = output_path.with_suffix(".usage.json")
    with usage_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "model": model,
                "provider": provider,
                "n_requested": len(items),
                "n_ok": ok_count,
                "n_fail": fail_count,
                "elapsed_seconds": round(dt, 2),
                "usage": usage,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"[label] usage report written to {usage_path}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Annotate medical_o1_sft_mcq.json with key-evidence spans."
    )
    p.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help=f"Path to input JSON. Default: {DEFAULT_INPUT}",
    )
    p.add_argument(
        "--output", type=Path, default=None,
        help=(
            "Output JSONL path. Default: "
            f"{DEFAULT_OUTPUT_DIR}/labels_<model>_n<N>_<timestamp>.jsonl"
        ),
    )
    p.add_argument(
        "--n", type=int, required=True,
        help="Number of items to label this run (use -1 for all).",
    )
    p.add_argument(
        "--start", type=int, default=0,
        help="Start index into the input array (default: 0).",
    )
    p.add_argument(
        "--concurrency", type=int, default=8,
        help="Max concurrent in-flight requests (default: 8).",
    )
    # Model / endpoint knobs (defaults match config/default.yaml judge stage).
    p.add_argument("--model", default="gpt-4o")
    p.add_argument(
        "--provider", default="venus", choices=["venus", "openai"],
    )
    p.add_argument("--base-url", default=None)
    p.add_argument("--api-key-env", default=None)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max-tokens", type=int, default=1200)
    p.add_argument(
        "--exclude", type=Path, action="append", default=None,
        help=(
            "Path(s) to existing labels JSONL file(s) whose items should be "
            "skipped (matched by ``index`` and ``Question``). Can be passed "
            "multiple times. Defaults to "
            f"{[str(p) for p in DEFAULT_EXCLUDE_FILES]}."
        ),
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # Default output filename if user didn't pass --output.
    if args.output is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        n_tag = "all" if args.n is None or args.n < 0 else str(args.n)
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        args.output = DEFAULT_OUTPUT_DIR / (
            f"labels_{args.model}_start{args.start}_n{n_tag}_{ts}.jsonl"
        )

    # Sanity check: the API key env var must be set before we make any call.
    key_env = args.api_key_env or DEFAULT_ENDPOINT.api_key_env
    if not os.environ.get(key_env):
        print(
            f"[label] ERROR: env var {key_env} is not set. "
            "Export it (e.g. ENV_VENUS_OPENAPI_SECRET_ID) and retry.",
            file=sys.stderr,
        )
        sys.exit(2)

    exclude_paths = (
        args.exclude if args.exclude is not None else list(DEFAULT_EXCLUDE_FILES)
    )

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
            exclude_paths=exclude_paths,
        )
    )


if __name__ == "__main__":
    main()
