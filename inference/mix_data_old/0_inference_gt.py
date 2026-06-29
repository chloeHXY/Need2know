import os
import json
import time
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# 代理token请前往 https://venus.woa.com/#/openapi/accountManage/personalAccount  查看代理token，并替换后调用
TOKEN = "vxlvrEY2AbE0DmrJreMHBlEN@5325"
URL = "http://v2.open.venus.oa.com/llmproxy/chat/completions"
MODEL = "gpt-4o"

INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/test_with_priv_query.parquet"
# INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/test_with_priv_query.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/one.parquet"


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

SYSTEM_PROMPT = "Please answer the question and provide the answer directly, without explanation."


def call_llm(question: str) -> str:
    """Call the LLM proxy with retries. Returns the answer string, or an error marker."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        **GEN_PARAMS
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


def extract_question(extra_info) -> str:
    """Extract the 'question' field from extra_info (which may be a dict-like object)."""
    if extra_info is None:
        return ""
    if isinstance(extra_info, dict):
        return extra_info.get("question", "") or ""
    # Some parquet readers may return objects supporting item access
    try:
        return extra_info["question"] or ""
    except Exception:
        return ""


def main():
    print(f"Loading parquet: {INPUT_PATH}")
    df = pd.read_parquet(INPUT_PATH)
    print(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}")

    questions = [extract_question(ei) for ei in df["extra_info"].tolist()]
    # questions = df["priv_query"].tolist()
    answers = [None] * len(questions)

    # Concurrent inference with index tracking to preserve order.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_idx = {
            executor.submit(call_llm, q): i for i, q in enumerate(questions) if q
        }
        with tqdm(total=len(future_to_idx), desc="Inferencing") as pbar:
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

    df["gpt_answer"] = answers

    # Sanity stats
    err_cnt = sum(1 for a in answers if isinstance(a, str) and a.startswith("[ERROR]"))
    print(f"Done. Total: {len(answers)}, Errors: {err_cnt}")

    print(f"Writing parquet: {OUTPUT_PATH}")
    df.to_parquet(OUTPUT_PATH, index=False)
    print("Saved.")


if __name__ == "__main__":
    main()