"""S1 -- structural filter (deterministic, no LLM calls).

Mirrors the paper's §4.1 funnel:
  * single-turn only
  * 25-2500 word user message
  * language in cfg.languages (default: English)
  * toxic == False
  * `redacted == True` rows can be dropped, kept inline, or routed to a
    separate "anchor pool" (great as natural PII anchors for the
    human-verified test set).

Inputs / outputs are JSONL records produced by S0 (load.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple


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
    """Return (kept_main, redacted_anchor_pool).

    ``redacted`` rows are routed according to cfg.redacted_route.
    """
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
