# -*- coding: utf-8 -*-
"""
对 `extra_info["question"]` 用 GPT-4o (Venus 代理) 进行 PII 打标。

Input  : /group/40047/eiraxyhuang/workspace/fc/DataG/inference/1_privacy/test_with_priv_query_pp.parquet
Output : /group/40047/eiraxyhuang/workspace/fc/DataG/inference/1_privacy/test_with_priv_query_pp_with_pii.parquet

每行的 `extra_info` 会被规范化为 dict 并新增两个子字段：
    - question_pii_entities      : list[str]   --- 仅保留命中的原始 span 文本
                                                  （供 0_privacy/0_eval.py 复用）
    - question_pii_entities_full : list[dict]  --- 完整结构 {text, type, confidence}

prompt 与产出格式与 PII taxonomy 见下文 ``PROMPT_TEMPLATE``。

Usage:
    python 0_pii_note.py                    # 默认输入/输出路径
    python 0_pii_note.py --limit 20         # smoke test
    python 0_pii_note.py --workers 8
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm


# =============================================================================
# Venus LLM proxy config (与项目其它脚本保持一致)
# 代理 token 见 https://venus.woa.com/#/openapi/accountManage/personalAccount
# =============================================================================
TOKEN = "vxlvrEY2AbE0DmrJreMHBlEN@5325"
URL = "http://v2.open.venus.oa.com/llmproxy/chat/completions"
MODEL = "gpt-4o"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}

# =============================================================================
# I/O config
# =============================================================================
DEFAULT_INPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/1_privacy/"
    "test_with_priv_query_pp.parquet"
)
DEFAULT_OUTPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/1_privacy/"
    "test_with_priv_query_pp_with_pii.parquet"
)

EXTRA_INFO_COL = "extra_info"
QUESTION_KEY = "question"
ENTITIES_KEY = "question_pii_entities"           # list[str]
ENTITIES_FULL_KEY = "question_pii_entities_full" # list[dict]

# =============================================================================
# Concurrency / robustness
# =============================================================================
MAX_WORKERS = 16
MAX_RETRIES = 3
RETRY_BACKOFF = 2
REQUEST_TIMEOUT = 120


# =============================================================================
# Prompt
# =============================================================================
PROMPT_TEMPLATE = """Identify all PII in the input sentence.

PII means any information that can identify, distinguish, trace, contact, locate, authenticate, or infer sensitive attributes of a specific natural person, either alone or when combined with other information.

Return only a JSON array. Each item must contain:
{
  "text": string,
  "type": one of [
    "NAME", "CONTACT", "LOCATION", "ID_NUMBER", "DATE_OF_BIRTH",
    "BIOMETRIC", "FINANCIAL", "MEDICAL", "EDUCATION", "EMPLOYMENT",
    "AUTH_CREDENTIAL", "DEVICE_ONLINE_ID", "SENSITIVE_ATTRIBUTE", "OTHER_PII"
  ],
  "confidence": "high" | "medium" | "low"
}

Rules:
- Extract only spans that appear exactly in the input.
- Do not infer missing information.
- Mark both direct identifiers and indirect/quasi-identifiers when they are linked to a specific person.
- If no PII exists, return [].
- Output JSON only.

Input:
{{sentence}}
"""

VALID_TYPES = {
    "NAME", "CONTACT", "LOCATION", "ID_NUMBER", "DATE_OF_BIRTH",
    "BIOMETRIC", "FINANCIAL", "MEDICAL", "EDUCATION", "EMPLOYMENT",
    "AUTH_CREDENTIAL", "DEVICE_ONLINE_ID", "SENSITIVE_ATTRIBUTE", "OTHER_PII",
}


def render_prompt(sentence: str) -> str:
    """Substitute the `{{sentence}}` placeholder. Use plain replace because the
    prompt also contains literal JSON braces that would break ``str.format``.
    """
    return PROMPT_TEMPLATE.replace("{{sentence}}", sentence or "")


# =============================================================================
# extra_info helpers
# =============================================================================
def to_mutable_dict(extra_info: Any) -> dict:
    """Normalize an ``extra_info`` cell into a plain mutable dict.

    Handles ``None``, ``dict``, ``numpy.ndarray`` of (key, value) pairs (which
    is how some parquet readers wrap struct columns), and any object with
    ``.items()``.
    """
    if extra_info is None:
        return {}
    if isinstance(extra_info, dict):
        return dict(extra_info)
    if isinstance(extra_info, np.ndarray):
        # struct ndarray w/ named fields
        if extra_info.dtype.names:
            return {n: extra_info[n].item() if hasattr(extra_info[n], "item")
                    else extra_info[n] for n in extra_info.dtype.names}
        # fall back: list of (k, v)
        try:
            return dict(extra_info.tolist())
        except Exception:
            return {}
    if hasattr(extra_info, "items"):
        try:
            return dict(extra_info.items())
        except Exception:
            pass
    # Last resort: try to deepcopy
    try:
        return copy.deepcopy(dict(extra_info))
    except Exception:
        return {}


def extract_question(extra_info: Any) -> str:
    if extra_info is None:
        return ""
    if isinstance(extra_info, dict):
        v = extra_info.get(QUESTION_KEY, "")
    else:
        try:
            v = extra_info[QUESTION_KEY]
        except Exception:
            return ""
    return v if isinstance(v, str) else (str(v) if v is not None else "")


# =============================================================================
# JSON extraction (the model may wrap output in ```json ... ``` or chatter)
# =============================================================================
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _strip_fences(text: str) -> str:
    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _slice_first_array(text: str) -> str | None:
    """Return the substring spanning the first balanced top-level JSON array."""
    start = text.find("[")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def parse_pii_array(raw: str) -> list[dict]:
    """Best-effort parse of the model output into list[dict]."""
    if not raw:
        return []
    body = _strip_fences(raw)
    # First try direct json
    try:
        obj = json.loads(body)
    except Exception:
        snippet = _slice_first_array(body)
        if snippet is None:
            return []
        try:
            obj = json.loads(snippet)
        except Exception:
            return []
    if not isinstance(obj, list):
        return []

    cleaned: list[dict] = []
    for item in obj:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        typ = item.get("type")
        conf = item.get("confidence")
        if not isinstance(text, str) or not text.strip():
            continue
        if not isinstance(typ, str) or typ not in VALID_TYPES:
            typ = "OTHER_PII"
        if not isinstance(conf, str) or conf not in {"high", "medium", "low"}:
            conf = "low"
        cleaned.append({
            "text": text.strip(),
            "type": typ,
            "confidence": conf,
        })
    return cleaned


# =============================================================================
# LLM call with retries
# =============================================================================
def call_gpt(prompt: str) -> str:
    """Single GPT-4o call with retries; returns raw content or ''."""
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

    print(f"[llm-error] {last_err}", flush=True)
    return ""


def annotate_one(question: str) -> tuple[list[str], list[dict], str]:
    """Annotate a single question. Returns (texts, full, raw_response)."""
    if not question or not question.strip():
        return [], [], ""
    raw = call_gpt(render_prompt(question))
    full = parse_pii_array(raw)
    texts = [e["text"] for e in full]
    return texts, full, raw


# =============================================================================
# Main
# =============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="GPT-4o based PII annotation for extra_info['question']."
    )
    parser.add_argument("--input", "-i", default=DEFAULT_INPUT)
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--limit", type=int, default=0,
                        help="Only process the first N rows (0 = all).")
    args = parser.parse_args()

    print(f"[load] reading parquet: {args.input}", flush=True)
    df = pd.read_parquet(args.input)
    print(f"[load] rows={len(df)} cols={df.columns.tolist()}", flush=True)

    if EXTRA_INFO_COL not in df.columns:
        print(f"[ERROR] column '{EXTRA_INFO_COL}' not found in input parquet.",
              file=sys.stderr)
        sys.exit(2)

    n = len(df)
    if args.limit and args.limit < n:
        df = df.iloc[: args.limit].reset_index(drop=True)
        n = len(df)
    print(f"[plan] annotating {n} rows with workers={args.workers}", flush=True)

    extras_raw = df[EXTRA_INFO_COL].tolist()
    extras_dict = [to_mutable_dict(x) for x in extras_raw]
    questions = [extract_question(x) for x in extras_dict]

    pii_texts: list[list[str]] = [[] for _ in range(n)]
    pii_full: list[list[dict]] = [[] for _ in range(n)]
    raw_responses: list[str] = [""] * n

    def _run(i: int):
        try:
            texts, full, raw = annotate_one(questions[i])
        except Exception as e:
            print(f"[task-error] idx={i} err={e}", flush=True)
            return i, [], [], ""
        return i, texts, full, raw

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_run, i): i for i in range(n)}
        with tqdm(total=len(futures), desc="PII tagging") as pbar:
            for fut in as_completed(futures):
                try:
                    i, texts, full, raw = fut.result()
                except Exception as e:
                    i = futures[fut]
                    texts, full, raw = [], [], ""
                    print(f"[future-error] idx={i} err={e}", flush=True)
                pii_texts[i] = texts
                pii_full[i] = full
                raw_responses[i] = raw
                pbar.update(1)

    # ---- write back into extra_info ----
    new_extras: list[dict] = []
    for ei, texts, full in zip(extras_dict, pii_texts, pii_full):
        ei[ENTITIES_KEY] = list(texts)
        ei[ENTITIES_FULL_KEY] = list(full)
        new_extras.append(ei)
    df[EXTRA_INFO_COL] = new_extras

    # ---- stats ----
    n_with_pii = sum(1 for t in pii_texts if t)
    n_items = sum(len(t) for t in pii_texts)
    n_empty_q = sum(1 for q in questions if not (q or "").strip())
    n_empty_resp = sum(1 for r in raw_responses if not r)
    print("\n=== PII annotation summary ===", flush=True)
    print(f"  total rows                : {n}")
    print(f"  rows with empty question  : {n_empty_q}")
    print(f"  rows with empty response  : {n_empty_resp}")
    print(f"  rows with >=1 PII item    : {n_with_pii}")
    print(f"  total PII items           : {n_items}")

    # ---- save ----
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    print(f"\n[save] writing parquet: {args.output}", flush=True)
    df.to_parquet(args.output, index=False)
    print("[save] done.", flush=True)


if __name__ == "__main__":
    main()