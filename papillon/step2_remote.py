# -*- coding: utf-8 -*-
"""
PAPILLON Step 2: Remote Model Response.

Read the privacy-preserving prompt q' produced in Step 1 and send each q' to
the remote model (gpt-4o, via the venus llmproxy) to obtain an intermediate
response CR. Write CR back to the parquet as `remote_answer`.

Service / proxy follow `inference/inference.py`.
"""

import os
import json
import time
import argparse
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


# =============================================================================
# Remote service configuration (refer to inference/inference.py)
# =============================================================================
TOKEN = "vxlvrEY2AbE0DmrJreMHBlEN@5325"
URL = "http://v2.open.venus.oa.com/llmproxy/chat/completions"
MODEL = "gpt-4o"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}

SYSTEM_PROMPT = "Please answer the question and provide the answer directly, without explanation."

# =============================================================================
# I/O configuration
# =============================================================================
INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step1_qwen523_priv_query.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step2_remote_answer.parquet"

PRIV_QUERY_COL = "priv_query"   # q' from Step 1
OUTPUT_COL = "remote_answer"    # CR

# =============================================================================
# Concurrency / robustness
# =============================================================================
MAX_WORKERS = 16
MAX_RETRIES = 3
RETRY_BACKOFF = 2
REQUEST_TIMEOUT = 120


def call_remote(question: str) -> str:
    """Call the remote GPT-4o proxy with retries."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "temperature": 0.7,
    }

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                URL,
                headers=HEADERS,
                data=json.dumps(payload),
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            else:
                data = resp.json()
                try:
                    return data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as e:
                    last_err = f"Bad response structure: {e}; raw={str(data)[:200]}"
        except Exception as e:
            last_err = f"Exception: {e}"

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF ** attempt)

    return f"[ERROR] {last_err}"


def main():
    parser = argparse.ArgumentParser(description="PAPILLON Step2: Remote Model Response")
    parser.add_argument("--input", default=INPUT_PATH, help="Input parquet path")
    parser.add_argument("--output", default=OUTPUT_PATH, help="Output parquet path")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help="Concurrent workers")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only process the first N non-empty rows (0 = all)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume by reusing successful answers from the previous output file")
    args = parser.parse_args()

    print(f"[load] reading parquet: {args.input}")
    df = pd.read_parquet(args.input)
    print(f"[load] rows={len(df)} columns={df.columns.tolist()}")

    if PRIV_QUERY_COL not in df.columns:
        raise KeyError(f"Missing required column: {PRIV_QUERY_COL}")

    queries = df[PRIV_QUERY_COL].tolist()
    answers = [None] * len(queries)

    if args.resume and os.path.exists(args.output):
        try:
            prev = pd.read_parquet(args.output)
            if OUTPUT_COL in prev.columns and len(prev) == len(df):
                for i, v in enumerate(prev[OUTPUT_COL].tolist()):
                    if isinstance(v, str) and v and not v.startswith("[ERROR]"):
                        answers[i] = v
                done = sum(1 for a in answers if a is not None)
                print(f"[resume] loaded existing answers: {done}/{len(answers)}")
            else:
                print("[resume] previous output schema mismatch, starting from scratch")
        except Exception as e:
            print(f"[resume] failed to load previous output: {e}")

    tasks = []
    skipped_empty = 0
    processed_limit = 0
    for i, q in enumerate(queries):
        if not isinstance(q, str) or not q.strip() or q.startswith("[ERROR]"):
            answers[i] = answers[i] if answers[i] is not None else ""
            skipped_empty += 1
            continue
        if answers[i] is not None:
            continue
        tasks.append(i)
        processed_limit += 1
        if args.limit and processed_limit >= args.limit:
            break

    print(f"[plan] todo={len(tasks)}, skipped_empty={skipped_empty}, total={len(queries)}")

    if tasks:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_idx = {
                executor.submit(call_remote, queries[i]): i for i in tasks
            }
            with tqdm(total=len(future_to_idx), desc="Remote") as pbar:
                for fut in as_completed(future_to_idx):
                    idx = future_to_idx[fut]
                    try:
                        answers[idx] = fut.result()
                    except Exception as e:
                        answers[idx] = f"[ERROR] {e}"
                    pbar.update(1)

    for i, a in enumerate(answers):
        if a is None:
            answers[i] = ""

    df[OUTPUT_COL] = answers

    err_cnt = sum(1 for a in answers if isinstance(a, str) and a.startswith("[ERROR]"))
    ok_cnt = sum(1 for a in answers if isinstance(a, str) and a and not a.startswith("[ERROR]"))
    print(f"[done] total={len(answers)} ok={ok_cnt} err={err_cnt} "
          f"empty={len(answers) - ok_cnt - err_cnt}")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    print(f"[save] writing parquet: {args.output}")
    df.to_parquet(args.output, index=False)
    print("[save] saved.")


if __name__ == "__main__":
    main()
