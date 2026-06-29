# -*- coding: utf-8 -*-
"""
PAPILLON Step 1: Prompt Creator.

For every record in the input parquet, take the original user query q (from
`extra_info["question"]`) and ask the LOCAL model (llama-3.1-8b-instruct) to
craft a privacy-preserving prompt q'. The prompt template is loaded from
`papillon/prompt.py` (the Creator template).

The local model is served via the same SSE-based endpoint used in
`merge_inference/merge_inference.py` and `test2.py`.

Output: the original parquet plus a new column `priv_query` (q').
"""

import os
import re
import json
import time
import uuid
import argparse
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Import the Creator prompt defined in papillon/prompt.py
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prompt import Creator as CREATOR_PROMPT  # noqa: E402


# =============================================================================
# Local LLM service configuration (refer to test2.py / merge_inference.py)
# =============================================================================
SS_URL = "http://21.119.245.18:81/openapi/chat/completions"
MODEL = "llama_inference"  # llama-3.1-8b-instruct deployment
WSID = "10143"
TOKEN = "7auGXNATFSKl7dF"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
    "Wsid": WSID,
}

# =============================================================================
# I/O configuration
# =============================================================================
INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/0_.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step1_priv_query.parquet"

QUESTION_COL = "extra_info"   # df[QUESTION_COL][i]["question"] -> q
OUTPUT_COL = "priv_query"     # generated q'

# =============================================================================
# Concurrency / generation configuration
# =============================================================================
MAX_WORKERS = 8
MAX_RETRIES = 3
RETRY_BACKOFF = 2
REQUEST_TIMEOUT = 300
ENABLE_STREAM = True
DEBUG_STREAM = False

GEN_PARAMS = {
    "temperature": 0.3,
    "top_p": 0.8,
    "top_k": 40,
    "repetition_penalty": 1,
    "output_seq_len": 1024,
    "max_input_seq_len": 4096,
}


def _extract_question(extra_info) -> str:
    if extra_info is None:
        return ""
    if isinstance(extra_info, dict):
        return extra_info.get("question", "") or ""
    try:
        return extra_info["question"] or ""
    except Exception:
        return ""


def build_messages(user_query: str):
    """Render the Creator prompt with the user query."""
    # The Creator template in prompt.py contains the literal placeholder
    # "{user query}" (with a space), so use a manual replace instead of .format().
    content = CREATOR_PROMPT.replace("{user query}", user_query if user_query else "")
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": content},
    ]


def _extract_piece(data_js: dict) -> str:
    try:
        choice = data_js["choices"][0]
    except (KeyError, IndexError, TypeError):
        return ""
    if not isinstance(choice, dict):
        return ""
    delta = choice.get("delta")
    if isinstance(delta, dict):
        piece = delta.get("content")
        if piece:
            return piece
    msg = choice.get("message")
    if isinstance(msg, dict):
        piece = msg.get("content")
        if piece:
            return piece
    return ""


def _parse_stream_response(resp) -> str:
    chunks = []
    buf_lines = []

    def _flush_event():
        if not buf_lines:
            return
        data_str = "\n".join(buf_lines).strip()
        buf_lines.clear()
        if not data_str or data_str == "[DONE]":
            return
        try:
            data_js = json.loads(data_str)
        except json.JSONDecodeError:
            return
        piece = _extract_piece(data_js)
        if piece:
            chunks.append(piece)

    for raw in resp.iter_lines(decode_unicode=True):
        if raw is None:
            continue
        if DEBUG_STREAM:
            print(f"[sse-raw] {raw!r}", flush=True)
        if raw == "":
            _flush_event()
            continue
        if raw.startswith(":"):
            continue
        if raw.startswith("data:"):
            buf_lines.append(raw[5:].lstrip())
        elif raw.startswith("data"):
            buf_lines.append(raw[4:].lstrip())
        else:
            buf_lines.append(raw)

    _flush_event()
    return "".join(chunks)


# Regex to pick the createdPrompt block out of the structured response.
_CREATED_PROMPT_RE = re.compile(
    r"\[\[\[\s*###\s*createdPrompt\s*###\s*\]\]\]\s*(.*?)(?:\[\[\[|$)",
    re.DOTALL | re.IGNORECASE,
)


def _extract_created_prompt(text: str) -> str:
    """Pull out the createdPrompt section from the model's structured output.

    Falls back to the raw (stripped) text if the marker is not found.
    """
    if not isinstance(text, str) or not text:
        return ""
    m = _CREATED_PROMPT_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def call_creator(user_query: str) -> str:
    """Call the local llama service with retries; returns q' or [ERROR] ..."""
    messages = build_messages(user_query)
    payload = {
        "model": MODEL,
        "query_id": "papillon_step1_" + str(uuid.uuid4()),
        "messages": messages,
        "stream": ENABLE_STREAM,
        **GEN_PARAMS,
    }

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                SS_URL,
                headers=HEADERS,
                json=payload,
                stream=ENABLE_STREAM,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            else:
                if ENABLE_STREAM:
                    text = _parse_stream_response(resp)
                else:
                    data = resp.json()
                    text = data["choices"][0]["message"]["content"]
                if text:
                    return _extract_created_prompt(text)
                last_err = "Empty response"
        except Exception as e:
            last_err = f"Exception: {e}"

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF ** attempt)

    return f"[ERROR] {last_err}"


def main():
    parser = argparse.ArgumentParser(description="PAPILLON Step1: Prompt Creator")
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

    if QUESTION_COL not in df.columns:
        raise KeyError(f"Missing required column: {QUESTION_COL}")

    questions = [_extract_question(ei) for ei in df[QUESTION_COL].tolist()]
    answers = [None] * len(questions)

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
    for i, q in enumerate(questions):
        if not isinstance(q, str) or not q.strip():
            answers[i] = answers[i] if answers[i] is not None else ""
            skipped_empty += 1
            continue
        if answers[i] is not None:
            continue
        tasks.append(i)
        processed_limit += 1
        if args.limit and processed_limit >= args.limit:
            break

    print(f"[plan] todo={len(tasks)}, skipped_empty={skipped_empty}, total={len(questions)}")

    if tasks:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_idx = {
                executor.submit(call_creator, questions[i]): i for i in tasks
            }
            with tqdm(total=len(future_to_idx), desc="Creator") as pbar:
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
