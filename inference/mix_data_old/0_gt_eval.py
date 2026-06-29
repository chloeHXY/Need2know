# -*- coding: utf-8 -*-
"""
Evaluate the accuracy of `gpt_answer` against `answer_label` for ability == "Med".

This is a standalone sanity check that mirrors the Med branch of
`inference/mix_data/3_eval.py`, but:
    - filters to ability == "Med" only
    - scores `gpt_answer` (instead of `merge_inference_answer`)
      against `extra_info["answer_label"]`

Input (default):
    /group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_.parquet

Required columns:
    - ability       : must contain "Med"
    - gpt_answer    : natural-language answer to be judged
    - extra_info    : dict with "answer_label" (and "question" optional)
"""

import os
import json
import time
import random
import argparse
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


# =============================================================================
# Judge service configuration (GPT-4o)
# =============================================================================
TOKEN = "vxlvrEY2AbE0DmrJreMHBlEN@5325"
URL = "http://v2.open.venus.oa.com/llmproxy/chat/completions"
MODEL = "gpt-4o"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}

# =============================================================================
# I/O configuration
# =============================================================================
INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_gt_eval_result.parquet"

ABILITY_COL = "ability"
ANSWER_COL = "gpt_answer"          # the response to score
EXTRA_COL = "extra_info"           # extra_info["answer_label"], extra_info["question"]

TARGET_ABILITY = "Med"

# =============================================================================
# Concurrency / robustness
# =============================================================================
MAX_WORKERS = 16
MAX_RETRIES = 3
RETRY_BACKOFF = 2
REQUEST_TIMEOUT = 120

# =============================================================================
# Med single-choice consistency prompt (same as 3_eval.py)
# =============================================================================
F_MED = """You are a strict answer-consistency evaluator. Your task is to determine whether the final answer expressed in the natural-language answer matches the answer_label.

Evaluation rules:
1. Focus only on the final option or answer explicitly stated in answer.
2. Output 1 if the option selected in answer exactly matches answer_label.
3. Output 0 if answer selects a different option, does not clearly select an option, gives multiple conflicting options, or the final answer cannot be determined.
4. Do not judge whether the explanation is medically, scientifically, or factually correct; only judge whether the final selected answer matches answer_label.
5. Output only a single character: 1 or 0. Do not output any explanation, punctuation, spaces, or extra text.

Input:
answer: {merge_inference_answer}
answer_label: {answer_label}

Output:
"""


# =============================================================================
# Helpers
# =============================================================================
def _extract_field(extra_info, key: str) -> str:
    if extra_info is None:
        return ""
    if isinstance(extra_info, dict):
        v = extra_info.get(key, "")
        return str(v) if v is not None else ""
    try:
        v = extra_info[key]
        return str(v) if v is not None else ""
    except Exception:
        return ""


def _parse_zero_one(text: str) -> int:
    """Map judge output to {1, 0}; default to 0 on unparseable."""
    if not isinstance(text, str):
        return 0
    t = text.strip().strip(" \t\r\n.\"'`")
    if not t:
        return 0
    for ch in t:
        if ch == "1":
            return 1
        if ch == "0":
            return 0
        if not ch.isalnum():
            continue
        break
    if "1" in t and "0" not in t:
        return 1
    return 0


def _post_judge(prompt: str) -> str:
    """Single GPT-4o call with retries; returns raw text content or ''."""
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
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
                    return data["choices"][0]["message"]["content"] or ""
                except (KeyError, IndexError, TypeError) as e:
                    last_err = f"Bad response structure: {e}; raw={str(data)[:200]}"
        except Exception as e:
            last_err = f"Exception: {e}"

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF ** attempt)

    print(f"[judge-error] {last_err}", flush=True)
    return ""


def judge_med(answer: str, answer_label: str) -> int:
    prompt = F_MED.format(
        merge_inference_answer=answer or "",
        answer_label=answer_label or "",
    )
    return _parse_zero_one(_post_judge(prompt))


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Evaluate gpt_answer vs answer_label accuracy on ability==Med."
    )
    parser.add_argument("--input", default=INPUT_PATH)
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--limit", type=int, default=0,
                        help="Only evaluate the first N Med rows (0 = all)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    print(f"[load] reading parquet: {args.input}")
    df = pd.read_parquet(args.input)
    print(f"[load] rows={len(df)} cols={df.columns.tolist()}")

    for col in (ABILITY_COL, ANSWER_COL, EXTRA_COL):
        if col not in df.columns:
            raise KeyError(f"Missing required column: {col}")

    # Filter to Med only
    mask = df[ABILITY_COL].astype(str).str.strip().str.lower() == TARGET_ABILITY.lower()
    df = df[mask].reset_index(drop=True)
    print(f"[filter] ability=={TARGET_ABILITY!r} -> rows={len(df)}")

    if args.limit and args.limit < len(df):
        df = df.iloc[:args.limit].reset_index(drop=True)
    n = len(df)
    if n == 0:
        print("[exit] no Med rows to evaluate.")
        return

    answers = df[ANSWER_COL].tolist()
    extras = df[EXTRA_COL].tolist()
    questions = [_extract_field(x, "question") for x in extras]
    answer_labels = [_extract_field(x, "answer_label") for x in extras]

    scores = [None] * n

    def _run(i):
        a = answers[i] if isinstance(answers[i], str) else ""
        label = answer_labels[i] or ""
        if not a or not label:
            return i, 0
        return i, judge_med(a, label)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_run, i): i for i in range(n)}
        with tqdm(total=len(futures), desc="Evaluating Med (gpt_answer)") as pbar:
            for fut in as_completed(futures):
                try:
                    i, score = fut.result()
                except Exception as e:
                    i = futures[fut]
                    score = 0
                    print(f"[task-error] idx={i} err={e}", flush=True)
                scores[i] = score
                pbar.update(1)

    # =========================================================================
    # Aggregate
    # =========================================================================
    valid = [s for s in scores if s is not None]
    acc = (sum(valid) / len(valid)) if valid else 0.0
    print("\n=== Result ===")
    print(f"  [Med | gpt_answer vs answer_label]  count={len(valid)}  accuracy = {acc:.4f}")

    # =========================================================================
    # Print 2 random samples
    # =========================================================================
    valid_idxs = [i for i in range(n) if scores[i] is not None]
    if valid_idxs:
        sample_idx = random.sample(valid_idxs, k=min(2, len(valid_idxs)))
        print("\n--- Random samples ---")
        for idx in sample_idx:
            a = answers[idx] if isinstance(answers[idx], str) else ""
            print(f"\n[sample idx={idx}] score={scores[idx]}")
            print(f"  question     : {(questions[idx] or '')[:200]}")
            print(f"  answer_label : {answer_labels[idx]}")
            print(f"  gpt_answer   : {a[:300]}{'...' if len(a) > 300 else ''}")

    # =========================================================================
    # Persist
    # =========================================================================
    out_df = pd.DataFrame({
        "ability": [TARGET_ABILITY] * n,
        "question": questions,
        "answer_label": answer_labels,
        "gpt_answer": answers,
        "score": scores,
    })
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    out_df.to_parquet(args.output, index=False)
    print(f"\n[save] wrote results to: {args.output}")


if __name__ == "__main__":
    main()