# -*- coding: utf-8 -*-
"""
PAPILLON Step 1 (single-content variant): Prompt Creator for one query.

This is a simplified version of `step1_creator.py` that runs Creator inference
on a SINGLE user content string (instead of iterating over a parquet file).

Usage examples:

    # 1) Pass content directly via CLI
    python step1_creator_single.py --content "Hi, I'm Jane. ..."

    # 2) Pipe content via stdin
    echo "Hi, I'm Jane. ..." | python step1_creator_single.py

    # 3) Read content from a text file
    python step1_creator_single.py --content-file ./query.txt

    # 4) Import and call from Python
    from step1_creator_single import run_single
    priv_query = run_single("Hi, I'm Jane. ...")
"""

import os
import re
import sys
import json
import time
import uuid
import argparse
import requests

# Reuse the Creator prompt template defined in papillon/prompt.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prompt import Creator as CREATOR_PROMPT  # noqa: E402


# =============================================================================
# Local LLM service configuration (mirrors step1_creator.py)
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
# Generation configuration
# =============================================================================
MAX_RETRIES = 3
RETRY_BACKOFF = 2
REQUEST_TIMEOUT = 300
ENABLE_STREAM = True
DEBUG_STREAM = False

GEN_PARAMS = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 40,
    "repetition_penalty": 1,
    "output_seq_len": 1024,
    "max_input_seq_len": 4096,
}


# =============================================================================
# Prompt building / streaming helpers (kept consistent with step1_creator.py)
# =============================================================================
def build_messages(user_query: str):
    """Render the Creator prompt with the user query."""
    # The Creator template contains the literal placeholder "{user query}"
    # (with a space), so use a manual replace instead of .format().
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


def call_creator(user_query: str, return_raw: bool = False) -> str:
    """Call the local llama service with retries.

    Returns the extracted createdPrompt (q'). When return_raw=True, returns the
    full raw model output (including rationale/markers) instead.
    On failure, returns "[ERROR] ..." string.
    """
    messages = build_messages(user_query)
    payload = {
        "model": MODEL,
        "query_id": "papillon_step1_single_" + str(uuid.uuid4()),
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
                    return text if return_raw else _extract_created_prompt(text)
                last_err = "Empty response"
        except Exception as e:
            last_err = f"Exception: {e}"

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF ** attempt)

    return f"[ERROR] {last_err}"


def run_single(content: str, return_raw: bool = False) -> str:
    """Convenience wrapper for programmatic use."""
    return call_creator(content, return_raw=return_raw)


# =============================================================================
# CLI entry
# =============================================================================
def _read_content(args) -> str:
    if args.content is not None and args.content != "":
        return args.content
    if args.content_file:
        with open(args.content_file, "r", encoding="utf-8") as f:
            return f.read()
    # Fallback: stdin (only if not a TTY)
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="PAPILLON Step1 single-content Creator inference"
    )
    parser.add_argument("--content", type=str, default=None,
                        help="User query content (q) to be transformed into q'")
    parser.add_argument("--content-file", type=str, default=None,
                        help="Path to a text file containing the user query")
    parser.add_argument("--raw", action="store_true",
                        help="Return the full raw model output (including "
                             "rationale and markers) instead of just createdPrompt")
    parser.add_argument("--output", type=str, default=None,
                        help="Optional output file path; if omitted, prints to stdout")
    args = parser.parse_args()

    content = _read_content(args)
    if not content or not content.strip():
        print("[error] No content provided. Use --content / --content-file / stdin.",
              file=sys.stderr)
        sys.exit(2)

    print(f"[input] length={len(content)} chars", file=sys.stderr)
    print("[run] calling creator ...", file=sys.stderr)

    result = call_creator(content, return_raw=args.raw)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"[save] written to {args.output}", file=sys.stderr)
    else:
        print("===== priv_query (q') =====")
        print(result)


if __name__ == "__main__":
    main()
