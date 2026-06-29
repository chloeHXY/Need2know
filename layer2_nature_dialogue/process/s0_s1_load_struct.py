"""S0 + S1 — WildChat parquet loading & structural filtering.

This module is a self-contained extraction of:

* ``wcanchor/load.py``         (S0: parquet -> flat JSONL records)
* ``wcanchor/filter_struct.py`` (S1: deterministic structural filter)

It exists so that the cheap, no-LLM stages of the Layer-2 pipeline
(``S0 load`` and ``S1 filter_struct``) can be run independently of the
``wcanchor`` package -- e.g. on a worker node that only needs to produce
``00_loaded.jsonl`` / ``01_struct.jsonl`` / ``01_struct_anchor.jsonl``.

S0 — load
=========

Reads one or several WildChat parquet shards. For each row we keep only
the *first* ``role == "user"`` message (this pipeline is single-turn only,
cf. paper §4.1) and emit a flat record::

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

S1 — filter_struct
==================

Pure-Python filter with no LLM calls. Mirrors the §4.1 funnel:

* ``single_turn_only`` (default on): drop ``turn != 1``
* ``language in cfg.languages`` (default: ``("English",)``)
* ``drop_toxic`` (default on): drop ``toxic == True``
* word count in ``[word_min, word_max]`` (default 25..2500)
* ``first_user`` must be non-empty

``redacted == True`` rows have three routing strategies:

* ``drop``         — discard;
* ``anchor_pool``  — route to a separate JSONL ("natural PII anchors"); **default**;
* ``keep_inline``  — keep them in the main pool.

CLI
===

    python s0_s1_load_struct.py \
        --parquet train-00000-of-00006.parquet train-00001-of-00006.parquet \
        --out-dir ./stages_full \
        --word-min 25 --word-max 420 \
        --redacted-route anchor_pool

Outputs::

    <out_dir>/00_loaded.jsonl
    <out_dir>/01_struct.jsonl
    <out_dir>/01_struct_anchor.jsonl       # only if redacted_route == "anchor_pool"

python layer2_nature_dialogue/process/s0_s1_load_struct.py \
    --parquet layer2_nature_dialogue/train-00002-of-00006.parquet \
              layer2_nature_dialogue/train-00003-of-00006.parquet \
              layer2_nature_dialogue/train-00004-of-00006.parquet \
              layer2_nature_dialogue/train-00005-of-00006.parquet \
    --out-dir layer2_nature_dialogue/process/stages_full \
    --word-min 25 --word-max 250 \
    --redacted-route anchor_pool

也可以：
# 默认：分流到锚点池
python s0_s1_load_struct.py --parquet a.parquet --out-dir ./stages_full
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Sequence, Tuple, Union

import pandas as pd


# ---------------------------------------------------------------------------
# Small JSONL helpers (kept local so this file has no intra-package deps)
# ---------------------------------------------------------------------------

def write_jsonl(records: Iterable[Dict[str, Any]], path: str) -> int:
    """Write an iterable of dicts to ``path`` as JSONL. Returns count."""
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


# ---------------------------------------------------------------------------
# S0 — load
# ---------------------------------------------------------------------------

_REQUIRED_PARQUET_COLUMNS = {
    "conversation_id", "conversation", "turn", "language",
    "toxic", "redacted", "model", "timestamp",
}


def _first_user_message(conversation: Any) -> str:
    """Return the first ``role == "user"`` content from a WildChat
    conversation array (a list of dicts). Empty string on any failure."""
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

    ``path`` may be a single string path, or a list/tuple of paths. All
    shards must contain the WildChat-style columns listed in
    ``_REQUIRED_PARQUET_COLUMNS``.
    """
    if isinstance(path, (list, tuple)):
        paths = list(path)
    else:
        paths = [path]
    if not paths:
        raise ValueError("load_parquet: empty path list")

    frames: List[pd.DataFrame] = []
    for p in paths:
        df = pd.read_parquet(p)
        missing = _REQUIRED_PARQUET_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"parquet {p} is missing required columns: {missing}")
        frames.append(df)
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames, ignore_index=True)


def normalize(df: pd.DataFrame, *, id_offset: int = 0) -> List[Dict[str, Any]]:
    """Materialize a flat list of record dicts ready for S1.

    ``id_offset`` lets callers keep ``id`` globally unique when multiple
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


def run_s0_load(
    parquet_path: Union[str, Sequence[str]],
    out_jsonl: str,
) -> int:
    """Load one or more parquet files, normalize, write a single JSONL.

    Returns the number of records written.
    """
    df = load_parquet(parquet_path)
    records = normalize(df)
    return write_jsonl(records, out_jsonl)


# ---------------------------------------------------------------------------
# S1 — filter_struct
# ---------------------------------------------------------------------------

# valid values for StructFilterConfig.redacted_route
REDACTED_ROUTES: Tuple[str, ...] = ("drop", "anchor_pool", "keep_inline")


@dataclass
class StructFilterConfig:
    word_min: int = 25
    word_max: int = 2500
    single_turn_only: bool = True
    drop_toxic: bool = True
    languages: Tuple[str, ...] = ("English",)
    redacted_route: str = "anchor_pool"   # drop | anchor_pool | keep_inline


def _passes(rec: Dict[str, Any], cfg: StructFilterConfig) -> bool:
    if cfg.single_turn_only and rec.get("turn", 0) != 1:
        return False
    if rec.get("language") not in cfg.languages:
        return False
    if cfg.drop_toxic and rec.get("toxic"):
        return False
    n = rec.get("user_words", 0)
    if not (cfg.word_min <= n <= cfg.word_max):
        return False
    if not (rec.get("first_user") or "").strip():
        return False
    return True


def filter_records(
    records: Iterable[Dict[str, Any]],
    cfg: StructFilterConfig,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return ``(kept_main, redacted_anchor_pool)``.

    ``redacted`` rows are routed according to ``cfg.redacted_route``:

    * ``drop``         — neither list keeps them
    * ``anchor_pool``  — appended to the second list, NOT to the main pool
    * ``keep_inline``  — appended to the main pool just like any other row
    """
    if cfg.redacted_route not in REDACTED_ROUTES:
        raise ValueError(
            f"redacted_route must be one of {REDACTED_ROUTES}, "
            f"got {cfg.redacted_route!r}")

    kept: List[Dict[str, Any]] = []
    anchors: List[Dict[str, Any]] = []
    for r in records:
        if not _passes(r, cfg):
            continue
        is_redacted = bool(r.get("redacted", False))
        if is_redacted and cfg.redacted_route == "drop":
            continue
        if is_redacted and cfg.redacted_route == "anchor_pool":
            anchors.append(r)
            continue
        # keep_inline OR not redacted -> main pool
        kept.append(r)
    return kept, anchors


def run_s1_struct(
    in_jsonl: str,
    out_jsonl: str,
    cfg: StructFilterConfig,
    *,
    anchor_jsonl: str = "",
) -> Tuple[int, int]:
    """Run S1 over an existing S0 checkpoint.

    Writes the main pool to ``out_jsonl``. If ``cfg.redacted_route == "anchor_pool"``
    and ``anchor_jsonl`` is non-empty, the redacted anchor pool is also
    written to ``anchor_jsonl``.

    Returns ``(n_main, n_anchor)``.
    """
    records = read_jsonl(in_jsonl)
    kept, anchors = filter_records(records, cfg)
    n_main = write_jsonl(kept, out_jsonl)
    n_anchor = 0
    if cfg.redacted_route == "anchor_pool" and anchor_jsonl:
        n_anchor = write_jsonl(anchors, anchor_jsonl)
    return n_main, n_anchor


# ---------------------------------------------------------------------------
# Combined runner + CLI
# ---------------------------------------------------------------------------

def run_s0_s1(
    parquet_paths: Union[str, Sequence[str]],
    out_dir: str,
    cfg: StructFilterConfig,
) -> Dict[str, Any]:
    """Convenience: run S0 then S1 and write three checkpoints into ``out_dir``.

    Files written:
        <out_dir>/00_loaded.jsonl
        <out_dir>/01_struct.jsonl
        <out_dir>/01_struct_anchor.jsonl   (only if cfg.redacted_route == "anchor_pool")
    """
    os.makedirs(out_dir, exist_ok=True)

    loaded_path = os.path.join(out_dir, "00_loaded.jsonl")
    struct_path = os.path.join(out_dir, "01_struct.jsonl")
    anchor_path = os.path.join(out_dir, "01_struct_anchor.jsonl")

    n_loaded = run_s0_load(parquet_paths, loaded_path)
    n_main, n_anchor = run_s1_struct(
        loaded_path, struct_path, cfg,
        anchor_jsonl=anchor_path if cfg.redacted_route == "anchor_pool" else "",
    )

    return {
        "loaded":         loaded_path,
        "struct":         struct_path,
        "struct_anchor":  anchor_path if cfg.redacted_route == "anchor_pool" else None,
        "n_loaded":       n_loaded,
        "n_struct":       n_main,
        "n_struct_anchor": n_anchor,
    }


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run S0 (load WildChat parquet) + S1 (structural filter).",
    )
    p.add_argument(
        "--parquet", nargs="+", required=True,
        help="One or more WildChat parquet shards.",
    )
    p.add_argument(
        "--out-dir", required=True,
        help="Directory for 00_loaded.jsonl / 01_struct.jsonl checkpoints.",
    )
    p.add_argument("--word-min", type=int, default=25)
    p.add_argument("--word-max", type=int, default=250)
    p.add_argument(
        "--languages", nargs="+", default=["English"],
        help="Allowed languages (default: English only).",
    )
    p.add_argument(
        "--no-single-turn-only", action="store_true",
        help="Disable single-turn filtering (default keeps only turn==1).",
    )
    p.add_argument(
        "--keep-toxic", action="store_true",
        help="Keep toxic=True rows (default drops them).",
    )
    p.add_argument(
        "--redacted-route", choices=list(REDACTED_ROUTES),
        default="anchor_pool",
        help="How to handle redacted=True rows (default: anchor_pool).",
    )
    return p


def main(argv: Sequence[str] = None) -> None:
    args = _build_argparser().parse_args(argv)

    cfg = StructFilterConfig(
        word_min=args.word_min,
        word_max=args.word_max,
        single_turn_only=not args.no_single_turn_only,
        drop_toxic=not args.keep_toxic,
        languages=tuple(args.languages),
        redacted_route=args.redacted_route,
    )

    info = run_s0_s1(args.parquet, args.out_dir, cfg)
    print(f"[S0] loaded {info['n_loaded']} rows -> {info['loaded']}")
    print(f"[S1] kept   {info['n_struct']} rows -> {info['struct']}")
    if info["struct_anchor"]:
        print(f"[S1] anchor {info['n_struct_anchor']} rows -> {info['struct_anchor']}")


if __name__ == "__main__":
    main()
