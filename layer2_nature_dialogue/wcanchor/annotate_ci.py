"""S4 -- full CI annotation (single judge).

Adds a ``judge_a`` (or ``judge_b``, depending on which client you pass) field
to each record::

    rec["judge_a"] = {
      "primary_context": "...",
      "domain": "Employment_And_Applications",
      "task": "Personal_Advice",
      "spans": [
        {"span": "...", "subject": "third_party",
         "sensitivity_type": "name", "necessity": "non_essential",
         "recommended_action": "remove", "rationale": "..."},
        ...
      ],
      "endpoint": "judge-a-gpt4o",
      "raw_text": "<the model's raw output, kept for debugging>"
    }

This module is shared by S4 (judge_a) and S5 (judge_b) -- only the LLMClient
and the field key change.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from . import LLMClient
from ._jsonio import safe_json_loads
from .prompts import (
    CI_RESPONSE_FORMAT,
    DOMAINS,
    NECESSITY_TIERS,
    RECOMMENDED_ACTIONS,
    SENSITIVITY_TYPES,
    SPAN_SUBJECTS,
    TASKS,
    build_ci_annotation_messages,
)


# ---------------------------------------------------------------------------
# Output coercion
# ---------------------------------------------------------------------------

def _coerce_span(s: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(s, dict):
        return None
    span = str(s.get("span") or "").strip()
    if not span:
        return None
    subj = str(s.get("subject") or "unknown")
    if subj not in SPAN_SUBJECTS:
        subj = "unknown"
    stype = str(s.get("sensitivity_type") or "other")
    if stype not in SENSITIVITY_TYPES:
        stype = "other"
    necessity = str(s.get("necessity") or "helpful")
    if necessity not in NECESSITY_TIERS:
        necessity = "helpful"
    action = str(s.get("recommended_action") or "")
    if action not in RECOMMENDED_ACTIONS:
        action = {
            "essential": "keep",
            "helpful": "generalize",
            "non_essential": "remove",
        }[necessity]
    rationale = str(s.get("rationale") or "")[:300]
    return {
        "span": span,
        "subject": subj,
        "sensitivity_type": stype,
        "necessity": necessity,
        "recommended_action": action,
        "rationale": rationale,
    }


def coerce_ci_output(obj: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not obj:
        return {
            "primary_context": "",
            "domain": "Other",
            "task": "General_Chitchat",
            "spans": [],
            "_parse_error": True,
        }
    primary = str(obj.get("primary_context") or "").strip()
    domain = str(obj.get("domain") or "Other")
    if domain not in DOMAINS:
        domain = "Other"
    task = str(obj.get("task") or "General_Chitchat")
    if task not in TASKS:
        task = "General_Chitchat"
    spans: List[Dict[str, Any]] = []
    for s in obj.get("spans", []) or []:
        c = _coerce_span(s)
        if c is not None:
            spans.append(c)
    return {
        "primary_context": primary,
        "domain": domain,
        "task": task,
        "spans": spans,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

@dataclass
class AnnotateConfig:
    use_json_mode: bool = True
    concurrency: int = 16
    field_name: str = "judge_a"   # "judge_a" or "judge_b"


async def _annotate_one(
    client: LLMClient, rec: Dict[str, Any], cfg: AnnotateConfig,
) -> Dict[str, Any]:
    messages = build_ci_annotation_messages(rec["first_user"])
    try:
        out = await client.chat(
            messages,
            response_format=CI_RESPONSE_FORMAT if cfg.use_json_mode else None,
        )
        parsed = coerce_ci_output(safe_json_loads(out["text"]))
        parsed["endpoint"] = out["endpoint"]
        parsed["raw_text"] = out["text"]
    except Exception as e:  # noqa: BLE001
        parsed = coerce_ci_output(None)
        parsed["error"] = repr(e)[:200]
    rec = dict(rec)
    rec[cfg.field_name] = parsed
    return rec


async def annotate(
    client: LLMClient,
    records: Iterable[Dict[str, Any]],
    cfg: AnnotateConfig,
) -> List[Dict[str, Any]]:
    sem = asyncio.Semaphore(cfg.concurrency)

    async def _bound(rec: Dict[str, Any]) -> Dict[str, Any]:
        async with sem:
            return await _annotate_one(client, rec, cfg)

    tasks = [asyncio.create_task(_bound(r)) for r in records]
    return [await t for t in tasks]


# ---------------------------------------------------------------------------
# Convenience: split spans into the three tiers
# ---------------------------------------------------------------------------

def split_by_tier(spans: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out = {"essential": [], "helpful": [], "non_essential": []}
    for s in spans:
        out.get(s.get("necessity"), out["helpful"]).append(s)
    return out
