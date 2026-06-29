"""S2+S3 -- combined screening (content_type tagging + binary CI-concern flag).

Cheap LLM call. We combine the two sub-stages into one prompt to avoid
paying twice for what's essentially the same read of the same prompt.

Output record (added to each kept record from S1)::

    {
      ... S0/S1 fields ...
      "screen": {
        "content_type": "first_person_task",
        "content_type_confidence": 0.93,
        "has_ci_concern": true,
        "rationale": "...",
        "endpoint": "gpt4o-mini-screen"
      }
    }

Records that fail content-type or CI-concern gates are still kept in the
``screen.jsonl`` checkpoint but tagged with ``screen.passed = false`` so you
can inspect rejection rates downstream.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import LLMClient
from ._jsonio import safe_json_loads
from .prompts import (
    CONTENT_TYPES,
    SCREEN_RESPONSE_FORMAT,
    build_screen_messages,
)


@dataclass
class ScreenConfig:
    keep_content_types: Tuple[str, ...] = (
        "first_person_task", "third_party_about", "mixed",
    )
    require_ci_concern: bool = True
    use_json_mode: bool = True
    concurrency: int = 16


def _coerce(obj: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not obj:
        return {
            "content_type": "unknown",
            "content_type_confidence": 0.0,
            "has_ci_concern": False,
            "rationale": "parse_error",
        }
    ct = str(obj.get("content_type", "")).strip()
    if ct not in CONTENT_TYPES:
        ct = "unknown"
    try:
        conf = float(obj.get("content_type_confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    has = obj.get("has_ci_concern")
    if isinstance(has, str):
        has = has.lower() in ("true", "yes", "1")
    has = bool(has)
    rat = str(obj.get("rationale", ""))[:300]
    return {
        "content_type": ct,
        "content_type_confidence": max(0.0, min(1.0, conf)),
        "has_ci_concern": has,
        "rationale": rat,
    }


async def _screen_one(
    client: LLMClient, rec: Dict[str, Any], cfg: ScreenConfig,
) -> Dict[str, Any]:
    messages = build_screen_messages(rec["first_user"])
    try:
        out = await client.chat(
            messages,
            response_format=SCREEN_RESPONSE_FORMAT if cfg.use_json_mode else None,
        )
        parsed = _coerce(safe_json_loads(out["text"]))
        parsed["endpoint"] = out["endpoint"]
    except Exception as e:  # noqa: BLE001
        parsed = _coerce(None)
        parsed["error"] = repr(e)[:200]
    rec = dict(rec)
    rec["screen"] = parsed
    rec["screen"]["passed"] = (
        parsed["content_type"] in cfg.keep_content_types
        and (not cfg.require_ci_concern or parsed["has_ci_concern"])
    )
    return rec


async def screen_records(
    client: LLMClient,
    records: Iterable[Dict[str, Any]],
    cfg: ScreenConfig,
    *,
    show_progress: bool = True,
) -> List[Dict[str, Any]]:
    sem = asyncio.Semaphore(cfg.concurrency)
    records = list(records)

    async def _bound(idx: int, rec: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        async with sem:
            res = await _screen_one(client, rec, cfg)
        return idx, res

    tasks = [asyncio.create_task(_bound(i, r)) for i, r in enumerate(records)]
    results: List[Optional[Dict[str, Any]]] = [None] * len(tasks)

    if show_progress and tasks:
        try:
            from tqdm.asyncio import tqdm as _atqdm
            iterator = _atqdm.as_completed(
                tasks, total=len(tasks), desc="S2+S3 screen", unit="req",
            )
        except Exception:  # noqa: BLE001
            iterator = asyncio.as_completed(tasks)
    else:
        iterator = asyncio.as_completed(tasks)

    for coro in iterator:
        idx, res = await coro
        results[idx] = res
    return [r for r in results if r is not None]
