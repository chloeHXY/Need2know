"""S5 -- two-judge concordance.

Given ``rec["judge_a"]`` and ``rec["judge_b"]`` produced by S4 (run twice
with different clients), compute a span-level soft IoU and categorical
agreement on document-level fields.

The soft matcher mirrors Layer 1's matcher (token overlap + optional
embedding cosine fallback). We import directly from layer 1's judge module
so the two layers share identical comparison semantics.

The output ``rec["concord"]`` is::

    {
      "ne_iou":          0.86,
      "e_iou":           0.75,
      "helpful_iou":     0.50,
      "domain_match":    True,
      "task_match":      True,
      "subject_avg":     1.0,
      "consensus": {
        "primary_context": "<judge_a's primary, judge_b mostly agreed>",
        "domain": "Employment_And_Applications",
        "task": "Personal_Advice",
        "essential":     [...spans agreed-on...],
        "helpful":       [...],
        "non_essential": [...],
        "judge_a_only":  [...spans only in A...],
        "judge_b_only":  [...spans only in B...]
      },
      "status": "PASS" | "SOFT" | "HARD"
    }
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

# Reuse Layer 1's matcher primitives so semantics match exactly.
from synth.judge import (  # type: ignore
    MatcherConfig,
    _content_token_set,
    _cosine,
    _max_overlap,
)

from .annotate_ci import split_by_tier


# ---------------------------------------------------------------------------
# Soft set IoU
# ---------------------------------------------------------------------------

def _matches_with_emb(
    value: str,
    candidates: Sequence[str],
    cfg: MatcherConfig,
    embeddings: Optional[Mapping[str, List[float]]] = None,
) -> bool:
    overlap, _ = _max_overlap(value, list(candidates))
    if overlap >= cfg.token_threshold:
        return True
    if embeddings is None:
        return False
    v_emb = embeddings.get(value)
    if not v_emb:
        return False
    best = 0.0
    for c in candidates:
        c_emb = embeddings.get(c)
        if not c_emb:
            continue
        s = _cosine(v_emb, c_emb)
        if s > best:
            best = s
    return best >= cfg.cosine_threshold


def soft_iou(
    a: Sequence[str],
    b: Sequence[str],
    cfg: MatcherConfig,
    embeddings: Optional[Mapping[str, List[float]]] = None,
) -> Tuple[float, List[str], List[str]]:
    """Return (iou, only_a, only_b).

    Soft set similarity: each item in A is "matched" if SOME item in B
    passes the matcher (or vice versa). IoU is then computed on these
    matched/unmatched counts.

    Empty sets: if both empty -> 1.0; if exactly one empty -> 0.0.
    """
    if not a and not b:
        return 1.0, [], []
    if not a or not b:
        return 0.0, list(a), list(b)
    a_matched = [x for x in a if _matches_with_emb(x, b, cfg, embeddings)]
    b_matched = [x for x in b if _matches_with_emb(x, a, cfg, embeddings)]
    only_a = [x for x in a if x not in a_matched]
    only_b = [x for x in b if x not in b_matched]
    inter = len(a_matched) + len(b_matched)
    union = len(a) + len(b)
    iou = inter / max(1, union)
    return iou, only_a, only_b


# ---------------------------------------------------------------------------
# Concord driver
# ---------------------------------------------------------------------------

@dataclass
class ConcordConfig:
    pass_ne_iou: float = 0.6
    pass_e_iou: float = 0.6
    pass_require_domain_match: bool = True
    soft_ne_iou: float = 0.4
    soft_e_iou: float = 0.4
    matcher_token_threshold: float = 0.5
    matcher_cosine_threshold: float = 0.65


def _spans_text(spans: Sequence[Dict[str, Any]]) -> List[str]:
    return [str(s["span"]) for s in spans]


def _index_by_span(spans: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(s["span"]): s for s in spans}


def _agreed_subjects(
    a_spans: Sequence[Dict[str, Any]], b_spans: Sequence[Dict[str, Any]],
    cfg: MatcherConfig, embeddings: Optional[Mapping[str, List[float]]],
) -> float:
    """For spans that are matched between A and B, what fraction agree on
    subject? Returns 1.0 if no matches (degenerate)."""
    a_index = _index_by_span(a_spans)
    b_index = _index_by_span(b_spans)
    a_strs = list(a_index.keys())
    b_strs = list(b_index.keys())
    agree = 0
    total = 0
    for av in a_strs:
        # Find best b match.
        best_overlap, best_b = _max_overlap(av, b_strs)
        if best_overlap >= cfg.token_threshold and best_b:
            total += 1
            if a_index[av]["subject"] == b_index[best_b]["subject"]:
                agree += 1
    if total == 0:
        return 1.0
    return agree / total


def _build_consensus(
    judge_a: Dict[str, Any], judge_b: Dict[str, Any],
    cfg: MatcherConfig, embeddings: Optional[Mapping[str, List[float]]],
) -> Dict[str, Any]:
    """Build a consensus annotation: spans both judges agree on (by tier),
    plus the disjoint sets for inspection."""
    a_spans = list(judge_a.get("spans", []))
    b_spans = list(judge_b.get("spans", []))
    a_by_tier = split_by_tier(a_spans)
    b_by_tier = split_by_tier(b_spans)

    consensus = {"essential": [], "helpful": [], "non_essential": []}
    only_a: List[Dict[str, Any]] = []
    only_b: List[Dict[str, Any]] = []
    matched_a_ids: Set[int] = set()

    for tier in ("essential", "helpful", "non_essential"):
        b_strs = [str(s["span"]) for s in b_by_tier[tier]]
        for s in a_by_tier[tier]:
            if _matches_with_emb(str(s["span"]), b_strs, cfg, embeddings):
                consensus[tier].append(s)
                matched_a_ids.add(id(s))

    # Build only_a / only_b lists across all tiers (regardless of which tier
    # they fell into). A span only in A still has educational value.
    matched_b_ids: Set[int] = set()
    for tier in ("essential", "helpful", "non_essential"):
        a_strs = [str(s["span"]) for s in a_by_tier[tier]]
        for s in b_by_tier[tier]:
            if _matches_with_emb(str(s["span"]), a_strs, cfg, embeddings):
                matched_b_ids.add(id(s))
    only_a = [s for s in a_spans if id(s) not in matched_a_ids]
    only_b = [s for s in b_spans if id(s) not in matched_b_ids]

    return {
        "primary_context": judge_a.get("primary_context") or judge_b.get("primary_context"),
        "domain": judge_a.get("domain") or judge_b.get("domain"),
        "task": judge_a.get("task") or judge_b.get("task"),
        **consensus,
        "judge_a_only": only_a,
        "judge_b_only": only_b,
    }


def compute_concord(
    rec: Dict[str, Any],
    cfg: ConcordConfig,
    embeddings: Optional[Mapping[str, List[float]]] = None,
) -> Dict[str, Any]:
    judge_a = rec.get("judge_a") or {}
    judge_b = rec.get("judge_b") or {}
    a_by_tier = split_by_tier(judge_a.get("spans", []))
    b_by_tier = split_by_tier(judge_b.get("spans", []))
    matcher_cfg = MatcherConfig(
        token_threshold=cfg.matcher_token_threshold,
        cosine_threshold=cfg.matcher_cosine_threshold,
    )

    e_iou, _, _ = soft_iou(
        _spans_text(a_by_tier["essential"]),
        _spans_text(b_by_tier["essential"]),
        matcher_cfg, embeddings,
    )
    h_iou, _, _ = soft_iou(
        _spans_text(a_by_tier["helpful"]),
        _spans_text(b_by_tier["helpful"]),
        matcher_cfg, embeddings,
    )
    ne_iou, _, _ = soft_iou(
        _spans_text(a_by_tier["non_essential"]),
        _spans_text(b_by_tier["non_essential"]),
        matcher_cfg, embeddings,
    )
    domain_match = (judge_a.get("domain") == judge_b.get("domain"))
    task_match = (judge_a.get("task") == judge_b.get("task"))
    subj_avg = _agreed_subjects(judge_a.get("spans", []),
                                judge_b.get("spans", []),
                                matcher_cfg, embeddings)

    if (
        ne_iou >= cfg.pass_ne_iou
        and e_iou >= cfg.pass_e_iou
        and (not cfg.pass_require_domain_match or domain_match)
    ):
        status = "PASS"
    elif ne_iou >= cfg.soft_ne_iou and e_iou >= cfg.soft_e_iou:
        status = "SOFT"
    else:
        status = "HARD"

    consensus = _build_consensus(judge_a, judge_b, matcher_cfg, embeddings)
    return {
        "ne_iou": round(ne_iou, 4),
        "e_iou": round(e_iou, 4),
        "helpful_iou": round(h_iou, 4),
        "domain_match": domain_match,
        "task_match": task_match,
        "subject_avg": round(subj_avg, 4),
        "consensus": consensus,
        "status": status,
    }


def all_concord_strings(rec: Dict[str, Any]) -> List[str]:
    """Strings the concord checker may want vectors for."""
    out: List[str] = []
    for key in ("judge_a", "judge_b"):
        spans = (rec.get(key) or {}).get("spans") or []
        out.extend(str(s["span"]) for s in spans)
    seen, uniq = set(), []
    for s in out:
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq
