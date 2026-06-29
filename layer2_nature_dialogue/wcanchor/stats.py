"""S10 -- funnel + distribution report.

Walks the per-stage jsonl checkpoints and prints a Markdown report with:
  * funnel counts at each stage,
  * (domain, task) cross-tabulation,
  * span subject distribution,
  * necessity-tier distribution,
  * concord status distribution,
  * judge agreement histogram (ne_iou, e_iou).
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from ._jsonio import read_jsonl


def _safe_count(path: Optional[str]) -> int:
    if not path or not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)


def funnel(stage_paths: Dict[str, str]) -> List[Dict[str, Any]]:
    """stage_paths: {stage_name: jsonl_path}; insertion order is preserved
    (Python 3.7+) so iterate to get the funnel order."""
    rows = []
    last = None
    for name, path in stage_paths.items():
        n = _safe_count(path)
        retained = (None if last is None else (n / last if last else 0.0))
        rows.append({"stage": name, "n": n, "retained_from_prev": retained})
        last = n
    return rows


def _bucket(x: Optional[float], buckets=(0.0, 0.4, 0.6, 0.8, 1.0)) -> str:
    if x is None:
        return "n/a"
    for i, b in enumerate(buckets):
        if x < b:
            return f"<{b}"
    return f">={buckets[-1]}"


def annotate_distribution(unified_path: str) -> Dict[str, Any]:
    domain_task: Dict[str, Counter] = defaultdict(Counter)
    subj = Counter()
    necessity = Counter()
    concord_status = Counter()
    ne_iou_buckets = Counter()
    e_iou_buckets = Counter()
    helpful_iou_buckets = Counter()
    redacted_count = 0

    n = 0
    for rec in read_jsonl(unified_path):
        n += 1
        spec = rec.get("spec") or {}
        d = spec.get("domain") or "Other"
        t = spec.get("task") or "General_Chitchat"
        domain_task[d][t] += 1
        for key in ("essential_info", "helpful_info", "nonessential_sensitive_info"):
            for s in spec.get(key, []) or []:
                subj[s.get("source_subject", "unknown")] += 1
                necessity[s.get("necessity", "helpful")] += 1
        c = rec.get("consistency") or {}
        concord_status[c.get("status", "n/a")] += 1
        ne_iou_buckets[_bucket(c.get("ne_iou"))] += 1
        e_iou_buckets[_bucket(c.get("e_iou"))] += 1
        helpful_iou_buckets[_bucket(c.get("helpful_iou"))] += 1
        if (rec.get("source_meta") or {}).get("wc_redacted_flag"):
            redacted_count += 1

    return {
        "n": n,
        "redacted_count": redacted_count,
        "domain_task":   {k: dict(v) for k, v in domain_task.items()},
        "subject":       dict(subj),
        "necessity":     dict(necessity),
        "concord":       dict(concord_status),
        "ne_iou_hist":   dict(ne_iou_buckets),
        "e_iou_hist":    dict(e_iou_buckets),
        "helpful_iou_hist": dict(helpful_iou_buckets),
    }


def render_markdown(funnel_rows: List[Dict[str, Any]],
                    dist: Optional[Dict[str, Any]]) -> str:
    out: List[str] = []
    out.append("# Layer 2 (WildChat anchor) -- pipeline report\n")
    out.append("## Funnel\n")
    out.append("| stage | count | retained_from_prev |")
    out.append("|---|---:|---:|")
    for r in funnel_rows:
        keep = ("" if r["retained_from_prev"] is None
                else f'{r["retained_from_prev"]:.1%}')
        out.append(f'| {r["stage"]} | {r["n"]} | {keep} |')
    out.append("")

    if dist is None:
        return "\n".join(out)

    out.append(f"## Final unified set: n = {dist['n']} "
               f"(of which redacted-anchor: {dist['redacted_count']})\n")

    out.append("### Domain x Task")
    out.append("| domain | top tasks (count) |")
    out.append("|---|---|")
    for d, tasks in sorted(dist["domain_task"].items()):
        top = ", ".join(f"{t}={c}" for t, c in
                        sorted(tasks.items(), key=lambda kv: -kv[1])[:5])
        out.append(f"| {d} | {top} |")
    out.append("")

    out.append("### Span subject distribution")
    out.append("| subject | n |")
    out.append("|---|---:|")
    for k, v in sorted(dist["subject"].items(), key=lambda kv: -kv[1]):
        out.append(f"| {k} | {v} |")
    out.append("")

    out.append("### Necessity tier distribution")
    out.append("| necessity | n |")
    out.append("|---|---:|")
    for k, v in dist["necessity"].items():
        out.append(f"| {k} | {v} |")
    out.append("")

    out.append("### Concord status")
    out.append("| status | n |")
    out.append("|---|---:|")
    for k, v in dist["concord"].items():
        out.append(f"| {k} | {v} |")
    out.append("")

    out.append("### IoU histograms")
    for label, key in [("non-essential IoU", "ne_iou_hist"),
                       ("essential IoU",     "e_iou_hist"),
                       ("helpful IoU",       "helpful_iou_hist")]:
        out.append(f"\n**{label}**")
        out.append("| bucket | n |")
        out.append("|---|---:|")
        for k, v in dist[key].items():
            out.append(f"| {k} | {v} |")

    return "\n".join(out)
