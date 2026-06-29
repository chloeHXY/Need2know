"""S6 -- unify the post-concord record into Layer-1-compatible JSONL.

Layer 1 schema lives in ../README.md §3. The unified record reuses
``spec.essential_info`` and ``spec.nonessential_sensitive_info`` (so SFT/RL
code expecting Layer 1 structure works unchanged) and adds three Layer 2
extensions:

  spec.helpful_info       three-tier extension (advice.md §4)
  spec.subject_summary    per-span subject distribution snapshot
  spec.content_type       from S2 screen
  meta.source             "wildchat"
  meta.judges             list of endpoint names that contributed
  meta.concord            full concord report

Per-span dicts use the Layer-1 ``AttributeValue.to_dict()`` shape:
``{"attribute": <sensitivity_type>, "value": <span text>, "subject_modifier": ...}``.

This is a pure transform (no LLM calls).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import SCHEMA_VERSION_L2

# Map our Layer-2 sensitivity_type -> Layer-1 ATTRIBUTE key. Everything that
# does not have an exact Layer-1 counterpart goes through ``other``.
_SENSITIVITY_TO_L1_ATTR = {
    "name":               "name",
    "email":              "email",
    "phone_number":       "phone_number",
    "address":            "address",
    "ssn":                "ssn",
    "driver_license":     "driver_license",
    "age":                "age",
    "gender":             "gender",
    "ethnicity":          "ethnicity",
    "religious_beliefs":  "religious_beliefs",
    "sexual_orientation": "sexual_orientation",
    "physical_health":    "physical_health",
    "mental_health":      "mental_health",
    "medications":        "medications",
    "allergies":          "allergies",
    "disabilities":       "disabilities",
    "family_history":     "family_history",
    "relationship_status": "relationship_status",
    "pet_ownership":      "pet_ownership",
    "employment":         "employment",
    "financial_situation": "financial_situation",
    "legal":              "legal",
    "education":          "employment",   # closest Layer-1 attr
    "location":           "address",
    "dates":              "dates",
    "third_party_identity": "name",       # third-party name reuses the slot
    "other":              "other",
}

# Map our span subject onto Layer-1 subject_modifier (used in shared_attr
# confusion samples). None means "self / no modifier".
_SUBJECT_TO_MODIFIER = {
    "self":          None,
    "third_party":   "third_party_acquaintance",
    "fictional":     None,   # fictional spans should rarely reach here
    "public_figure": "third_party_acquaintance",
    "quoted_doc":    None,
    "unknown":       None,
}

# The Layer-1 ``Spec.subject`` axis takes self/family/friend/coworker/third_party.
# We pick a sensible coarse value for downstream code that buckets on it.
_DOC_SUBJECT_FROM_SUBJECTS = {
    "self":          "self",
    "third_party":   "third_party",
    "fictional":     "third_party",
    "public_figure": "third_party",
    "quoted_doc":    "third_party",
    "unknown":       "self",
}

# Layer-1 task -> essential_policy. Mirror of synth.taxonomy.TASK_ESSENTIAL_POLICY.
_TASK_POLICY = {
    "Code_Generation": "none", "Code_Editing_And_Debugging": "none",
    "Translation": "none", "Summarization": "none", "Text_Editing": "none",
    "Answering_Multiple_Choice_Questions": "none",
    "Comparison_Ranking_And_Recommendation": "none",
    "Brainstorming_And_Idea_Generation": "none",
    "Information_Retrieval": "none", "General_Chitchat": "none",
    "Prompt_Generation_For_AI_Models": "none",
    "Personal_Advice": "domain", "Explanation_And_Practical_Advice": "domain",
    "Problem_Solving": "domain", "Non_Fictional_Document_Generation": "domain",
    "Back_And_Forth_Role_Playing": "domain",
    "Communication_Generation": "addressed_person",
    "Story_And_Script_Generation": "addressed_person",
    "Song_And_Poem_Generation": "addressed_person",
    "Character_Description_Generation": "addressed_person",
}


def _doc_subject(spans: List[Dict[str, Any]]) -> str:
    """Pick a single coarse Layer-1 ``subject`` for the whole prompt.
    Uses the most common per-span subject, mapped via _DOC_SUBJECT_FROM_SUBJECTS."""
    if not spans:
        return "self"
    counts: Dict[str, int] = {}
    for s in spans:
        counts[s.get("subject", "unknown")] = counts.get(s.get("subject", "unknown"), 0) + 1
    top = max(counts.items(), key=lambda kv: kv[1])[0]
    return _DOC_SUBJECT_FROM_SUBJECTS.get(top, "self")


def _to_l1_attribute(span: Dict[str, Any]) -> Dict[str, Any]:
    attr = _SENSITIVITY_TO_L1_ATTR.get(span.get("sensitivity_type", "other"), "other")
    out: Dict[str, Any] = {"attribute": attr, "value": str(span["span"])}
    mod = _SUBJECT_TO_MODIFIER.get(span.get("subject", "self"))
    if mod:
        out["subject_modifier"] = mod
    out["sensitivity_type"] = span.get("sensitivity_type", "other")
    out["necessity"] = span.get("necessity", "helpful")
    out["recommended_action"] = span.get("recommended_action", "remove")
    out["source_subject"] = span.get("subject", "unknown")
    return out


def unify_record(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert a (post-concord) record into a Layer-1-compatible row.

    Returns None if the record doesn't have a usable concord/consensus.
    """
    concord = rec.get("concord") or {}
    consensus = concord.get("consensus") or {}
    if not consensus:
        return None

    domain = consensus.get("domain") or "Other"
    task = consensus.get("task") or "General_Chitchat"

    e_spans = consensus.get("essential", [])
    h_spans = consensus.get("helpful", [])
    ne_spans = consensus.get("non_essential", [])

    essential_info = [_to_l1_attribute(s) for s in e_spans]
    helpful_info = [_to_l1_attribute(s) for s in h_spans]
    nonessential_info = [_to_l1_attribute(s) for s in ne_spans]

    spec = {
        "domain": domain,
        "task": task,
        "subject": _doc_subject(e_spans + h_spans + ne_spans),
        "embedding_style": "natural",
        "tone": "natural",
        "essential_policy": _TASK_POLICY.get(task, "domain"),
        "task_brief": None,
        "essential_info": essential_info,
        "nonessential_sensitive_info": nonessential_info,
        # Layer-2 extensions (do not break Layer-1 downstream code)
        "helpful_info": helpful_info,
        "content_type": (rec.get("screen") or {}).get("content_type"),
        "primary_context": consensus.get("primary_context"),
        "confusion_kind": None,
    }

    judges = []
    for k in ("judge_a", "judge_b"):
        ep = (rec.get(k) or {}).get("endpoint")
        if ep:
            judges.append(ep)

    return {
        "id": "l2-" + rec["id"],
        "source": "wildchat",
        "source_meta": {
            "conversation_id": rec.get("conversation_id"),
            "model": rec.get("model"),
            "timestamp": rec.get("timestamp"),
            "language": rec.get("language"),
            "wc_redacted_flag": bool(rec.get("redacted", False)),
            "user_words": rec.get("user_words"),
        },
        "spec": spec,
        "raw_prompt": rec["first_user"],
        "judge_out": {
            "judge_a": rec.get("judge_a"),
            "judge_b": rec.get("judge_b"),
        },
        "consistency": {
            "ne_iou": concord.get("ne_iou"),
            "e_iou": concord.get("e_iou"),
            "helpful_iou": concord.get("helpful_iou"),
            "domain_match": concord.get("domain_match"),
            "task_match": concord.get("task_match"),
            "subject_avg": concord.get("subject_avg"),
            "status": concord.get("status"),
        },
        "gold_reformulation": rec.get("gold_reformulation"),
        "human_verified": False,
        "verification": None,
        "meta": {
            "schema_version": SCHEMA_VERSION_L2,
            "judges": judges,
            "screen": rec.get("screen"),
        },
    }


def unify_all(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in records:
        u = unify_record(r)
        if u is not None:
            out.append(u)
    return out
