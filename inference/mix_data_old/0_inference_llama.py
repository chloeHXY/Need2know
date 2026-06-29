# -*- coding: utf-8 -*-
"""
使用部署的 llama_inference 进行推理。

数据使用逻辑参考: /group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_inference_gt.py
    - 读取 INPUT_PATH 的 parquet
    - 从 `extra_info` 列中提取 `question`
    - 多线程并发推理
    - 把结果写入新列后保存为 OUTPUT_PATH

服务调用方式参考: /group/40047/eiraxyhuang/workspace/fc/DataG/merge_inference/merge_inference.py
    - OpenAI 兼容的 SSE 流式接口
    - 通过 requests.iter_lines() 手动解析 SSE 帧
"""

import json
import time
import uuid
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


# =============================================================================
# Service configuration (refer to merge_inference.py / test2.py)
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
# I/O configuration (aligned with 0_inference_gt.py)
# =============================================================================
INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_llama.parquet"

OUTPUT_COL = "llama_answer"

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

SYSTEM_PROMPT = "Please answer the question and provide the answer directly, without explanation."


def extract_question(extra_info) -> str:
    """Extract the 'question' field from extra_info (which may be a dict-like object)."""
    if extra_info is None:
        return ""
    if isinstance(extra_info, dict):
        return extra_info.get("question", "") or ""
    try:
        return extra_info["question"] or ""
    except Exception:
        return ""


def _extract_piece(data_js: dict) -> str:
    """Extract a text piece from one SSE chunk (supports both delta and message)."""
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
    """Concatenate streamed text into a single string by manually parsing SSE."""
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


def call_llm(question: str) -> str:
    """Call the deployed llama_inference service with retries.

    Returns the answer string, or an error marker starting with [ERROR].
    """
    payload = {
        "model": MODEL,
        "query_id": "infer_llama_" + str(uuid.uuid4()),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
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
    print(f"Loading parquet: {INPUT_PATH}")
    df = pd.read_parquet(INPUT_PATH)
    print(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}")

    questions = [extract_question(ei) for ei in df["extra_info"].tolist()]
    answers = [None] * len(questions)

    # Concurrent inference with index tracking to preserve order.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_idx = {
            executor.submit(call_llm, q): i for i, q in enumerate(questions) if q
        }
        with tqdm(total=len(future_to_idx), desc="Inferencing(llama)") as pbar:
            for fut in as_completed(future_to_idx):
                idx = future_to_idx[fut]
                try:
                    answers[idx] = fut.result()
                except Exception as e:
                    answers[idx] = f"[ERROR] {e}"
                pbar.update(1)

    # Fill in empty-question rows with empty answers
    for i, q in enumerate(questions):
        if not q and answers[i] is None:
            answers[i] = ""

    df[OUTPUT_COL] = answers

    # Sanity stats
    err_cnt = sum(1 for a in answers if isinstance(a, str) and a.startswith("[ERROR]"))
    ok_cnt = sum(1 for a in answers if isinstance(a, str) and a and not a.startswith("[ERROR]"))
    print(f"Done. Total: {len(answers)}, OK: {ok_cnt}, Errors: {err_cnt}")

    print(f"Writing parquet: {OUTPUT_PATH}")
    df.to_parquet(OUTPUT_PATH, index=False)
    print("Saved.")


if __name__ == "__main__":
    main()