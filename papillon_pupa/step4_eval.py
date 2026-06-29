# -*- coding: utf-8 -*-
"""
PAPILLON Step 4: z_eval evaluation.

Use the Step 3 output (`final_answer`, i.e. C_L) as Response A, and compare it
against the target gpt-4o answer (`gpt_answer`, i.e. C_T) from
`inference/test_with_gpt_answer.parquet` as Response B, following the Q_AL
double-judge algorithm described in z_eval/skill.md / z_eval/eval.py.

Outputs:
    - prints the average Q_AL score
    - prints 2 random sample triples (response_A, response_B, score)
    - dumps full per-row results to a parquet file
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
# Judge service configuration (GPT-4o, same as inference/inference.py)
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
FILE_A = "/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step3_final_answer.parquet"
FILE_B = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/test_with_gpt_answer.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step4_eval_result.parquet"

RESPONSE_A_COL = "final_answer"   # C_L (papillon pipeline output, from Step 3)
RESPONSE_B_COL = "gpt_answer"     # C_T (target gpt-4o answer)
QUESTION_COL = "extra_info"       # user_query lives in extra_info["question"]

# =============================================================================
# Concurrency / robustness
# =============================================================================
MAX_WORKERS = 16
MAX_RETRIES = 3
RETRY_BACKOFF = 2
REQUEST_TIMEOUT = 120

# =============================================================================
# Judge prompt (f_QJ from z_eval/skill.md)
# =============================================================================
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


def _extract_question(extra_info) -> str:
    if extra_info is None:
        return ""
    if isinstance(extra_info, dict):
        return extra_info.get("question", "") or ""
    try:
        return extra_info["question"] or ""
    except Exception:
        return ""


def _parse_yes_no(text: str) -> int:
    if not isinstance(text, str):
        return 0
    t = text.strip().lower()
    t = t.strip(" \t\r\n.\"'`")
    if t.startswith("yes"):
        return 1
    if t.startswith("no"):
        return 0
    if "yes" in t and "no" not in t:
        return 1
    if "no" in t and "yes" not in t:
        return 0
    return 0


def call_judge(user_query: str, resp_a: str, resp_b: str) -> int:
    prompt = F_QJ.format(
        user_query=user_query if user_query is not None else "",
        response_A=resp_a if resp_a is not None else "",
        response_B=resp_b if resp_b is not None else "",
    )
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
                    text = data["choices"][0]["message"]["content"]
                    return _parse_yes_no(text)
                except (KeyError, IndexError, TypeError) as e:
                    last_err = f"Bad response structure: {e}; raw={str(data)[:200]}"
        except Exception as e:
            last_err = f"Exception: {e}"

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF ** attempt)

    print(f"[judge-error] {last_err}", flush=True)
    return 0


def judge_pair(user_query: str, c_l: str, c_t: str):
    """Q_AL with order swap. Returns (score, s1, s2).

    s1 == s2 -> 1 (conservative pass / inconsistent)
    s1 != s2 -> s1
    """
    s1 = call_judge(user_query, c_l, c_t)
    s2 = call_judge(user_query, c_t, c_l)
    score = 1 if s1 == s2 else s1
    return score, s1, s2


def _align_dataframes(df_a: pd.DataFrame, df_b: pd.DataFrame) -> pd.DataFrame:
    """Align file A and file B row-by-row.

    1) Prefer extra_info.question
    2) Fall back to priv_query
    3) Otherwise positional alignment (must have equal length)
    """
    n_a, n_b = len(df_a), len(df_b)
    print(f"[align] file_A rows={n_a}, file_B rows={n_b}")

    has_extra_a = QUESTION_COL in df_a.columns
    has_extra_b = QUESTION_COL in df_b.columns

    if has_extra_a and has_extra_b:
        print("[align] aligning on extra_info.question")
        qa = [_extract_question(x) for x in df_a[QUESTION_COL].tolist()]
        qb = [_extract_question(x) for x in df_b[QUESTION_COL].tolist()]
        df_a = df_a.copy()
        df_b = df_b.copy()
        df_a["__q__"] = qa
        df_b["__q__"] = qb
        b_keep = df_b[["__q__", RESPONSE_B_COL]].drop_duplicates(subset="__q__", keep="first")
        merged = df_a.merge(b_keep, on="__q__", how="inner")
        merged = merged.rename(columns={"__q__": "user_query"})
        print(f"[align] merged rows={len(merged)} (joined on extra_info.question)")
        return merged

    if "priv_query" in df_a.columns and "priv_query" in df_b.columns:
        print("[align] aligning on priv_query")
        b_keep = df_b[["priv_query", RESPONSE_B_COL]].drop_duplicates(subset="priv_query", keep="first")
        merged = df_a.merge(b_keep, on="priv_query", how="inner")
        if QUESTION_COL in merged.columns:
            merged["user_query"] = [_extract_question(x) for x in merged[QUESTION_COL].tolist()]
        else:
            merged["user_query"] = merged["priv_query"]
        print(f"[align] merged rows={len(merged)} (joined on priv_query)")
        return merged

    if n_a != n_b:
        raise ValueError(
            f"Cannot align files: no shared key column and lengths differ "
            f"(A={n_a}, B={n_b})."
        )
    print("[align] falling back to positional alignment")
    df = df_a.copy().reset_index(drop=True)
    df[RESPONSE_B_COL] = df_b[RESPONSE_B_COL].reset_index(drop=True)
    if QUESTION_COL in df.columns:
        df["user_query"] = [_extract_question(x) for x in df[QUESTION_COL].tolist()]
    else:
        df["user_query"] = ""
    return df


def main():
    parser = argparse.ArgumentParser(description="PAPILLON Step4: z_eval Q_AL judge")
    parser.add_argument("--file_a", default=FILE_A)
    parser.add_argument("--file_b", default=FILE_B)
    parser.add_argument("--output", default=OUTPUT_PATH)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--limit", type=int, default=0,
                        help="Only judge the first N rows (0 = all)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    print(f"[load] file A: {args.file_a}")
    df_a = pd.read_parquet(args.file_a)
    print(f"[load] file A rows={len(df_a)} cols={df_a.columns.tolist()}")
    print(f"[load] file B: {args.file_b}")
    df_b = pd.read_parquet(args.file_b)
    print(f"[load] file B rows={len(df_b)} cols={df_b.columns.tolist()}")

    if RESPONSE_A_COL not in df_a.columns:
        raise KeyError(f"file A missing column: {RESPONSE_A_COL}")
    if RESPONSE_B_COL not in df_b.columns:
        raise KeyError(f"file B missing column: {RESPONSE_B_COL}")

    df = _align_dataframes(df_a, df_b)

    user_queries = df["user_query"].tolist() if "user_query" in df.columns else [""] * len(df)
    responses_a = df[RESPONSE_A_COL].tolist()
    responses_b = df[RESPONSE_B_COL].tolist()

    n = len(df)
    if args.limit and args.limit < n:
        n = args.limit
        user_queries = user_queries[:n]
        responses_a = responses_a[:n]
        responses_b = responses_b[:n]
    print(f"[plan] judging {n} pairs")

    scores = [None] * n
    s1_list = [None] * n
    s2_list = [None] * n

    def _run(i):
        q = user_queries[i] or ""
        a = responses_a[i] if isinstance(responses_a[i], str) else ""
        b = responses_b[i] if isinstance(responses_b[i], str) else ""
        if not a and not b:
            return i, 1, 1, 1
        if not a:
            return i, 0, 0, 1
        if not b:
            return i, 1, 1, 0
        score, s1, s2 = judge_pair(q, a, b)
        return i, score, s1, s2

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_run, i): i for i in range(n)}
        with tqdm(total=len(futures), desc="Judging") as pbar:
            for fut in as_completed(futures):
                try:
                    i, score, s1, s2 = fut.result()
                except Exception as e:
                    i = futures[fut]
                    score, s1, s2 = 0, 0, 0
                    print(f"[task-error] idx={i} err={e}", flush=True)
                scores[i] = score
                s1_list[i] = s1
                s2_list[i] = s2
                pbar.update(1)

    valid_scores = [s for s in scores if s is not None]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
    print("\n=== Result ===")
    print(f"total pairs : {len(valid_scores)}")
    print(f"average     : {avg_score:.4f}")

    if valid_scores:
        sample_idx = random.sample(range(len(valid_scores)), k=min(2, len(valid_scores)))
        print("\n--- Random samples ---")
        for idx in sample_idx:
            ra = responses_a[idx] if isinstance(responses_a[idx], str) else ""
            rb = responses_b[idx] if isinstance(responses_b[idx], str) else ""
            print(f"\n[sample idx={idx}] score={scores[idx]} (s1={s1_list[idx]}, s2={s2_list[idx]})")
            print(f"  user_query : {(user_queries[idx] or '')[:200]}")
            print(f"  response_A : {ra[:300]}{'...' if len(ra) > 300 else ''}")
            print(f"  response_B : {rb[:300]}{'...' if len(rb) > 300 else ''}")

    out_df = pd.DataFrame({
        "user_query": user_queries,
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
