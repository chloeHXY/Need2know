"""
Classify each user query in
    /group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/process/stages_full/01_struct_lt250.jsonl
using the contextual-privacy filtering prompt defined in
    /group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/process/find.py
via gpt-4o-mini on the Venus LLM proxy.

Output:
    /group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/process/stages_full/05_suitable.jsonl
    /group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/process/stages_full/05_suitable.A.jsonl
        (mirror of records whose suit_category == "A")

Each output line preserves the original record and appends:
    - suit_category                  : "A" | "B" | "C" | "D" | "E" | None
    - is_suitable_for_main_benchmark : bool | None
    - primary_task                   : str
    - suit_reason                    : str
    - suit_confidence                : float | None
    - suit_model                     : "gpt-4o-mini"
    - suit_ok                        : bool
    - suit_error                     : Optional[str]
    - suit_raw                       : raw model output (only on parse failure)
    - usage                          : OpenAI-style token usage dict (or None)

Run:
    python 2_filter_suitable.py                    # process everything, 16 workers
    python 2_filter_suitable.py --limit 50         # quick smoke test
    python 2_filter_suitable.py --workers 32       # bump concurrency
    python 2_filter_suitable.py --overwrite        # ignore existing output
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
# Import the prompt template from the sibling file `find.py`.
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from find import system_prompt as PROMPT_TEMPLATE  # noqa: E402


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
INPUT_PATH = _THIS_DIR / "stages_full" / "01_struct.jsonl"
OUTPUT_PATH = _THIS_DIR / "stages_full" / "02_suitable.jsonl"
OUTPUT_A_PATH = _THIS_DIR / "stages_full" / "02_suitable.A.jsonl"


VENUS_URL = "http://v2.open.venus.oa.com/llmproxy/chat/completions"
MODEL_NAME = "gpt-4o-mini"

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

    def __init__(self, model: str = MODEL_NAME) -> None:
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
# `find.system_prompt` already plays the role of the system message; the
# user query is injected via the literal placeholder `{{USER_QUERY}}`.
def _render_messages(user_query: str) -> List[Dict[str, str]]:
    # Use plain `replace` (NOT str.format) because the template contains
    # many curly braces (JSON schema examples).
    rendered_system = PROMPT_TEMPLATE.replace("{{USER_QUERY}}", "").rstrip()
    return [
        {"role": "system", "content": rendered_system},
        {
            "role": "user",
            "content": (
                "Classify the following user query. "
                "Respond ONLY with a single JSON object that strictly follows "
                "the schema described in the system prompt.\n\n"
                "USER QUERY:\n"
                f"{user_query}"
            ),
        },
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


_VALID_CATS = {"A", "B", "C", "D", "E"}


def _norm_category(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip().upper()
    # Accept things like "A.", "Category A", "A - ..." etc.
    m = re.search(r"\b([ABCDE])\b", s)
    if m:
        return m.group(1)
    if s in _VALID_CATS:
        return s
    return None


def _norm_bool(v: Any) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"true", "yes", "1"}:
        return True
    if s in {"false", "no", "0"}:
        return False
    return None


def _norm_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------
def call_llm(
    user_query: str,
    *,
    token: str,
    timeout: int = 60,
    max_retries: int = 3,
    use_json_mode: bool = True,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """Call gpt-4o-mini via Venus proxy.

    Returns ``(parsed_json, raw_text, usage, error)``.
    """
    payload: Dict[str, Any] = {
        "model": MODEL_NAME,
        "messages": _render_messages(user_query),
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
            if rid is not None and obj.get("suit_ok"):
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
def classify_one(rec: Dict[str, Any], token: str) -> Dict[str, Any]:
    text = rec.get("first_user") or ""
    out = dict(rec)
    if not isinstance(text, str) or not text.strip():
        out.update(
            {
                "suit_category": None,
                "is_suitable_for_main_benchmark": None,
                "primary_task": "",
                "suit_reason": "",
                "suit_confidence": None,
                "suit_model": MODEL_NAME,
                "suit_ok": False,
                "suit_error": "empty first_user",
                "usage": None,
            }
        )
        return out

    parsed, raw, usage, err = call_llm(text, token=token)
    if parsed is None:
        out.update(
            {
                "suit_category": None,
                "is_suitable_for_main_benchmark": None,
                "primary_task": "",
                "suit_reason": "",
                "suit_confidence": None,
                "suit_model": MODEL_NAME,
                "suit_ok": False,
                "suit_error": err,
                "suit_raw": raw,
                "usage": usage,
            }
        )
        return out

    cat = _norm_category(parsed.get("category"))
    is_suitable = _norm_bool(parsed.get("is_suitable_for_main_benchmark"))
    if is_suitable is None and cat is not None:
        # Fall back to the schema-defined mapping: A/B are suitable.
        is_suitable = cat in {"A", "B"}

    out.update(
        {
            "suit_category": cat,
            "is_suitable_for_main_benchmark": is_suitable,
            "primary_task": str(parsed.get("primary_task") or "").strip(),
            "suit_reason": str(parsed.get("reason") or "").strip(),
            "suit_confidence": _norm_float(parsed.get("confidence")),
            "suit_model": MODEL_NAME,
            "suit_ok": cat is not None,
            "suit_error": None if cat is not None else "missing/invalid category",
            "usage": usage,
        }
    )
    if cat is None:
        out["suit_raw"] = raw
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(INPUT_PATH))
    ap.add_argument("--output", default=str(OUTPUT_PATH))
    ap.add_argument("--output-a", dest="output_a", default=str(OUTPUT_A_PATH),
                    help="separate jsonl file for records classified as category A")
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--limit", type=int, default=0,
                    help="only process the first N un-done records (0 = all)")
    ap.add_argument("--overwrite", action="store_true",
                    help="ignore existing output file and start fresh")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_a_path = Path(args.output_a)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_a_path.parent.mkdir(parents=True, exist_ok=True)

    if args.overwrite:
        if out_path.exists():
            out_path.unlink()
        if out_a_path.exists():
            out_a_path.unlink()

    token = _build_token()

    done = set() if args.overwrite else load_done_ids(out_path)
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
    fout_a = out_a_path.open("a", encoding="utf-8")

    stats = UsageStats(MODEL_NAME)
    n_ok = 0
    n_fail = 0
    cat_counts: Dict[str, int] = {c: 0 for c in _VALID_CATS}
    t0 = time.time()
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(classify_one, rec, token): rec for rec in pending}
            for i, fut in enumerate(as_completed(futs), 1):
                rec = futs[fut]
                try:
                    out = fut.result()
                except Exception as e:
                    out = dict(rec)
                    out.update(
                        {
                            "suit_category": None,
                            "is_suitable_for_main_benchmark": None,
                            "primary_task": "",
                            "suit_reason": "",
                            "suit_confidence": None,
                            "suit_model": MODEL_NAME,
                            "suit_ok": False,
                            "suit_error": f"worker exception: {e}",
                            "usage": None,
                        }
                    )
                stats.add(out.get("usage"))
                line = json.dumps(out, ensure_ascii=False) + "\n"
                is_cat_a = out.get("suit_ok") and out.get("suit_category") == "A"
                with write_lock:
                    fout.write(line)
                    fout.flush()
                    if is_cat_a:
                        fout_a.write(line)
                        fout_a.flush()
                if out.get("suit_ok"):
                    n_ok += 1
                    c = out.get("suit_category")
                    if c in cat_counts:
                        cat_counts[c] += 1
                else:
                    n_fail += 1
                if i % 50 == 0 or i == len(pending):
                    elapsed = time.time() - t0
                    rate = i / elapsed if elapsed > 0 else 0.0
                    cat_str = " ".join(
                        f"{c}={cat_counts[c]}" for c in sorted(cat_counts)
                    )
                    print(
                        f"[progress] {i}/{len(pending)} "
                        f"ok={n_ok} fail={n_fail} [{cat_str}] "
                        f"{rate:.1f} rec/s | {stats.format_line()}"
                    )
    finally:
        fout.close()
        fout_a.close()

    snap = stats.snapshot()
    price = _price_for(MODEL_NAME)
    print(f"[done] ok={n_ok} fail={n_fail} -> {out_path}")
    print(f"[done] category A -> {out_a_path} (count={cat_counts.get('A', 0)})")
    print(
        "[cats] "
        + " ".join(f"{c}={cat_counts[c]}" for c in sorted(cat_counts))
    )
    print(
        f"[usage] model={MODEL_NAME} "
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
