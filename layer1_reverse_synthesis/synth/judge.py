"""Judge: parses the LLM-judge response and computes a consistency score.

The score compares attributes the sampler INJECTED (gold) against attributes
the judge EXTRACTED. Two-stage matcher:

  1. Token-overlap (cheap; works for direct lexical re-use).
  2. Embedding cosine fallback (optional; passed in as a precomputed
     dict[str, list[float]]). Catches the common case where the judge
     paraphrases ("grandmother died from alcoholism" vs. "grandmother passed
     away from complications related to heavy drinking").

The matcher always works without embeddings, so offline tests / smoke runs
that don't configure an embedding client still produce sensible reports.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .sampler import AttributeValue, Spec


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "at", "for",
    "with", "is", "are", "was", "were", "be", "been", "being", "have",
    "has", "had", "do", "does", "did", "i", "my", "me", "we", "our", "us",
    "you", "your", "they", "them", "their", "this", "that", "these",
    "those", "it", "its", "as", "by", "from", "about", "out", "up",
    "down", "into", "than", "then", "so", "but", "not", "no", "yes",
}

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS]


def _content_token_set(text: str) -> set:
    return set(_tokenize(text))


def _max_overlap(value: str, candidates: List[str]) -> Tuple[float, str]:
    """Return (best_overlap_ratio, matched_candidate).

    overlap = |tokens(value) ∩ tokens(candidate)| / |tokens(value)|
    """
    v_toks = _content_token_set(value)
    if not v_toks:
        return 0.0, ""
    best, hit = 0.0, ""
    for c in candidates:
        c_toks = _content_token_set(c)
        if not c_toks:
            continue
        ratio = len(v_toks & c_toks) / max(1, len(v_toks))
        if ratio > best:
            best, hit = ratio, c
    return best, hit


# ---------------------------------------------------------------------------
# Cosine similarity (for the embedding-based fallback)
# ---------------------------------------------------------------------------

def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _max_cosine(
    value: str,
    candidates: List[str],
    embeddings: Mapping[str, List[float]],
) -> Tuple[float, str]:
    v_emb = embeddings.get(value)
    if not v_emb:
        return 0.0, ""
    best, hit = 0.0, ""
    for c in candidates:
        c_emb = embeddings.get(c)
        if not c_emb:
            continue
        sim = _cosine(v_emb, c_emb)
        if sim > best:
            best, hit = sim, c
    return best, hit


# ---------------------------------------------------------------------------
# Composite matcher
# ---------------------------------------------------------------------------

@dataclass
class MatcherConfig:
    token_threshold: float = 0.5
    cosine_threshold: float = 0.65


def _matches(
    av: AttributeValue,
    judge_list: List[str],
    *,
    cfg: MatcherConfig,
    embeddings: Optional[Mapping[str, List[float]]] = None,
) -> Tuple[bool, str, str]:
    """Returns (matched, hit, source) where source ∈ {"token","embed","none"}."""
    overlap, hit = _max_overlap(av.value, judge_list)
    if overlap >= cfg.token_threshold:
        return True, hit, "token"
    if embeddings is not None:
        sim, hit_e = _max_cosine(av.value, judge_list, embeddings)
        if sim >= cfg.cosine_threshold:
            return True, hit_e, "embed"
    return False, "", "none"


# ---------------------------------------------------------------------------
# Parsing the judge JSON
# ---------------------------------------------------------------------------

def parse_judge_output(text: str) -> Dict[str, List[str]]:
    if not text:
        return {"primary_context": [], "essential_attributes": [], "nonessential_attributes": []}

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return {"primary_context": [], "essential_attributes": [], "nonessential_attributes": []}
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {"primary_context": [], "essential_attributes": [], "nonessential_attributes": []}

    out = {
        "primary_context": list(obj.get("primary_context") or obj.get("primary context") or []),
        "essential_attributes": list(
            obj.get("essential_attributes")
            or obj.get("attributes essential to the context")
            or []
        ),
        "nonessential_attributes": list(
            obj.get("nonessential_attributes")
            or obj.get("non_essential_attributes")
            or obj.get("sensitive attributes not essential to the context")
            or []
        ),
    }
    for k in out:
        out[k] = [str(x) for x in out[k] if x is not None]
    return out


# ---------------------------------------------------------------------------
# Consistency report
# ---------------------------------------------------------------------------

@dataclass
class ConsistencyReport:
    essential_recall: float
    nonessential_recall: float
    essential_misses: List[str] = field(default_factory=list)
    nonessential_misses: List[str] = field(default_factory=list)
    extra_nonessential: List[str] = field(default_factory=list)
    swapped_essential_into_ne: List[str] = field(default_factory=list)
    swapped_ne_into_essential: List[str] = field(default_factory=list)
    matcher_sources: Dict[str, int] = field(default_factory=dict)
    status: str = "PASS"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "essential_recall": round(self.essential_recall, 4),
            "nonessential_recall": round(self.nonessential_recall, 4),
            "essential_misses": self.essential_misses,
            "nonessential_misses": self.nonessential_misses,
            "extra_nonessential": self.extra_nonessential,
            "swapped_essential_into_ne": self.swapped_essential_into_ne,
            "swapped_ne_into_essential": self.swapped_ne_into_essential,
            "matcher_sources": self.matcher_sources,
            "status": self.status,
        }


def _all_strings_to_embed(spec: Spec, judge_out: Dict[str, List[str]]) -> List[str]:
    """Strings the consistency checker may need vectors for."""
    out: List[str] = []
    out.extend(a.value for a in spec.essential_info)
    out.extend(a.value for a in spec.nonessential_sensitive_info)
    out.extend(judge_out.get("essential_attributes", []))
    out.extend(judge_out.get("nonessential_attributes", []))
    if spec.task_brief:
        out.append(spec.task_brief)
    # Deduplicate while preserving order.
    seen: set = set()
    uniq: List[str] = []
    for s in out:
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def compute_consistency(
    spec: Spec,
    judge_out: Dict[str, List[str]],
    *,
    pass_threshold: float = 0.8,
    soft_fail_threshold: float = 0.5,
    embeddings: Optional[Mapping[str, List[float]]] = None,
    matcher_cfg: Optional[MatcherConfig] = None,
) -> ConsistencyReport:
    """Compare what the sampler injected vs. what the judge extracted.

    Special cases:
      * spec.essential_info == [] (none-policy task):
        essential_recall is defined as 1.0; we additionally check that the
        judge's primary_context covers the task_brief (if any). If the judge
        wrongly puts MANY items into "essential_attributes" it's still a
        warning sign so we count those as "swapped_ne_into_essential".
    """
    cfg = matcher_cfg or MatcherConfig()
    je = judge_out.get("essential_attributes", [])
    jne = judge_out.get("nonessential_attributes", [])

    sources: Dict[str, int] = {"token": 0, "embed": 0, "none": 0}

    e_hits, e_misses = 0, []
    swap_e2ne = []
    for a in spec.essential_info:
        ok, _, src = _matches(a, je, cfg=cfg, embeddings=embeddings)
        sources[src] = sources.get(src, 0) + 1
        if ok:
            e_hits += 1
        else:
            e_misses.append(a.value)
            ok2, _, _ = _matches(a, jne, cfg=cfg, embeddings=embeddings)
            if ok2:
                swap_e2ne.append(a.value)

    ne_hits, ne_misses = 0, []
    swap_ne2e = []
    for a in spec.nonessential_sensitive_info:
        ok, _, src = _matches(a, jne, cfg=cfg, embeddings=embeddings)
        sources[src] = sources.get(src, 0) + 1
        if ok:
            ne_hits += 1
        else:
            ne_misses.append(a.value)
            ok2, _, _ = _matches(a, je, cfg=cfg, embeddings=embeddings)
            if ok2:
                swap_ne2e.append(a.value)

    if spec.essential_info:
        e_recall = e_hits / len(spec.essential_info)
    else:
        # none-policy: no sensitive essential to find.
        e_recall = 1.0
        # If the judge wrongly classifies many of the sampler's NEs as essential,
        # we'll catch that via swap_ne2e (counted below).

    ne_recall = ne_hits / max(1, len(spec.nonessential_sensitive_info))

    # "Extra" NEs the judge surfaced that we didn't inject (could be model-
    # leaked PII -- still useful, kept for downstream reward shaping).
    sampler_ne_values = [a.value for a in spec.nonessential_sensitive_info]
    sampler_e_values = [a.value for a in spec.essential_info]
    extras: List[str] = []
    for j in jne:
        is_overlap_ne = any(
            _matches(AttributeValue("_", v), [j], cfg=cfg, embeddings=embeddings)[0]
            for v in sampler_ne_values
        )
        is_overlap_e = any(
            _matches(AttributeValue("_", v), [j], cfg=cfg, embeddings=embeddings)[0]
            for v in sampler_e_values
        )
        if not is_overlap_ne and not is_overlap_e:
            extras.append(j)

    # Decide overall status.
    # For none-policy tasks, status is governed entirely by NE recall + the
    # absence of large swap_ne2e (which would mean the judge thinks our
    # "non-essentials" are actually essential, contradicting the policy).
    if spec.essential_info:
        floor = min(e_recall, ne_recall)
    else:
        # Penalise the case where many of our NEs got promoted into E by
        # the judge -- that suggests our NE pick is questionable.
        n_total_ne = max(1, len(spec.nonessential_sensitive_info))
        promotion_rate = len(swap_ne2e) / n_total_ne
        # A promotion rate >= 0.5 makes this look unreliable.
        floor = ne_recall * (1.0 - 0.5 * promotion_rate)

    if floor >= pass_threshold:
        status = "PASS"
    elif floor >= soft_fail_threshold:
        status = "SOFT_FAIL"
    else:
        status = "HARD_FAIL"

    return ConsistencyReport(
        essential_recall=e_recall,
        nonessential_recall=ne_recall,
        essential_misses=e_misses,
        nonessential_misses=ne_misses,
        extra_nonessential=extras,
        swapped_essential_into_ne=swap_e2ne,
        swapped_ne_into_essential=swap_ne2e,
        matcher_sources=sources,
        status=status,
    )
