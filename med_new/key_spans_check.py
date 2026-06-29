"""
key_spans 必要性二次校验（方案 2：Leave-One-Out 消融）

逻辑：
  对每条数据的每个 key_span：
    1. 在 question 中把该 span 用 [REDACTED] 占位（保留其他 spans 与上下文）。
    2. 让 LLM 直接只输出正确选项字母（A/B/C/D/E），不做自然语言解释。
    3. 把模型选出的字母与 extra_info["answer_label"]（gold）比较：
         - 不同 -> 该 span 必要 (is_necessary=True)
         - 相同 -> 该 span 对解题贡献低，标记为可疑冗余 (is_necessary=False)

输入  : med.anonymized.cleaned.with_answer_label.parquet
输出  : med.anonymized.cleaned.with_span_check.parquet
新增字段（写在 extra_info 内）：
  - key_spans 内每个 item 增加 is_necessary / masked_pred / masked_pred_raw
  - key_spans_check_summary：整行汇总（必要数 / 总数 / 是否全必要）
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

# ---- LLM proxy config (与 打标.py / 答案打标.py 保持一致) ----
TOKEN = "vxlvrEY2AbE0DmrJreMHBlEN@5325"
URL = "http://v2.open.venus.oa.com/llmproxy/chat/completions"
MODEL = "gpt-4o"

INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_answer_label.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_span_check.parquet"

MAX_WORKERS = 16
MAX_RETRIES = 3
RETRY_BACKOFF = 2
REQUEST_TIMEOUT = 120

REDACT_TOKEN = "[REDACTED]"
VALID_LABELS = {"A", "B", "C", "D", "E"}

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}

# 让模型直接吐出一个字母即可，output_seq_len 拉到极小
GEN_PARAMS = {
    "temperature": 0,
    "top_p": 0.8,
    "top_k": 40,
    "repetition_penalty": 1,
    "output_seq_len": 8,
    "max_input_seq_len": 4096,
}

PROMPT_TEMPLATE = """\
You are a medical multiple-choice solver.

You will be given a question with options A, B, C, D, and optionally E.
Some information in the question may be replaced with the placeholder [REDACTED].
Use only the information that is still visible to pick the single best option.

Rules:
1. Output exactly ONE uppercase letter: A, B, C, D, or E.
2. No explanation, no punctuation, no extra text.
3. If you cannot decide with the visible information, still output the single most likely letter (do NOT output UNKNOWN).

question:
{question}

Output:"""


# ---------------- helpers ----------------

def to_dict(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    try:
        return dict(obj)
    except Exception:
        return {}


def to_list(obj):
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    try:
        return list(obj)
    except Exception:
        return []


def normalize_letter(text: str) -> str:
    """从模型原始输出里抽取 A/B/C/D/E，抽不到返回空字符串。"""
    if text is None:
        return ""
    s = str(text).strip().upper()
    if not s:
        return ""
    m = re.search(r"\b([ABCDE])\b", s)
    if m:
        return m.group(1)
    m = re.search(r"[ABCDE]", s)
    if m:
        return m.group(0)
    return ""


def mask_span_in_question(question: str, span: str) -> str:
    """把 question 中所有出现的 span 替换成 [REDACTED]。

    1) 优先精确替换；
    2) 若精确替换无效（可能因 span 含多余空白），回退为空白归一化后做正则替换。
    """
    if not span:
        return question
    if span in question:
        return question.replace(span, REDACT_TOKEN)

    # 回退：把 span 内连续空白视为 \s+ 做正则匹配
    pattern = re.escape(span.strip())
    pattern = re.sub(r"\\\s+", r"\\s+", pattern)
    try:
        new_q, n = re.subn(pattern, REDACT_TOKEN, question, flags=re.IGNORECASE)
        if n > 0:
            return new_q
    except re.error:
        pass
    return question  # 找不到时原样返回（这种 span 本身就不忠实）


def call_llm(messages: list) -> str:
    if not messages:
        return ""
    payload = {"model": MODEL, "messages": messages, **GEN_PARAMS}
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                URL, headers=HEADERS, data=json.dumps(payload), timeout=REQUEST_TIMEOUT
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


def predict_letter(masked_question: str) -> tuple:
    """对一个被遮盖后的 question 调一次模型，返回 (letter, raw)."""
    user_content = PROMPT_TEMPLATE.format(question=masked_question.strip())
    messages = [{"role": "user", "content": user_content}]
    raw = call_llm(messages)
    if isinstance(raw, str) and raw.startswith("[ERROR]"):
        return "", raw
    return normalize_letter(raw), raw


# ---------------- main ----------------

def build_tasks(df: pd.DataFrame):
    """Flatten all (row_idx, span_idx, masked_question) tasks.

    跳过条件：
      * 无 question
      * gold_label 不是 A-E
      * span 在 question 中找不到（无法做有效消融）
    """
    tasks = []          # list of (row_idx, span_idx, masked_q)
    row_meta = []       # list of dict per row：question / gold / spans / skip 信息
    for row_idx, ei in enumerate(df["extra_info"].tolist()):
        d = to_dict(ei)
        question = str(d.get("question", "") or "")
        gold = str(d.get("answer_label", "") or "").strip().upper()
        spans = [to_dict(it) for it in to_list(d.get("key_spans"))]

        meta = {
            "question": question,
            "gold": gold,
            "spans": spans,
            # per-span 占位：每个 span 一份预测结果
            "results": [
                {"is_necessary": None, "masked_pred": "", "masked_pred_raw": "",
                 "skipped_reason": ""}
                for _ in spans
            ],
        }

        if not question or gold not in VALID_LABELS or not spans:
            for r in meta["results"]:
                r["skipped_reason"] = (
                    "no_question" if not question else
                    "bad_gold_label" if gold not in VALID_LABELS else
                    "no_spans"
                )
            row_meta.append(meta)
            continue

        for span_idx, item in enumerate(spans):
            span_text = str(item.get("span", "") or "")
            if not span_text:
                meta["results"][span_idx]["skipped_reason"] = "empty_span"
                continue
            masked_q = mask_span_in_question(question, span_text)
            if masked_q == question:
                # span 不在 question 里 -> 标记不忠实，无法消融
                meta["results"][span_idx]["skipped_reason"] = "span_not_in_question"
                continue
            tasks.append((row_idx, span_idx, masked_q))

        row_meta.append(meta)
    return tasks, row_meta


def main():
    print(f"Loading parquet: {INPUT_PATH}")
    df = pd.read_parquet(INPUT_PATH)
    print(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}")

    tasks, row_meta = build_tasks(df)
    print(f"Total ablation tasks: {len(tasks)} (across {len(df)} rows)")

    # 并发跑 leave-one-out
    if tasks:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_key = {
                executor.submit(predict_letter, masked_q): (row_idx, span_idx)
                for (row_idx, span_idx, masked_q) in tasks
            }
            with tqdm(total=len(future_to_key), desc="Ablation") as pbar:
                for fut in as_completed(future_to_key):
                    row_idx, span_idx = future_to_key[fut]
                    try:
                        letter, raw = fut.result()
                    except Exception as e:
                        letter, raw = "", f"[ERROR] {e}"
                    res = row_meta[row_idx]["results"][span_idx]
                    res["masked_pred"] = letter
                    res["masked_pred_raw"] = raw
                    gold = row_meta[row_idx]["gold"]
                    if not letter:
                        # 模型没给出有效字母：当作"无法判断"，必要性置 None
                        res["is_necessary"] = None
                    else:
                        # 遮盖后预测变了 -> 必要；预测不变 -> 可疑冗余
                        res["is_necessary"] = (letter != gold)
                    pbar.update(1)

    # 把结果写回 extra_info
    new_extra_infos = []
    summary_total_spans = 0
    summary_necessary = 0
    summary_skipped = 0
    summary_uncertain = 0

    for row_idx, ei in enumerate(df["extra_info"].tolist()):
        if isinstance(ei, dict):
            new_ei = copy.deepcopy(ei)
        elif ei is None:
            new_ei = {}
        else:
            try:
                new_ei = dict(ei)
            except Exception:
                new_ei = {"_original_extra_info": ei}

        meta = row_meta[row_idx]
        spans = meta["spans"]
        results = meta["results"]

        new_key_spans = []
        n_total = len(spans)
        n_necessary = 0
        n_skipped = 0
        n_uncertain = 0
        for item, res in zip(spans, results):
            new_item = copy.deepcopy(item)
            new_item["masked_pred"] = res["masked_pred"]
            new_item["masked_pred_raw"] = res["masked_pred_raw"]
            new_item["skipped_reason"] = res["skipped_reason"]
            new_item["is_necessary"] = res["is_necessary"]
            new_key_spans.append(new_item)

            if res["skipped_reason"]:
                n_skipped += 1
            elif res["is_necessary"] is True:
                n_necessary += 1
            elif res["is_necessary"] is None:
                n_uncertain += 1
            # else: is_necessary == False -> 可疑冗余

        new_ei["key_spans"] = new_key_spans
        new_ei["key_spans_check_summary"] = {
            "gold_label": meta["gold"],
            "n_total": n_total,
            "n_necessary": n_necessary,
            "n_redundant": n_total - n_necessary - n_skipped - n_uncertain,
            "n_uncertain": n_uncertain,
            "n_skipped": n_skipped,
            "all_necessary": (n_total > 0 and n_necessary == n_total),
        }
        new_extra_infos.append(new_ei)

        summary_total_spans += n_total
        summary_necessary += n_necessary
        summary_skipped += n_skipped
        summary_uncertain += n_uncertain

    df["extra_info"] = new_extra_infos

    print("==== Summary ====")
    print(f"rows           : {len(df)}")
    print(f"total spans    : {summary_total_spans}")
    print(f"necessary      : {summary_necessary}")
    print(f"redundant      : {summary_total_spans - summary_necessary - summary_skipped - summary_uncertain}")
    print(f"uncertain (no letter) : {summary_uncertain}")
    print(f"skipped (not in q / bad gold) : {summary_skipped}")

    print(f"Writing parquet: {OUTPUT_PATH}")
    df.to_parquet(OUTPUT_PATH, index=False)
    print("Saved.")


if __name__ == "__main__":
    main()
