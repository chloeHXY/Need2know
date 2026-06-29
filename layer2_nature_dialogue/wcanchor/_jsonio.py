"""Tiny shared helpers for jsonl + robust JSON parsing of LLM outputs."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterable, Iterator, List, Optional


def write_jsonl(records: Iterable[Dict[str, Any]], path: str) -> int:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: str) -> Iterator[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def safe_json_loads(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse JSON that may be wrapped in markdown fences, prefixed by chatter,
    or have trailing commentary. Returns None on failure."""
    if not text:
        return None
    s = text.strip()
    # strip markdown fences
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = _JSON_OBJECT_RE.search(s)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def append_status(rec: Dict[str, Any], stage: str, status: str,
                  detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Add a per-stage status field without clobbering earlier fields."""
    rec = dict(rec)
    history = list(rec.get("_stage_history") or [])
    entry = {"stage": stage, "status": status}
    if detail:
        entry["detail"] = detail
    history.append(entry)
    rec["_stage_history"] = history
    return rec
