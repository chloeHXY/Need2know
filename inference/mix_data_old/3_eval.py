# -*- coding: utf-8 -*-
"""
Mixed-ability evaluation over a single parquet file.

Input parquet (default):
    /group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/2_.parquet

Required columns:
    - ability                 : "privacy" | "Med"
    - merge_inference_answer  : C_L  (pipeline output, the response to score)
    - gpt_answer              : C_T  (target / reference response from GPT-4o)
    - extra_info              : dict with "question" (and "answer_label" for Med)

Per ability:
    1) ability == "privacy"
       Pairwise quality judge with swap (Q_AL), same logic as z_eval/eval.py:
           s1 = judge(A=C_L, B=C_T)
           s2 = judge(A=C_T, B=C_L)
           score = 1 if s1 == s2 else s1
       The privacy metric is the average score (1 = at least as good as GPT-4o).

    2) ability == "Med"
       Single-choice consistency check via GPT-4o using the prompt from todo.md:
       compare merge_inference_answer against extra_info["answer_label"],
       parse the judge output to {0, 1}, and report accuracy.

Output:
    - prints per-ability metrics and an overall summary
    - dumps per-row evaluation results to a parquet file
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
# Judge service configuration (GPT-4o, identical to z_eval/eval.py)
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
INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/2_2.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/3_2_eval_result.parquet"

ABILITY_COL = "ability"
RESPONSE_A_COL = "merge_inference_answer"   # C_L (pipeline output)
RESPONSE_B_COL = "gpt_answer"               # C_T (GPT-4o reference)
QUESTION_COL = "extra_info"                 # extra_info["question"], extra_info["answer_label"]

# =============================================================================
# Concurrency / robustness
# =============================================================================
MAX_WORKERS = 16
MAX_RETRIES = 3
RETRY_BACKOFF = 2
REQUEST_TIMEOUT = 120

# =============================================================================
# Prompts
# =============================================================================
# Pairwise judge prompt (same as z_eval/eval.py, f_QJ)
F_QJ = """You are an impartial evaluator comparing two responses to the same user query.

Determine whether Response A is at least as good as Response B.

Answer "yes" if Response A is equal to or better than Response B overall.
Answer "no" if Response A is worse than Response B overall.

Evaluate based on correctness, completeness, relevance, helpfulness, safety, and clarity.

Do not favor a response simply because it is longer.

Return exactly one word: "yes" or "no". Do not include any explanation.

User Query:
{user_query}

Response A:
{response_A}

Response B:
{response_B}

Answer:
"""

# Med single-choice consistency prompt (from todo.md)
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
def _extract_question(extra_info) -> str:
    if extra_info is None:
        return ""
    if isinstance(extra_info, dict):
        return extra_info.get("question", "") or ""
    try:
        return extra_info["question"] or ""
    except Exception:
        return ""


def _extract_answer_label(extra_info) -> str:
    if extra_info is None:
        return ""
    if isinstance(extra_info, dict):
        v = extra_info.get("answer_label", "")
        return str(v) if v is not None else ""
    try:
        v = extra_info["answer_label"]
        return str(v) if v is not None else ""
    except Exception:
        return ""


def _parse_yes_no(text: str) -> int:
    """Map judge output to {1: yes, 0: no}; default to 0 on unparseable."""
    if not isinstance(text, str):
        return 0
    t = text.strip().lower().strip(" \t\r\n.\"'`")
    if t.startswith("yes"):
        return 1
    if t.startswith("no"):
        return 0
    if "yes" in t and "no" not in t:
        return 1
    if "no" in t and "yes" not in t:
        return 0
    return 0


def _parse_zero_one(text: str) -> int:
    """Map judge output to {1, 0}; default to 0 on unparseable."""
    if not isinstance(text, str):
        return 0
    t = text.strip()
    # Strip surrounding punctuation/quotes/whitespace
    t = t.strip(" \t\r\n.\"'`")
    if not t:
        return 0
    # Look at the first token / character
    for ch in t:
        if ch == "1":
            return 1
        if ch == "0":
            return 0
        # Skip unrelated leading punctuation
        if not ch.isalnum():
            continue
        break
    # Fallback: if "1" appears and "0" does not, treat as 1
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


# =============================================================================
# Privacy: pairwise judge with swap (Q_AL)
# =============================================================================
def _privacy_call(user_query: str, resp_a: str, resp_b: str) -> int:
    prompt = F_QJ.format(
        user_query=user_query or "",
        response_A=resp_a or "",
        response_B=resp_b or "",
    )
    return _parse_yes_no(_post_judge(prompt))


def judge_privacy(user_query: str, c_l: str, c_t: str):
    """Returns (score, s1, s2) with conservative-pass on tie."""
    s1 = _privacy_call(user_query, c_l, c_t)
    s2 = _privacy_call(user_query, c_t, c_l)
    score = 1 if s1 == s2 else s1
    return score, s1, s2


# =============================================================================
# Med: single-choice consistency
# =============================================================================
def judge_med(merge_inference_answer: str, answer_label: str) -> int:
    prompt = F_MED.format(
        merge_inference_answer=merge_inference_answer or "",
        answer_label=answer_label or "",
    )
    return _parse_zero_one(_post_judge(prompt))


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Mixed-ability evaluation over a parquet file.")
    parser.add_argument("--input", default=INPUT_PATH)
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--limit", type=int, default=0,
                        help="Only evaluate the first N rows (0 = all)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    print(f"[load] reading parquet: {args.input}")
    df = pd.read_parquet(args.input)
    print(f"[load] rows={len(df)} cols={df.columns.tolist()}")

    for col in (ABILITY_COL, RESPONSE_A_COL, RESPONSE_B_COL, QUESTION_COL):
        if col not in df.columns:
            raise KeyError(f"Missing required column: {col}")

    n = len(df)
    if args.limit and args.limit < n:
        df = df.iloc[:args.limit].reset_index(drop=True)
        n = len(df)
    print(f"[plan] evaluating {n} rows; ability counts:\n{df[ABILITY_COL].value_counts()}")

    abilities = df[ABILITY_COL].tolist()
    responses_a = df[RESPONSE_A_COL].tolist()
    responses_b = df[RESPONSE_B_COL].tolist()
    extras = df[QUESTION_COL].tolist()

    user_queries = [_extract_question(x) for x in extras]
    answer_labels = [_extract_answer_label(x) for x in extras]

    scores = [None] * n   # privacy: 0/1 from Q_AL; med: 0/1 correctness
    s1_list = [None] * n  # privacy only
    s2_list = [None] * n  # privacy only
    notes = [""] * n      # ability tag for clarity

    def _run(i):
        ab = (abilities[i] or "").strip()
        a = responses_a[i] if isinstance(responses_a[i], str) else ""
        b = responses_b[i] if isinstance(responses_b[i], str) else ""

        if ab.lower() == "privacy":
            q = user_queries[i] or ""
            # Edge cases: empty strings -> avoid LLM calls
            if not a and not b:
                return i, 1, 1, 1, "privacy"
            if not a:
                return i, 0, 0, 1, "privacy"
            if not b:
                return i, 1, 1, 0, "privacy"
            score, s1, s2 = judge_privacy(q, a, b)
            return i, score, s1, s2, "privacy"

        if ab.lower() == "med":
            label = answer_labels[i] or ""
            if not a or not label:
                return i, 0, None, None, "Med"
            score = judge_med(a, label)
            return i, score, None, None, "Med"

        # Unknown ability: skip (score=None)
        return i, None, None, None, ab or "unknown"

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_run, i): i for i in range(n)}
        with tqdm(total=len(futures), desc="Evaluating") as pbar:
            for fut in as_completed(futures):
                try:
                    i, score, s1, s2, note = fut.result()
                except Exception as e:
                    i = futures[fut]
                    score, s1, s2, note = 0, None, None, "error"
                    print(f"[task-error] idx={i} err={e}", flush=True)
                scores[i] = score
                s1_list[i] = s1
                s2_list[i] = s2
                notes[i] = note
                pbar.update(1)

    # =========================================================================
    # Aggregate per-ability metrics
    # =========================================================================
    print("\n=== Result ===")
    overall_total = 0
    overall_sum = 0
    for ab in sorted({(a or "").strip() for a in abilities}):
        if not ab:
            continue
        idxs = [i for i, x in enumerate(abilities) if (x or "").strip() == ab]
        valid = [scores[i] for i in idxs if scores[i] is not None]
        if not valid:
            print(f"  [{ab}] count=0 (no valid scores)")
            continue
        avg = sum(valid) / len(valid)
        overall_total += len(valid)
        overall_sum += sum(valid)
        if ab.lower() == "med":
            print(f"  [{ab:8s}] count={len(valid):4d}  accuracy = {avg:.4f}")
        elif ab.lower() == "privacy":
            print(f"  [{ab:8s}] count={len(valid):4d}  Q_AL avg = {avg:.4f}")
        else:
            print(f"  [{ab:8s}] count={len(valid):4d}  avg      = {avg:.4f}")

    if overall_total:
        print(f"  [overall ] count={overall_total:4d}  avg      = {overall_sum / overall_total:.4f}")

    # =========================================================================
    # Print 2 random samples
    # =========================================================================
    valid_idxs = [i for i in range(n) if scores[i] is not None]
    if valid_idxs:
        sample_idx = random.sample(valid_idxs, k=min(2, len(valid_idxs)))
        print("\n--- Random samples ---")
        for idx in sample_idx:
            ra = responses_a[idx] if isinstance(responses_a[idx], str) else ""
            rb = responses_b[idx] if isinstance(responses_b[idx], str) else ""
            print(f"\n[sample idx={idx}] ability={notes[idx]} score={scores[idx]} "
                  f"(s1={s1_list[idx]}, s2={s2_list[idx]})")
            print(f"  user_query   : {(user_queries[idx] or '')[:200]}")
            print(f"  answer_label : {answer_labels[idx]}")
            print(f"  response_A   : {ra[:300]}{'...' if len(ra) > 300 else ''}")
            print(f"  response_B   : {rb[:300]}{'...' if len(rb) > 300 else ''}")

    # =========================================================================
    # Persist results
    # =========================================================================
    out_df = pd.DataFrame({
        "ability": abilities,
        "user_query": user_queries,
        "answer_label": answer_labels,
        "response_A": responses_a,
        "response_B": responses_b,
        "s1": s1_list,
        "s2": s2_list,
        "score": scores,
    })
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    out_df.to_parquet(args.output, index=False)
    print(f"\n[save] wrote results to: {args.output}")


if __name__ == "__main__":
    main()
