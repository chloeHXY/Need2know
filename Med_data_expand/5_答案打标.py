"""
撰写脚本
数据：/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_query_gt.parquet
当前数据question虽然是单选题，但是answer都是自然语言解释，请撰写脚本利用大模型打标，标注选项类答案（ABCDE）
question:extra_info['question']
answer:extra_info['answer']
脚本可以参考/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/打标.py
"""

import os
import re
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

INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/Med_data_expand/4_.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/Med_data_expand/5_.parquet"

MAX_WORKERS = 16          # concurrent requests
MAX_RETRIES = 3           # retry times for each request
RETRY_BACKOFF = 2         # seconds, exponential backoff base
REQUEST_TIMEOUT = 120     # seconds

VALID_LABELS = {"A", "B", "C", "D", "E", "UNKNOWN"}

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}

GEN_PARAMS = {
    "temperature": 0,
    "top_p": 0.8,
    "top_k": 40,
    "repetition_penalty": 1,
    "output_seq_len": 16,
    "max_input_seq_len": 4096,
}

PROMPT_TEMPLATE = """\
You are a strict multiple-choice answer labeler.

Given:
- question: a single-choice question with options A, B, C, D, and optionally E
- answer: a natural-language explanation

Your task is to infer which option letter the answer selects.

Rules:
1. Output exactly one label: A, B, C, D, E, or UNKNOWN.
2. If the answer explicitly mentions an option letter, such as "ECG (D)", "the answer is D", or "choose E", use that letter.
3. If the answer does not explicitly mention a letter, match the selected answer text to the options in the question.
4. If multiple options are mentioned, choose the one endorsed as the correct, best, most appropriate, next, indicated, or final answer.
5. Ignore options that are only mentioned as alternatives, rejected choices, comparisons, or less appropriate options.
6. If the selected option cannot be determined confidently, output UNKNOWN.
7. Do not provide any explanation or extra text.

question:
{question}

answer:
{answer}

Output:"""


def build_messages(question: str, answer: str) -> list:
    """Build chat messages for the labeler."""
    if question is None:
        question = ""
    if answer is None:
        answer = ""
    user_content = PROMPT_TEMPLATE.format(
        question=str(question).strip(),
        answer=str(answer).strip(),
    )
    return [{"role": "user", "content": user_content}]


def normalize_label(text: str) -> str:
    """Extract a clean A/B/C/D/E/UNKNOWN label from raw model output."""
    if text is None:
        return "UNKNOWN"
    s = str(text).strip()
    if not s:
        return "UNKNOWN"

    upper = s.upper()
    if "UNKNOWN" in upper:
        return "UNKNOWN"

    # Prefer the first standalone A/B/C/D/E occurrence.
    m = re.search(r"\b([ABCDE])\b", upper)
    if m:
        return m.group(1)

    # Fallback: any A/B/C/D/E character.
    m = re.search(r"[ABCDE]", upper)
    if m:
        return m.group(0)

    return "UNKNOWN"


def call_llm(messages: list) -> str:
    """Call the LLM proxy with retries. Returns the raw answer string, or an error marker."""
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


def label_one(question: str, answer: str) -> tuple:
    """Run one labeling request. Returns (label, raw_output)."""
    messages = build_messages(question, answer)
    raw = call_llm(messages)
    if isinstance(raw, str) and raw.startswith("[ERROR]"):
        return "UNKNOWN", raw
    return normalize_label(raw), raw


def _get_qa(extra_info):
    """Safely fetch (question, answer) from an extra_info cell."""
    if extra_info is None:
        return "", ""
    if isinstance(extra_info, dict):
        return extra_info.get("question", "") or "", extra_info.get("answer", "") or ""
    # numpy / mapping-like fallback
    try:
        return extra_info["question"], extra_info["answer"]
    except Exception:
        return "", ""


def main():
    print(f"Loading parquet: {INPUT_PATH}")
    df = pd.read_parquet(INPUT_PATH)
    print(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}")

    extra_infos = df["extra_info"].tolist()
    qa_pairs = [_get_qa(ei) for ei in extra_infos]

    labels = [None] * len(qa_pairs)
    raws = [None] * len(qa_pairs)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_idx = {
            executor.submit(label_one, q, a): i
            for i, (q, a) in enumerate(qa_pairs)
            if (q or a)
        }
        with tqdm(total=len(future_to_idx), desc="Labeling") as pbar:
            for fut in as_completed(future_to_idx):
                idx = future_to_idx[fut]
                try:
                    label, raw = fut.result()
                except Exception as e:
                    label, raw = "UNKNOWN", f"[ERROR] {e}"
                labels[idx] = label
                raws[idx] = raw
                pbar.update(1)

    # Fill skipped rows
    for i, (q, a) in enumerate(qa_pairs):
        if labels[i] is None:
            labels[i] = "UNKNOWN"
            raws[i] = ""

    # Write labels into extra_info["answer_label"] (and keep raw for debugging)
    new_extra_infos = []
    for i, ei in enumerate(extra_infos):
        if isinstance(ei, dict):
            new_ei = copy.deepcopy(ei)
        elif ei is None:
            new_ei = {}
        else:
            try:
                new_ei = dict(ei)
            except Exception:
                new_ei = {"_original_extra_info": ei}
        new_ei["answer_label"] = labels[i]
        new_ei["answer_label_raw"] = raws[i]
        new_extra_infos.append(new_ei)

    df["extra_info"] = new_extra_infos

    # Stats
    from collections import Counter
    cnt = Counter(labels)
    err_cnt = sum(
        1 for r in raws if isinstance(r, str) and r.startswith("[ERROR]")
    )
    print(f"Done. Total: {len(labels)}, Errors: {err_cnt}")
    print(f"Label distribution: {dict(cnt)}")

    print(f"Writing parquet: {OUTPUT_PATH}")
    df.to_parquet(OUTPUT_PATH, index=False)
    print("Saved.")


if __name__ == "__main__":
    main()