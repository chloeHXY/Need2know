# -*- coding: utf-8 -*-
"""
Batch inference over a parquet dataset using an internal SSE-based LLM service.

For each row in the input parquet, build a prompt by combining `priv_query` and
`privq_gpt_answer` (the high-quality reference answer from a stronger model),
then call the deployed model and store the response in a new column.

Service interaction style follows test2.py (OpenAI-compatible SSE), but the
streaming response is parsed manually with resp.iter_lines() instead of
relying on `sseclient`, because that library has occasionally lost middle
chunks against this upstream.
"""

import os
import json
import time
import uuid
import argparse
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


# =============================================================================
# Service configuration (refer to test2.py)
# =============================================================================
SS_URL = "http://21.119.245.18:81/openapi/chat/completions"
MODEL = "llama_inference"
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
INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/pupa/1_.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/pupa/2_.parquet"

QUERY_COL = "priv_query"
GPT_ANSWER_COL = "privq_gpt_answer"
QUESTION_COL = "extra_info"
ABILITY_COL = "ability"
OUTPUT_COL = "merge_inference_answer"

# =============================================================================
# Concurrency / generation configuration
# =============================================================================
MAX_WORKERS = 8
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, exponential backoff base
REQUEST_TIMEOUT = 300      # seconds
ENABLE_STREAM = True
DEBUG_STREAM = False       # set True to dump raw SSE lines for debugging

GEN_PARAMS = {
    "temperature": 1,
    "top_p": 0.8,
    "top_k": 40,
    "repetition_penalty": 1,
    "output_seq_len": 1024,
    "max_input_seq_len": 4096,
}

# =============================================================================
# Prompt template (from skill.md)
# =============================================================================
PROMPT_TEMPLATE_privacy ="""
You are answering the original user question.

Inputs:
- originalQuestion: the real user question.
- helpfulInformation: reference information from a stronger model for relatedQuery.

You may use the helpfulInformation only as background. The final answer must answer originalQuestion.

Rules:
- Only If helpfulInformation is useful, adapt it to originalQuestion.
- If helpfulInformation is too general, use only the relevant parts.
- If helpfulInformation conflicts with originalQuestion, follow originalQuestion.
- Do not mention relatedQuery or helpfulInformation.
- Do not ask follow-up questions.
- Give the best possible final answer directly.

originalQuestion:
{question}

helpfulInformation:
{priv_query}:{priv_gpt_answer}

Final answer:
"""
PROMPT_TEMPLATE_Med="""
Choose the single best answer to the original question.

You may use the helpfulInformation only as background.

Do not mention the helpfulInformation.

Do not add new options.

Return only:

<option letter>. <option text>

originalQuestion:

{question}

helpfulInformation:

{priv_query}:{priv_gpt_answer}

Answer:
"""
# PROMPT_TEMPLATE = """You are a highly skilled assistant capable of generating engaging and innovative responses. Analyze the user's request thoroughly and provide a detailed response that not only answers their query but also showcases creativity and understanding of the context. Your output should include well-structured content, relevant examples, and an engaging tone appropriate for the task at hand. Always aim to surprise the user with insightful perspectives that go beyond basic information, ensuring clarity and emotional resonance in your communication.

# Your input fields are:
# 1. `userQuery` (str): The user's request to be fulfilled.
# 2. `commonQuery`: A query that is similar to `userQuery`, but simpler and more general.
# 3. `modelExampleResponses` (str): You have the following information from a better language model responding to `commonQuery`. Complete the user query by referencing this information. Only you have access to this information.

# ## Input
# - userQuery: {question}
# - commonQuery: {priv_query}
# - modelExampleResponses: {priv_gpt_answer}

# Return only your response. Do not include any other text."""


# Mapping from `ability` value to its prompt template
PROMPT_TEMPLATE_MAP = {
    "Med": PROMPT_TEMPLATE_Med,
    "privacy": PROMPT_TEMPLATE_privacy,
}


def _select_prompt_template(ability: str) -> str:
    """Select prompt template based on `ability`. Falls back to privacy template."""
    if isinstance(ability, str):
        tmpl = PROMPT_TEMPLATE_MAP.get(ability)
        if tmpl is not None:
            return tmpl
    # Fallback: use privacy template if ability is missing/unknown
    return PROMPT_TEMPLATE_privacy


def build_messages(priv_query: str, priv_gpt_answer: str, question: str, ability: str = ""):
    """Build chat messages from a single record using the prompt template.

    The prompt template is selected by `ability`:
    - ability == "Med"     -> PROMPT_TEMPLATE_Med
    - ability == "privacy" -> PROMPT_TEMPLATE_privacy
    """
    template = _select_prompt_template(ability)
    content = template.format(
        priv_query=priv_query if priv_query is not None else "",
        priv_gpt_answer=priv_gpt_answer if priv_gpt_answer is not None else "",
        question=question if question is not None else "",
    )
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": content}
    ]


def _extract_piece(data_js: dict) -> str:
    """Extract a text piece from one SSE chunk (supports both delta and message)."""
    try:
        choice = data_js["choices"][0]
    except (KeyError, IndexError, TypeError):
        return ""
    if not isinstance(choice, dict):
        return ""
    # Streaming chunk: delta.content
    delta = choice.get("delta")
    if isinstance(delta, dict):
        piece = delta.get("content")
        if piece:
            return piece
    # Non-streaming or final chunk: message.content
    msg = choice.get("message")
    if isinstance(msg, dict):
        piece = msg.get("content")
        if piece:
            return piece
    return ""


def _parse_stream_response(resp) -> str:
    """Concatenate streamed text into a single string.

    Parse SSE manually via resp.iter_lines() to be robust against quirks of the
    upstream service (CRLF endings, occasional empty keep-alive lines,
    multi-line `data:` events, `[DONE]` sentinels, etc.).
    """
    chunks = []
    buf_lines = []  # accumulate consecutive `data:` lines for a single event

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
        # An empty line marks the end of one SSE event
        if raw == "":
            _flush_event()
            continue
        # Ignore SSE comments / unknown fields
        if raw.startswith(":"):
            continue
        if raw.startswith("data:"):
            buf_lines.append(raw[5:].lstrip())
        elif raw.startswith("data"):  # tolerate "data " without colon
            buf_lines.append(raw[4:].lstrip())
        else:
            # Some servers stream raw JSON without the "data:" prefix
            buf_lines.append(raw)

    _flush_event()
    return "".join(chunks)


def call_llm(priv_query: str, priv_gpt_answer: str, question: str, ability: str = "") -> str:
    """Call the internal LLM service with retries; returns the answer or [ERROR] ..."""
    messages = build_messages(priv_query, priv_gpt_answer, question, ability)

    payload = {
        "model": MODEL,
        "query_id": "merge_infer_" + str(uuid.uuid4()),
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
                    return text
                last_err = "Empty response"
        except Exception as e:
            last_err = f"Exception: {e}"

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF ** attempt)

    return f"[ERROR] {last_err}"


def main():
    parser = argparse.ArgumentParser(description="Batch merge-inference over parquet.")
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

    if QUERY_COL not in df.columns:
        raise KeyError(f"Missing required column: {QUERY_COL}")
    if GPT_ANSWER_COL not in df.columns:
        raise KeyError(f"Missing required column: {GPT_ANSWER_COL}")
    if QUESTION_COL not in df.columns:
        raise KeyError(f"Missing required column: {QUESTION_COL}")
    if ABILITY_COL not in df.columns:
        raise KeyError(f"Missing required column: {ABILITY_COL}")

    queries = df[QUERY_COL].tolist()
    refs = df[GPT_ANSWER_COL].tolist()
    questions = [ei['question'] for ei in df[QUESTION_COL].tolist()]
    abilities = df[ABILITY_COL].tolist()

    # Quick stats on ability distribution to make routing transparent
    try:
        from collections import Counter
        ab_counter = Counter(abilities)
        print(f"[plan] ability distribution: {dict(ab_counter)}")
    except Exception:
        pass

    answers = [None] * len(queries)

    # Optional resume
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

    # Build the task list (skip empty queries / already-finished rows)
    tasks = []
    skipped_empty = 0
    processed_limit = 0
    for i, q in enumerate(queries):
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

    print(f"[plan] todo={len(tasks)}, skipped_empty={skipped_empty}, total={len(queries)}")

    if tasks:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_idx = {
                executor.submit(call_llm, queries[i], refs[i], questions[i], abilities[i]): i for i in tasks
            }
            with tqdm(total=len(future_to_idx), desc="Inferencing") as pbar:
                for fut in as_completed(future_to_idx):
                    idx = future_to_idx[fut]
                    try:
                        answers[idx] = fut.result()
                    except Exception as e:
                        answers[idx] = f"[ERROR] {e}"
                    pbar.update(1)

    # Fill any remaining None as empty string
    for i, a in enumerate(answers):
        if a is None:
            answers[i] = ""

    df[OUTPUT_COL] = answers

    err_cnt = sum(1 for a in answers if isinstance(a, str) and a.startswith("[ERROR]"))
    ok_cnt = sum(1 for a in answers if isinstance(a, str) and a and not a.startswith("[ERROR]"))
    print(f"[done] total={len(answers)} ok={ok_cnt} err={err_cnt} empty={len(answers) - ok_cnt - err_cnt}")

    print(f"[save] writing parquet: {args.output}")
    df.to_parquet(args.output, index=False)
    print("[save] saved.")


if __name__ == "__main__":
    main()
