"""
撰写脚本
对/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.parquet
的prompt进行推理，结果存储到extra_info字段的query_gt下
参考：/group/40047/eiraxyhuang/workspace/fc/DataG/inference/inference_gt.py
"""

import os
import json
import time
import copy
import requests
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# 代理token请前往 https://venus.woa.com/#/openapi/accountManage/personalAccount  查看代理token，并替换后调用
TOKEN = "vxlvrEY2AbE0DmrJreMHBlEN@5325"
URL = "http://v2.open.venus.oa.com/llmproxy/chat/completions"
MODEL = "gpt-4o"

INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/Med_data_expand/3_.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/Med_data_expand/4_.parquet"

MAX_WORKERS = 16          # concurrent requests
MAX_RETRIES = 3           # retry times for each request
RETRY_BACKOFF = 2         # seconds, exponential backoff base
REQUEST_TIMEOUT = 120     # seconds

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}

GEN_PARAMS = {
    "temperature": 1,
    "top_p": 0.8,
    "top_k": 40,
    "repetition_penalty": 1,
    "output_seq_len": 1024,
    "max_input_seq_len": 4096,
}


def _to_plain_messages(prompt) -> list:
    """Convert a prompt field (which may be a numpy array of dict-like items) into
    a plain list of {"role", "content"} dicts suitable for the chat API."""
    if prompt is None:
        return []

    # numpy array -> list
    if isinstance(prompt, np.ndarray):
        prompt = prompt.tolist()

    messages = []
    for item in prompt:
        if isinstance(item, dict):
            role = item.get("role", "user")
            content = item.get("content", "")
        else:
            # Fallback: try item access
            try:
                role = item["role"]
                content = item["content"]
            except Exception:
                continue
        if content is None:
            content = ""
        messages.append({"role": str(role), "content": str(content)})
    return messages


def call_llm(messages: list) -> str:
    """Call the LLM proxy with retries. Returns the answer string, or an error marker."""
    if not messages:
        return ""

    payload = {
        "model": MODEL,
        "messages": messages,
        **GEN_PARAMS,
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
    print(f"Loading parquet: {INPUT_PATH}")
    df = pd.read_parquet(INPUT_PATH)
    print(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}")

    prompts = df["prompt"].tolist()
    messages_list = [_to_plain_messages(p) for p in prompts]
    answers = [None] * len(messages_list)

    # Concurrent inference, preserving original order via index mapping.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_idx = {
            executor.submit(call_llm, msgs): i
            for i, msgs in enumerate(messages_list)
            if msgs
        }
        with tqdm(total=len(future_to_idx), desc="Inferencing") as pbar:
            for fut in as_completed(future_to_idx):
                idx = future_to_idx[fut]
                try:
                    answers[idx] = fut.result()
                except Exception as e:
                    answers[idx] = f"[ERROR] {e}"
                pbar.update(1)

    # Fill empty-prompt rows with empty answer
    for i, msgs in enumerate(messages_list):
        if not msgs and answers[i] is None:
            answers[i] = ""

    # Write answers into extra_info["query_gt"]
    new_extra_infos = []
    for i, ei in enumerate(df["extra_info"].tolist()):
        if isinstance(ei, dict):
            new_ei = copy.deepcopy(ei)
        elif ei is None:
            new_ei = {}
        else:
            # Try to coerce mapping-like objects into dict
            try:
                new_ei = dict(ei)
            except Exception:
                new_ei = {"_original_extra_info": ei}
        new_ei["query_gt"] = answers[i]
        new_extra_infos.append(new_ei)

    df["extra_info"] = new_extra_infos

    # Sanity stats
    err_cnt = sum(
        1 for a in answers if isinstance(a, str) and a.startswith("[ERROR]")
    )
    print(f"Done. Total: {len(answers)}, Errors: {err_cnt}")

    print(f"Writing parquet: {OUTPUT_PATH}")
    df.to_parquet(OUTPUT_PATH, index=False)
    print("Saved.")


if __name__ == "__main__":
    main()