# -*- coding: utf-8 -*-
"""
LLM-as-Judge inference using gpt-4o-mini (Venus proxy).

Inputs (under /group/40047/eiraxyhuang/workspace/fc/DataG/llm_test_data/):
    - our.parquet
    - papillon.parquet
    - prediax.parquet

For every row, build a judge prompt using:
    - system_prompt = contents of /group/40047/eiraxyhuang/workspace/fc/DataG/judge_prompt.md
    - user message  = JSON payload with {question, priv_query, ne_items, ea_items}
        - question        : extra_info["question"]
        - priv_query      : row["priv_query"]
        - ne_items        : extra_info["ne"]   (list of non-essential / sensitive items)
        - ea_items        : extra_info["ea"]   (list of essential attributes)

Call gpt-4o-mini via the Venus LLM proxy (see examples/formal.py).
Parse the returned JSON and store both the structured fields and the raw
output as new columns. Writes to <name>_judged.parquet alongside the input.

Usage:
    # All three files, default 16 workers
    python 0_judge_gpt4o_mini.py

    # Single file / quick smoke test
    python 0_judge_gpt4o_mini.py --inputs our.parquet --limit 10

    # More workers, force re-run
    python 0_judge_gpt4o_mini.py --workers 32 --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Paths / config
# ---------------------------------------------------------------------------
DATA_DIR = Path("/group/40047/eiraxyhuang/workspace/fc/DataG/llm_test_data")
PROMPT_PATH = Path("/group/40047/eiraxyhuang/workspace/fc/DataG/judge_prompt.md")

DEFAULT_INPUTS = ["our.parquet", "papillon.parquet", "prediax.parquet"]

VENUS_URL = "http://v2.open.venus.oa.com/llmproxy/chat/completions"
MODEL_NAME = "gpt-4o-mini"

# USD per 1M tokens (gpt-4o-mini)
PRICE_INPUT_PER_MTOK = 0.15
PRICE_OUTPUT_PER_MTOK = 0.60

# Concurrency / generation
DEFAULT_WORKERS = 32
MAX_RETRIES = 3
REQUEST_TIMEOUT = 120
TEMPERATURE = 0.6

OUTPUT_SUFFIX = "_judged.parquet"

# Columns added to the output parquet.
COL_RAW = "judge_raw"
COL_PARSED = "judge_parsed"
COL_VERDICT = "judge_verdict"
COL_REID = "judge_reid_risk"
COL_UTIL = "judge_utility_score"
COL_CONF = "judge_confidence"
COL_OK = "judge_ok"
COL_ERR = "judge_error"
COL_USAGE = "judge_usage"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def build_token() -> str:
    sid = os.environ.get("ENV_VENUS_OPENAPI_SECRET_ID")
    if not sid:
        raise RuntimeError(
            "Environment variable ENV_VENUS_OPENAPI_SECRET_ID is not set; "
            "cannot call the Venus LLM proxy."
        )
    return f"{sid}@5325"


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------
def _to_str_list(v: Any) -> List[str]:
    if v is None:
        return []
    # Numpy arrays, pandas arrays, tuples -> list
    try:
        seq = list(v)
    except TypeError:
        return [str(v)]
    out: List[str] = []
    for x in seq:
        if x is None:
            continue
        s = str(x).strip()
        if s:
            out.append(s)
    return out


def extract_fields(row: pd.Series) -> Dict[str, Any]:
    """Extract question / priv_query / ne / ea from a row."""
    extra = row.get("extra_info") or {}
    if not isinstance(extra, dict):
        # Some parquet readers return a Mapping-like; coerce defensively.
        try:
            extra = dict(extra)
        except Exception:
            extra = {}

    question = extra.get("question") or ""
    priv_query = row.get("priv_query") or ""
    ne_items = _to_str_list(extra.get("ne"))
    ea_items = _to_str_list(extra.get("ea"))

    return {
        "question": str(question),
        "priv_query": str(priv_query),
        "ne_items": ne_items,
        "ea_items": ea_items,
    }


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
def load_system_prompt() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    if not text.strip():
        raise RuntimeError(f"Empty prompt file: {PROMPT_PATH}")
    return text


def build_messages(system_prompt: str, fields: Dict[str, Any]) -> List[Dict[str, str]]:
    user_payload = {
        "question": fields["question"],
        "priv_query": fields["priv_query"],
        "ne_items": fields["ne_items"],
        "ea_items": fields["ea_items"],
    }
    user_text = (
        "Evaluate the following privacy rewrite. "
        "Return ONLY the JSON object specified in the system instructions.\n\n"
        + json.dumps(user_payload, ensure_ascii=False, indent=2)
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Usage stats
# ---------------------------------------------------------------------------
class UsageStats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def add(self, usage: Optional[Dict[str, Any]]) -> None:
        if not usage:
            return
        pt = int(usage.get("prompt_tokens", 0) or 0)
        ct = int(usage.get("completion_tokens", 0) or 0)
        tt = int(usage.get("total_tokens", 0) or (pt + ct))
        with self._lock:
            self.calls += 1
            self.prompt_tokens += pt
            self.completion_tokens += ct
            self.total_tokens += tt

    def cost_usd(self) -> float:
        return (
            self.prompt_tokens * PRICE_INPUT_PER_MTOK / 1_000_000.0
            + self.completion_tokens * PRICE_OUTPUT_PER_MTOK / 1_000_000.0
        )

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "calls": self.calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
                "cost_usd": round(self.cost_usd(), 6),
            }

    def format_line(self) -> str:
        s = self.snapshot()
        return (
            f"calls={s['calls']} in={s['prompt_tokens']} "
            f"out={s['completion_tokens']} total={s['total_tokens']} "
            f"cost=${s['cost_usd']:.4f}"
        )


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------
def call_llm(
    messages: List[Dict[str, str]],
    *,
    token: str,
    use_json_mode: bool = True,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """Call gpt-4o-mini via Venus proxy.

    Returns ``(parsed_json, raw_text, usage, error)``.
    """
    payload: Dict[str, Any] = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": TEMPERATURE,
    }
    if use_json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    last_err: Optional[str] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                VENUS_URL,
                headers=headers,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                last_err = f"http {resp.status_code}: {resp.text[:300]}"
            else:
                data = resp.json()
                usage = data.get("usage") if isinstance(data, dict) else None
                try:
                    content = data["choices"][0]["message"]["content"]
                except Exception:
                    last_err = f"unexpected response shape: {str(data)[:300]}"
                    content = None
                if content is not None:
                    parsed = extract_json(content)
                    if parsed is not None:
                        return parsed, content, usage, None
                    return None, content, usage, "model output is not valid JSON"
        except requests.RequestException as e:
            last_err = f"request error: {e}"
        # exponential backoff
        time.sleep(min(2 ** attempt, 8))
    return None, None, None, last_err or "unknown error"


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
def judge_one(
    idx: int,
    fields: Dict[str, Any],
    system_prompt: str,
    token: str,
) -> Tuple[int, Dict[str, Any]]:
    if not fields["question"].strip() or not fields["priv_query"].strip():
        return idx, {
            COL_RAW: "",
            COL_PARSED: None,
            COL_VERDICT: None,
            COL_REID: None,
            COL_UTIL: None,
            COL_CONF: None,
            COL_OK: False,
            COL_ERR: "empty question or priv_query",
            COL_USAGE: None,
        }

    messages = build_messages(system_prompt, fields)
    parsed, raw, usage, err = call_llm(messages, token=token)

    verdict = reid = util = conf = None
    if isinstance(parsed, dict):
        verdict = parsed.get("verdict")
        reid = parsed.get("reid_risk")
        util = parsed.get("utility_score")
        conf = parsed.get("confidence")

    return idx, {
        COL_RAW: raw or "",
        COL_PARSED: json.dumps(parsed, ensure_ascii=False) if parsed is not None else None,
        COL_VERDICT: verdict,
        COL_REID: float(reid) if isinstance(reid, (int, float)) else None,
        COL_UTIL: float(util) if isinstance(util, (int, float)) else None,
        COL_CONF: float(conf) if isinstance(conf, (int, float)) else None,
        COL_OK: parsed is not None,
        COL_ERR: err,
        COL_USAGE: json.dumps(usage, ensure_ascii=False) if usage else None,
    }


# ---------------------------------------------------------------------------
# Per-file processing
# ---------------------------------------------------------------------------
def process_file(
    in_path: Path,
    out_path: Path,
    *,
    system_prompt: str,
    token: str,
    workers: int,
    limit: int,
    overwrite: bool,
) -> None:
    print(f"\n=== {in_path.name} ===")
    print(f"[info] reading {in_path}")
    df = pd.read_parquet(in_path)
    n = len(df)
    print(f"[info] rows={n} cols={list(df.columns)}")

    # Resume support: if output exists and not overwrite, load existing judge
    # columns and skip rows already judged successfully.
    existing: Optional[pd.DataFrame] = None
    if out_path.exists() and not overwrite:
        try:
            existing = pd.read_parquet(out_path)
            if len(existing) == n:
                print(f"[info] resuming from existing {out_path.name}")
                for c in (COL_RAW, COL_PARSED, COL_VERDICT, COL_REID,
                          COL_UTIL, COL_CONF, COL_OK, COL_ERR, COL_USAGE):
                    if c in existing.columns:
                        df[c] = existing[c].values
            else:
                print(f"[warn] existing length mismatch "
                      f"({len(existing)} vs {n}); ignoring resume.")
                existing = None
        except Exception as e:
            print(f"[warn] failed to read existing {out_path}: {e}")
            existing = None

    # Ensure output columns exist.
    for c, default in (
        (COL_RAW, ""),
        (COL_PARSED, None),
        (COL_VERDICT, None),
        (COL_REID, None),
        (COL_UTIL, None),
        (COL_CONF, None),
        (COL_OK, False),
        (COL_ERR, None),
        (COL_USAGE, None),
    ):
        if c not in df.columns:
            df[c] = default

    # Build worklist
    todo: List[Tuple[int, Dict[str, Any]]] = []
    for i, row in df.iterrows():
        if not overwrite and bool(df.at[i, COL_OK]):
            continue
        fields = extract_fields(row)
        todo.append((i, fields))
        if limit and len(todo) >= limit:
            break

    print(f"[info] pending: {len(todo)} (workers={workers})")
    if not todo:
        # Still write a fresh copy so users always see an up-to-date file.
        df.to_parquet(out_path, index=False)
        print(f"[info] nothing to do. wrote {out_path}")
        return

    stats = UsageStats()
    n_ok = 0
    n_fail = 0

    # Periodic checkpointing
    save_every = max(50, len(todo) // 20)
    processed = 0
    save_lock = threading.Lock()

    def _maybe_checkpoint(force: bool = False) -> None:
        nonlocal processed
        with save_lock:
            if force or processed % save_every == 0:
                try:
                    df.to_parquet(out_path, index=False)
                except Exception as e:
                    print(f"[warn] checkpoint failed: {e}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(judge_one, idx, fields, system_prompt, token): idx
            for idx, fields in todo
        }
        with tqdm(total=len(futs), desc=f"judge {in_path.name}") as pbar:
            for fut in as_completed(futs):
                idx = futs[fut]
                try:
                    _, result = fut.result()
                except Exception as e:
                    result = {
                        COL_RAW: "",
                        COL_PARSED: None,
                        COL_VERDICT: None,
                        COL_REID: None,
                        COL_UTIL: None,
                        COL_CONF: None,
                        COL_OK: False,
                        COL_ERR: f"worker exception: {e}",
                        COL_USAGE: None,
                    }
                # Write back
                for k, v in result.items():
                    df.at[idx, k] = v
                # Stats
                if result.get(COL_USAGE):
                    try:
                        stats.add(json.loads(result[COL_USAGE]))
                    except Exception:
                        pass
                if result.get(COL_OK):
                    n_ok += 1
                else:
                    n_fail += 1

                processed += 1
                pbar.update(1)
                if processed % save_every == 0:
                    pbar.set_postfix_str(stats.format_line())
                    _maybe_checkpoint()

    _maybe_checkpoint(force=True)

    snap = stats.snapshot()
    print(f"[done] {in_path.name}: ok={n_ok} fail={n_fail} -> {out_path}")
    print(
        f"[usage] calls={snap['calls']} "
        f"prompt_tokens={snap['prompt_tokens']} "
        f"completion_tokens={snap['completion_tokens']} "
        f"total_tokens={snap['total_tokens']} "
        f"cost=${snap['cost_usd']:.4f}"
    )

    # Sidecar usage
    sidecar = out_path.with_suffix(out_path.suffix + ".usage.json")
    try:
        sidecar.write_text(json.dumps(snap, ensure_ascii=False, indent=2))
        print(f"[usage] wrote {sidecar}")
    except Exception as e:
        print(f"[usage] failed to write sidecar: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--inputs",
        nargs="+",
        default=DEFAULT_INPUTS,
        help="parquet file names under llm_test_data (default: all three)",
    )
    ap.add_argument("--data-dir", default=str(DATA_DIR))
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    ap.add_argument("--limit", type=int, default=0,
                    help="only judge the first N pending rows per file (0 = all)")
    ap.add_argument("--overwrite", action="store_true",
                    help="re-judge all rows, ignoring previous results")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    system_prompt = load_system_prompt()
    token = build_token()

    print(f"[cfg] model={MODEL_NAME}")
    print(f"[cfg] data_dir={data_dir}")
    print(f"[cfg] prompt={PROMPT_PATH} ({len(system_prompt)} chars)")
    print(f"[cfg] workers={args.workers} limit={args.limit} "
          f"overwrite={args.overwrite}")

    for name in args.inputs:
        in_path = data_dir / name
        if not in_path.exists():
            print(f"[skip] not found: {in_path}", file=sys.stderr)
            continue
        stem = in_path.stem  # e.g. "our"
        out_path = data_dir / f"{stem}{OUTPUT_SUFFIX}"
        process_file(
            in_path,
            out_path,
            system_prompt=system_prompt,
            token=token,
            workers=args.workers,
            limit=args.limit,
            overwrite=args.overwrite,
        )


if __name__ == "__main__":
    main()
