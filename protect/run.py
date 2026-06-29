#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Formal pipeline runner for the contextual privacy reformulation framework.

The pipeline (see pipeline.md) processes a user prompt in 3 stages:
    1. Context identification         (domain / task)
    2. Sensitive info classification  (essential / non-essential)
    3. Reformulation                  (rewrite while preserving intent)

Two execution modes are supported:
    - single sentence test:
        python run.py --text "your prompt here"
    - parquet batch mode (reads extra_info.question, writes priv_query):
        python run.py --parquet /path/to/input.parquet \
                      --output  /path/to/output.parquet

Default parquet (when --parquet is omitted while --mode parquet):
    /group/40047/eiraxyhuang/workspace/fc/DataG/protect/0_gt_ref.parquet
"""

import argparse
import json
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests
import sseclient

try:
    from tqdm import tqdm  # type: ignore
except ImportError:  # pragma: no cover - optional
    tqdm = None  # type: ignore

from prompt import (
    INTENT_DETECTION_PROMPT,
    TASK_DETECTION_PROMPT,
    ESSENTIAL_PROMPT,
    NON_ESSENTIAL_PROMPT,
    REFORMULATION_PROMPT,
)


# =========================================================
# LLM client (OpenAPI / SSE, mirrors test2.py)
# =========================================================

DEFAULT_SS_URL = "http://21.119.245.18:81/openapi/chat/completions"
DEFAULT_MODEL = "qwen7b"
DEFAULT_WSID = "10143"
DEFAULT_AUTH = "Bearer 7auGXNATFSKl7dF"


class LLMClient:
    """Thin wrapper around the internal OpenAPI chat-completions endpoint."""

    def __init__(
        self,
        ss_url: str = DEFAULT_SS_URL,
        model: str = DEFAULT_MODEL,
        wsid: str = DEFAULT_WSID,
        auth: str = DEFAULT_AUTH,
        temperature: float = 0.0,
        top_p: float = 0.8,
        top_k: int = 40,
        repetition_penalty: float = 1.0,
        output_seq_len: int = 1024,
        max_input_seq_len: int = 4096,
        stream: bool = False,
        timeout: int = 180,
        system_prompt: str = "You are a helpful assistant.",
    ):
        self.ss_url = ss_url
        self.model = model
        self.wsid = wsid
        self.auth = auth
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.repetition_penalty = repetition_penalty
        self.output_seq_len = output_seq_len
        self.max_input_seq_len = max_input_seq_len
        self.stream = stream
        self.timeout = timeout
        self.system_prompt = system_prompt

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": self.auth,
            "Wsid": self.wsid,
        }

    def _payload(self, user_prompt: str) -> Dict[str, Any]:
        return {
            "model": self.model,
            "query_id": "run_" + str(uuid.uuid4()),
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repetition_penalty": self.repetition_penalty,
            "output_seq_len": self.output_seq_len,
            "max_input_seq_len": self.max_input_seq_len,
            "stream": self.stream,
        }

    def generate(self, user_prompt: str) -> str:
        resp = requests.post(
            self.ss_url,
            headers=self._headers(),
            json=self._payload(user_prompt),
            stream=self.stream,
            timeout=self.timeout,
        )
        resp.raise_for_status()

        if not self.stream:
            data = resp.json()
            return self._extract_non_stream(data)

        chunks: List[str] = []
        client = sseclient.SSEClient(resp)
        for event in client.events():
            if not event.data:
                continue
            if event.data.strip() == "[DONE]":
                break
            try:
                data_js = json.loads(event.data)
            except json.JSONDecodeError:
                continue
            try:
                delta = data_js["choices"][0].get("delta", {})
                piece = delta.get("content")
                if piece is None:
                    # Some servers put final text in "message"
                    piece = data_js["choices"][0].get("message", {}).get("content")
                if piece:
                    chunks.append(piece)
            except (KeyError, IndexError, TypeError):
                continue
        return "".join(chunks).strip()

    @staticmethod
    def _extract_non_stream(data: Dict[str, Any]) -> str:
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            return json.dumps(data, ensure_ascii=False)


# =========================================================
# Output parsing helpers
# =========================================================

_LIST_RE = re.compile(r"\[(.*?)\]", re.DOTALL)


def _clean_label(line: str) -> str:
    """Strip leading category prefixes like 'Task: xxx' or '-> xxx'."""
    line = line.strip().strip("`").strip()
    # take the first non-empty line
    for piece in line.splitlines():
        piece = piece.strip()
        if not piece:
            continue
        # remove arrows / colons / bullets
        piece = re.sub(r"^[\-\*\u2022\u2192>:\s]+", "", piece)
        if ":" in piece:
            tail = piece.split(":", 1)[1].strip()
            if tail:
                piece = tail
        # cut at first whitespace if the model added trailing prose
        piece = piece.split()[0] if piece else piece
        return piece.strip(".,:;`\"' ")
    return line.strip()


def parse_intent(raw: str) -> str:
    return _clean_label(raw)


def parse_task(raw: str) -> str:
    return _clean_label(raw)


def parse_info_list(raw: str, header_keyword: str) -> List[str]:
    """
    Parse outputs like:
        ESSENTIAL INFORMATION: ["item1", "item2"]
        NON-ESSENTIAL INFORMATION: [item1, item2]
    Returns a list of strings (possibly empty).
    """
    if not raw:
        return []

    # Try to locate the section after the header keyword (case-insensitive)
    text = raw
    idx = text.upper().find(header_keyword.upper())
    if idx != -1:
        text = text[idx:]

    match = _LIST_RE.search(text)
    if not match:
        return []

    inner = match.group(1).strip()
    if not inner:
        return []

    # Try strict JSON first
    try:
        parsed = json.loads("[" + inner + "]")
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except json.JSONDecodeError:
        pass

    # Fallback: split by commas, strip quotes
    items = []
    for piece in re.split(r",(?![^\[\]]*\])", inner):
        piece = piece.strip().strip("'\"` ").strip()
        if piece:
            items.append(piece)
    return items


def parse_reformulation(raw: str) -> str:
    """
    The reformulation prompt asks for ONLY the reformulated text on a new line.
    We keep the last non-empty line if the model adds prefatory text.
    """
    if not raw:
        return ""
    text = raw.strip().strip("`").strip()
    # Strip leading "Reformulated:" style prefix if present
    text = re.sub(r"(?im)^\s*reformulated\s*[:\-]\s*", "", text)
    # Remove surrounding quotes
    text = text.strip().strip('"').strip("'").strip()
    # Take the last non-empty line which is most likely the answer
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    return lines[-1].strip().strip('"').strip("'").strip()


# =========================================================
# Pipeline stages
# =========================================================

def stage_identify_intent(text: str, llm: LLMClient) -> str:
    raw = llm.generate(INTENT_DETECTION_PROMPT.format(input_text=text))
    return parse_intent(raw)


def stage_identify_task(text: str, llm: LLMClient) -> str:
    raw = llm.generate(TASK_DETECTION_PROMPT.format(input_text=text))
    return parse_task(raw)


def stage_classify_essential(text: str, intent: str, llm: LLMClient) -> List[str]:
    raw = llm.generate(ESSENTIAL_PROMPT.format(intent=intent, text=text))
    return parse_info_list(raw, "ESSENTIAL INFORMATION")


def stage_classify_non_essential(text: str, intent: str, llm: LLMClient) -> List[str]:
    raw = llm.generate(NON_ESSENTIAL_PROMPT.format(intent=intent, text=text))
    return parse_info_list(raw, "NON-ESSENTIAL INFORMATION")


def stage_reformulate(
    text: str,
    intent: str,
    essential_info: List[str],
    removable_info: List[str],
    llm: LLMClient,
) -> str:
    prompt = REFORMULATION_PROMPT.format(
        text=text,
        intent=intent,
        essential_info=json.dumps(essential_info, ensure_ascii=False),
        removable_info=json.dumps(removable_info, ensure_ascii=False),
    )
    raw = llm.generate(prompt)
    return parse_reformulation(raw)


def run_pipeline(text: str, llm: LLMClient, verbose: bool = False) -> Dict[str, Any]:
    """Execute all 3 pipeline stages on a single input text."""
    intent = stage_identify_intent(text, llm)
    if verbose:
        print(f"  [intent] {intent}")

    task = stage_identify_task(text, llm)
    if verbose:
        print(f"  [task]   {task}")

    essential = stage_classify_essential(text, intent, llm)
    non_essential = stage_classify_non_essential(text, intent, llm)
    if verbose:
        print(f"  [essential]     {essential}")
        print(f"  [non-essential] {non_essential}")

    if not non_essential:
        reformulated = text
    else:
        reformulated = stage_reformulate(text, intent, essential, non_essential, llm)
        if not reformulated:
            reformulated = text

    return {
        "original": text,
        "intent": intent,
        "task": task,
        "essential": essential,
        "non_essential": non_essential,
        "priv_query": reformulated,
    }


def _process_row(idx: int, question: Optional[str], llm: LLMClient) -> Dict[str, Any]:
    """Worker for ThreadPoolExecutor; never raises."""
    if not question:
        return {"idx": idx, "priv_query": "", "error": None, "skipped": True}
    try:
        result = run_pipeline(question, llm, verbose=False)
        return {
            "idx": idx,
            "priv_query": result["priv_query"],
            "error": None,
            "skipped": False,
        }
    except Exception as e:  # noqa: BLE001
        return {
            "idx": idx,
            "priv_query": question,  # fallback to original
            "error": str(e),
            "skipped": False,
        }


# =========================================================
# Parquet I/O
# =========================================================

def _extract_question(extra_info: Any) -> Optional[str]:
    """Get the 'question' field from an extra_info cell (dict / json-string)."""
    if extra_info is None:
        return None
    if isinstance(extra_info, dict):
        q = extra_info.get("question")
        return q if isinstance(q, str) else None
    if isinstance(extra_info, str):
        try:
            data = json.loads(extra_info)
            if isinstance(data, dict):
                q = data.get("question")
                return q if isinstance(q, str) else None
        except json.JSONDecodeError:
            return None
    return None


def run_parquet(
    input_path: str,
    output_path: str,
    llm: LLMClient,
    limit: Optional[int] = None,
    workers: int = 8,
    checkpoint_every: int = 200,
) -> None:
    try:
        import pandas as pd  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "pandas is required for parquet mode. Install with: pip install pandas pyarrow"
        ) from e

    import pandas as pd

    print(f"[parquet] reading: {input_path}")
    df = pd.read_parquet(input_path)
    print(f"[parquet] rows: {len(df)}, columns: {list(df.columns)}")

    if "extra_info" not in df.columns:
        raise SystemExit("Input parquet does not contain an 'extra_info' column.")

    if "priv_query" not in df.columns:
        df["priv_query"] = ""

    n = len(df) if limit is None else min(limit, len(df))
    print(f"[parquet] processing {n} rows with {workers} workers")

    # Pre-extract questions to keep the main loop free of pandas access from threads
    questions: List[Optional[str]] = [
        _extract_question(df.at[i, "extra_info"]) for i in range(n)
    ]

    t0 = time.time()
    completed = 0
    errors = 0
    skipped = 0

    progress = None
    if tqdm is not None:
        progress = tqdm(total=n, desc="priv_query", unit="row", dynamic_ncols=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_process_row, i, questions[i], llm): i for i in range(n)
        }
        for fut in as_completed(futures):
            res = fut.result()
            i = res["idx"]
            df.at[i, "priv_query"] = res["priv_query"]
            completed += 1
            if res["skipped"]:
                skipped += 1
            if res["error"]:
                errors += 1

            if progress is not None:
                progress.update(1)
                progress.set_postfix(err=errors, skip=skipped, refresh=False)
            elif completed % 20 == 0 or completed == n:
                elapsed = time.time() - t0
                rate = completed / elapsed if elapsed > 0 else 0.0
                print(
                    f"[progress] {completed}/{n} | err={errors} skip={skipped} | "
                    f"{rate:.2f} rows/s | elapsed={elapsed:.1f}s"
                )

            if checkpoint_every > 0 and completed % checkpoint_every == 0:
                df.to_parquet(output_path, index=False)

    if progress is not None:
        progress.close()

    df.to_parquet(output_path, index=False)
    elapsed = time.time() - t0
    print(
        f"[done] {completed}/{n} rows | err={errors} skip={skipped} | "
        f"elapsed={elapsed:.1f}s -> {output_path}"
    )


# =========================================================
# CLI
# =========================================================

DEFAULT_PARQUET = "/group/40047/eiraxyhuang/workspace/fc/DataG/protect/0_gt_ref.parquet"


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Contextual privacy reformulation pipeline."
    )
    p.add_argument(
        "--mode",
        choices=["text", "parquet"],
        default=None,
        help="Run mode. If omitted, inferred from --text / --parquet.",
    )
    p.add_argument("--text", type=str, default=None, help="Single input prompt to test.")
    p.add_argument(
        "--parquet",
        type=str,
        default=None,
        help=f"Input parquet path (default: {DEFAULT_PARQUET} when --mode parquet).",
    )
    p.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output parquet path (default: <input>.priv.parquet).",
    )
    p.add_argument("--limit", type=int, default=None, help="Process only first N rows.")
    p.add_argument("--model", type=str, default=DEFAULT_MODEL, help="LLM model name.")
    p.add_argument("--ss-url", type=str, default=DEFAULT_SS_URL, help="Endpoint URL.")
    p.add_argument(
        "--stream",
        action="store_true",
        help="Enable SSE streaming (default off; off is better for concurrency).",
    )
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument(
        "--workers",
        type=int,
        default=20,
        help="Concurrent worker threads in parquet mode (default: 8).",
    )
    p.add_argument(
        "--checkpoint-every",
        type=int,
        default=200,
        help="Flush parquet to disk every N completed rows (0 to disable).",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_argparser().parse_args(argv)

    # Infer mode
    mode = args.mode
    if mode is None:
        if args.text is not None:
            mode = "text"
        elif args.parquet is not None:
            mode = "parquet"
        else:
            # default: simple test sentence
            mode = "text"
            args.text = (
                "My friend Mark, who was just laid off from Google, "
                "is looking for a job where he can use ML and Python. "
                "Do you have any advice for him?"
            )

    llm = LLMClient(
        ss_url=args.ss_url,
        model=args.model,
        temperature=args.temperature,
        stream=args.stream,
    )

    if mode == "text":
        text = args.text
        if not text:
            print("Error: --text is required in text mode.", file=sys.stderr)
            return 2

        print("=" * 60)
        print("Original prompt:")
        print(text)
        print("-" * 60)
        result = run_pipeline(text, llm, verbose=True)
        print("-" * 60)
        print("Reformulated (priv_query):")
        print(result["priv_query"])
        print("=" * 60)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # parquet mode
    input_path = args.parquet or DEFAULT_PARQUET
    output_path = args.output
    if output_path is None:
        if input_path.endswith(".parquet"):
            output_path = input_path[: -len(".parquet")] + ".priv.parquet"
        else:
            output_path = input_path + ".priv.parquet"

    run_parquet(
        input_path=input_path,
        output_path=output_path,
        llm=llm,
        limit=args.limit,
        workers=args.workers,
        checkpoint_every=args.checkpoint_every,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
