"""S7 -- gold reformulation using the consensus E / helpful / NE lists.

Runs ``build_reformulator_messages`` against each post-concord record and
attaches ``rec["gold_reformulation"]``. Records whose concord status is
HARD are skipped (they don't have reliable labels to reformulate against).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from . import LLMClient
from .prompts import build_reformulator_messages


@dataclass
class ReformulateConfig:
    concurrency: int = 16
    skip_hard: bool = True


def _spans_to_texts(spans: List[Dict[str, Any]]) -> List[str]:
    return [str(s["span"]) for s in spans]


async def _reformulate_one(
    client: LLMClient, rec: Dict[str, Any],
) -> Dict[str, Any]:
    consensus = (rec.get("concord") or {}).get("consensus") or {}
    primary = consensus.get("primary_context") or ""
    e = _spans_to_texts(consensus.get("essential", []))
    h = _spans_to_texts(consensus.get("helpful", []))
    ne = _spans_to_texts(consensus.get("non_essential", []))
    messages = build_reformulator_messages(
        rec["first_user"],
        primary_context=primary,
        essential_spans=e,
        helpful_spans=h,
        non_essential_spans=ne,
    )
    try:
        out = await client.chat(messages, temperature=0.3)
        text = out["text"].strip().strip('"').strip()
        rec = dict(rec)
        rec["gold_reformulation"] = text
        rec["gold_reformulation_endpoint"] = out["endpoint"]
    except Exception as e:  # noqa: BLE001
        rec = dict(rec)
        rec["gold_reformulation"] = None
        rec["gold_reformulation_error"] = repr(e)[:200]
    return rec


async def reformulate(
    client: LLMClient,
    records: Iterable[Dict[str, Any]],
    cfg: ReformulateConfig,
) -> List[Dict[str, Any]]:
    sem = asyncio.Semaphore(cfg.concurrency)

    async def _bound(rec: Dict[str, Any]) -> Dict[str, Any]:
        async with sem:
            status = (rec.get("concord") or {}).get("status")
            if cfg.skip_hard and status == "HARD":
                rec = dict(rec)
                rec["gold_reformulation"] = None
                return rec
            return await _reformulate_one(client, rec)

    tasks = [asyncio.create_task(_bound(r)) for r in records]
    return [await t for t in tasks]
