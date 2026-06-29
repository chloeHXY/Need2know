"""
Tag the category-A dialogues in
    /group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/process/stages_full/05_suitable.A.jsonl
with three categories (primary context / essential attributes / non-essential
sensitive attributes) defined in
    /group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/process/new_prompt.py
using gpt-4o via the Venus LLM proxy.

Output:
    /group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/process/stages_full/06_ea_na_A.jsonl

Each output line preserves the original record and appends:
    - primary_context : List[str]
    - ea              : List[str]   # attributes essential to the context
    - na              : List[str]   # sensitive attributes NOT essential
    - tag_model       : "gpt-4o"
    - tag_ok          : bool
    - tag_error       : Optional[str]
    - tag_raw         : raw model output (only kept on parse failure for debugging)
    - usage           : OpenAI-style token usage dict (or None)

Run:
    python 3_tag_ea_na_A.py                       # process everything, 16 workers
    python 3_tag_ea_na_A.py --limit 50            # quick smoke test
    python 3_tag_ea_na_A.py --workers 32          # bump concurrency
    python 3_tag_ea_na_A.py --overwrite           # ignore existing output
    python 3_tag_ea_na_A.py --model gpt-4o-mini   # override model
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# ---------------------------------------------------------------------------
# Import the prompt template from the sibling file `new_prompt.py`.
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from new_prompt import system_prompt as PROMPT_TEMPLATE  # noqa: E402


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
INPUT_PATH = _THIS_DIR / "stages_full" / "02_suitable_B.jsonl"
OUTPUT_PATH = _THIS_DIR / "stages_full" / "03_ea_na_B.jsonl"

VENUS_URL = "http://v2.open.venus.oa.com/llmproxy/chat/completions"
DEFAULT_MODEL = "gpt-4o"

# USD per 1M tokens. Keep in sync with sibling scripts.
PRICE_PER_MTOK: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini":   {"input": 0.15,  "output": 0.60},
    "gpt-4o":        {"input": 5.00,  "output": 15.00},
    "gpt-4-turbo":   {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50,  "output": 1.50},
}


def _price_for(model: str) -> Dict[str, float]:
    if model in PRICE_PER_MTOK:
        return PRICE_PER_MTOK[model]
    best = ""
    for k in PRICE_PER_MTOK:
        if model.startswith(k) and len(k) > len(best):
            best = k
    return PRICE_PER_MTOK.get(best, {"input": 0.0, "output": 0.0})


class UsageStats:
    """Thread-safe accumulator for token usage and USD cost."""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        self._lock = threading.Lock()
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def add(self, usage: Optional[Dict[str, Any]]) -> None:
        if not usage:
            return
        pt = int(usage.get("prompt_tokens", 0) or 0)
        ct = int(usage.get("completion_tokens", 0) or 0)
        tt = int(usage.get("total_tokens", 0) or (pt + ct))
        with self._lock:
            self.calls += 1
            self.prompt_tokens += pt
            self.completion_tokens += ct
            self.total_tokens += tt

    def cost_usd(self) -> float:
        p = _price_for(self.model)
        return (
            self.prompt_tokens * p["input"] / 1_000_000.0
            + self.completion_tokens * p["output"] / 1_000_000.0
        )

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "model": self.model,
                "calls": self.calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens,
                "cost_usd": round(self.cost_usd(), 6),
            }

    def format_line(self) -> str:
        s = self.snapshot()
        return (
            f"calls={s['calls']} "
            f"in={s['prompt_tokens']} out={s['completion_tokens']} "
            f"total={s['total_tokens']} cost=${s['cost_usd']:.4f}"
        )


def _build_token() -> str:
    sid = os.environ.get("ENV_VENUS_OPENAPI_SECRET_ID")
    if not sid:
        raise RuntimeError(
            "Environment variable ENV_VENUS_OPENAPI_SECRET_ID is not set; "
            "cannot call the Venus LLM proxy."
        )
    return f"{sid}@5325"


# ---------------------------------------------------------------------------
# Prompt rendering / JSON extraction
# ---------------------------------------------------------------------------
def _render_messages(input_text: str) -> List[Dict[str, str]]:
    """Render the prompt template into chat messages.

    The template uses the literal placeholder ``{input_text}``. We avoid
    ``str.format`` because the template itself contains many curly braces
    (JSON examples). A plain ``replace`` is safe and sufficient.
    """
    rendered = PROMPT_TEMPLATE.replace("{input_text}", input_text)
    return [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. "
                "Respond ONLY with a single JSON object that strictly follows "
                "the schema described by the user."
            ),
        },
        {"role": "user", "content": rendered},
    ]


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON extraction from a model reply."""
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def _as_str_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x is not None and str(x).strip()]
    if isinstance(v, str):
        s = v.strip()
        return [s] if s else []
    return [str(v)]


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------
def call_llm(
    input_text: str,
    *,
    token: str,
    model: str,
    timeout: int = 60,
    max_retries: int = 3,
    use_json_mode: bool = True,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """Call the configured chat model via Venus proxy.

    Returns ``(parsed_json, raw_text, usage, error)``.
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": _render_messages(input_text),
        "temperature": 0.0,
    }
    if use_json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    last_err: Optional[str] = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                VENUS_URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=timeout,
            )
            if resp.status_code != 200:
                last_err = f"http {resp.status_code}: {resp.text[:300]}"
            else:
                data = resp.json()
                usage = data.get("usage") if isinstance(data, dict) else None
                try:
                    content = data["choices"][0]["message"]["content"]
                except Exception:
                    last_err = f"unexpected response shape: {str(data)[:300]}"
                    content = None
                if content is not None:
                    parsed = _extract_json(content)
                    if parsed is not None:
                        return parsed, content, usage, None
                    last_err = "model output is not valid JSON"
                    return None, content, usage, last_err
        except requests.RequestException as e:
            last_err = f"request error: {e}"
        time.sleep(min(2 ** attempt, 8))
    return None, None, None, last_err or "unknown error"


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------
def load_done_ids(path: Path) -> set:
    done: set = set()
    if not path.exists():
        return done
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            rid = obj.get("id")
            if rid is not None and obj.get("tag_ok"):
                done.add(rid)
    return done


def iter_input(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield ln, json.loads(line)
            except Exception as e:
                print(f"[warn] skip malformed line {ln}: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
def tag_one(rec: Dict[str, Any], token: str, model: str) -> Dict[str, Any]:
    text = rec.get("first_user") or ""
    out = dict(rec)
    if not isinstance(text, str) or not text.strip():
        out.update(
            {
                "primary_context": [],
                "ea": [],
                "na": [],
                "tag_model": model,
                "tag_ok": False,
                "tag_error": "empty first_user",
                "usage": None,
            }
        )
        return out

    parsed, raw, usage, err = call_llm(text, token=token, model=model)
    if parsed is None:
        out.update(
            {
                "primary_context": [],
                "ea": [],
                "na": [],
                "tag_model": model,
                "tag_ok": False,
                "tag_error": err,
                "tag_raw": raw,
                "usage": usage,
            }
        )
        return out

    out.update(
        {
            "primary_context": _as_str_list(parsed.get("primary context")),
            "ea": _as_str_list(parsed.get("attributes essential to the context")),
            "na": _as_str_list(
                parsed.get("sensitive attributes not essential to the context")
            ),
            "tag_model": model,
            "tag_ok": True,
            "tag_error": None,
            "usage": usage,
        }
    )
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(INPUT_PATH))
    ap.add_argument("--output", default=str(OUTPUT_PATH))
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"chat model name (default: {DEFAULT_MODEL})")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0,
                    help="only process the first N un-done records (0 = all)")
    ap.add_argument("--overwrite", action="store_true",
                    help="ignore existing output file and start fresh")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.overwrite and out_path.exists():
        out_path.unlink()

    token = _build_token()
    model = args.model

    done = set() if args.overwrite else load_done_ids(out_path)
    print(f"[info] model={model}")
    print(f"[info] input={in_path}")
    print(f"[info] output={out_path}")
    print(f"[info] already done: {len(done)}")

    pending: List[Dict[str, Any]] = []
    for _, rec in iter_input(in_path):
        rid = rec.get("id")
        if rid in done:
            continue
        pending.append(rec)
        if args.limit and len(pending) >= args.limit:
            break

    print(f"[info] pending: {len(pending)} (workers={args.workers})")
    if not pending:
        print("[info] nothing to do.")
        return

    write_lock = threading.Lock()
    fout = out_path.open("a", encoding="utf-8")

    stats = UsageStats(model)
    n_ok = 0
    n_fail = 0
    t0 = time.time()
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(tag_one, rec, token, model): rec for rec in pending}
            for i, fut in enumerate(as_completed(futs), 1):
                rec = futs[fut]
                try:
                    out = fut.result()
                except Exception as e:
                    out = dict(rec)
                    out.update(
                        {
                            "primary_context": [],
                            "ea": [],
                            "na": [],
                            "tag_model": model,
                            "tag_ok": False,
                            "tag_error": f"worker exception: {e}",
                            "usage": None,
                        }
                    )
                stats.add(out.get("usage"))
                with write_lock:
                    fout.write(json.dumps(out, ensure_ascii=False) + "\n")
                    fout.flush()
                if out.get("tag_ok"):
                    n_ok += 1
                else:
                    n_fail += 1
                if i % 50 == 0 or i == len(pending):
                    elapsed = time.time() - t0
                    rate = i / elapsed if elapsed > 0 else 0.0
                    print(
                        f"[progress] {i}/{len(pending)} "
                        f"ok={n_ok} fail={n_fail} "
                        f"{rate:.1f} rec/s | {stats.format_line()}"
                    )
    finally:
        fout.close()

    snap = stats.snapshot()
    price = _price_for(model)
    print(f"[done] ok={n_ok} fail={n_fail} -> {out_path}")
    print(
        f"[usage] model={model} "
        f"price=${price['input']:.2f}/Mtok in, ${price['output']:.2f}/Mtok out"
    )
    print(
        f"[usage] calls={snap['calls']} "
        f"prompt_tokens={snap['prompt_tokens']} "
        f"completion_tokens={snap['completion_tokens']} "
        f"total_tokens={snap['total_tokens']} "
        f"cost=${snap['cost_usd']:.4f}"
    )

    sidecar = out_path.with_suffix(out_path.suffix + ".usage.json")
    try:
        sidecar.write_text(json.dumps(snap, ensure_ascii=False, indent=2))
        print(f"[usage] wrote {sidecar}")
    except Exception as e:
        print(f"[usage] failed to write sidecar: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
