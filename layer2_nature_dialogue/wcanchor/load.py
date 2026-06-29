"""S0 -- load WildChat parquet, normalize each row to a flat record.

Output record::

    {
      "id":               "wc-000123",
      "conversation_id":  "26c5dc...",
      "model":            "gpt-4",
      "timestamp":        "2023-04-10T00:01:08+00:00",
      "language":         "English",
      "turn":             1,
      "redacted":         False,
      "toxic":            False,
      "first_user":       "<full text of first user message>",
      "user_words":       42
    }

We deliberately throw away the full multi-turn conversation here -- the rest
of the pipeline is single-turn-only (cf. paper §4.1).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Union

import pandas as pd


def _first_user_message(conversation: Any) -> str:
    """Walk a WildChat conversation array (list of dicts) and return the
    first user message's content."""
    if conversation is None:
        return ""
    try:
        for m in conversation:
            if isinstance(m, dict) and m.get("role") == "user":
                return str(m.get("content") or "")
    except TypeError:
        return ""
    return ""


def load_parquet(path: Union[str, Sequence[str]]) -> pd.DataFrame:
    """Load one parquet file or concatenate several.

    ``path`` may be a single string path, or a list/tuple of paths.
    """
    if isinstance(path, (list, tuple)):
        paths = list(path)
    else:
        paths = [path]
    if not paths:
        raise ValueError("load_parquet: empty path list")
    needed = {"conversation_id", "conversation", "turn", "language",
              "toxic", "redacted", "model", "timestamp"}
    frames: List[pd.DataFrame] = []
    for p in paths:
        df = pd.read_parquet(p)
        missing = needed - set(df.columns)
        if missing:
            raise ValueError(
                f"parquet {p} is missing required columns: {missing}")
        frames.append(df)
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames, ignore_index=True)


def normalize(df: pd.DataFrame, *, id_offset: int = 0) -> List[Dict[str, Any]]:
    """Materialize a flat list of record dicts ready for the rest of the
    pipeline. We compute first_user_text and user_words once here.

    ``id_offset`` lets callers keep ``id`` globally unique when several
    parquet shards are normalized separately.
    """
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(df.itertuples(index=False), start=id_offset):
        ts = getattr(row, "timestamp", None)
        if ts is not None:
            try:
                ts = ts.isoformat()
            except AttributeError:
                ts = str(ts)
        first_user = _first_user_message(getattr(row, "conversation", None))
        out.append({
            "id":              f"wc-{i:06d}",
            "conversation_id": getattr(row, "conversation_id", ""),
            "model":           getattr(row, "model", ""),
            "timestamp":       ts,
            "language":        getattr(row, "language", ""),
            "turn":            int(getattr(row, "turn", 0)),
            "redacted":        bool(getattr(row, "redacted", False)),
            "toxic":           bool(getattr(row, "toxic", False)),
            "first_user":      first_user,
            "user_words":      len(first_user.split()),
        })
    return out


def write_jsonl(records: List[Dict[str, Any]], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> Iterator[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def run(parquet_path: Union[str, Sequence[str]], out_jsonl: str) -> int:
    """Load one or more parquet files, normalize, write a single JSONL.

    ``parquet_path`` accepts either a single path or a list of paths.
    Records keep a globally-unique ``id`` across shards.
    """
    df = load_parquet(parquet_path)
    records = normalize(df)
    write_jsonl(records, out_jsonl)
    return len(records)
