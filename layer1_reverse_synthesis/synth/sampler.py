"""Spec sampler.

Turns a random seed into a structured ``Spec`` describing what the generator
should produce: domain, task, optional task brief, essential attributes
(+values), non-essential attributes (+values), subject, embedding style, tone.

Per-task essential policy (see taxonomy.TASK_ESSENTIAL_POLICY):
  * "none"             -> essential_info = []; spec.task_brief is set instead.
                          ALL sampled sensitive attributes go into NE.
  * "domain"           -> 1-2 essentials drawn from DOMAIN_ESSENTIAL_POOL[domain]
  * "addressed_person" -> force ``name`` essential + optional domain attr.

The sampler also occasionally produces "confusion" cases:
  * shared_attr        -> same attribute type appears in BOTH E and NE,
                          marked with ``subject_modifier`` so the generator
                          can frame the NE version as a third party naturally.
  * over_removal_trap  -> task is addressed-person + name is essential.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Set

from .taxonomy import (
    ATTRIBUTES,
    DOMAINS,
    DOMAIN_ESSENTIAL_POOL,
    SUBJECTS,
    EMBEDDING_STYLES,
    TASK_BRIEFS,
    TASK_ESSENTIAL_POLICY,
    TASK_FORCED_ESSENTIAL,
    TASKS,
    TONES,
)
from .value_bank import sample_value


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AttributeValue:
    attribute: str
    value: str
    # Optional natural-language hint for how the generator should frame this
    # value. Examples:
    #   None                          - default (about the user themselves)
    #   "third_party_coworker"        - frame as something a coworker mentioned
    #   "third_party_relative"        - frame as a relative's situation
    # The generator prompt expands these into freeform NL guidance.
    subject_modifier: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        d: Dict[str, Optional[str]] = {
            "attribute": self.attribute,
            "value": self.value,
        }
        if self.subject_modifier:
            d["subject_modifier"] = self.subject_modifier
        return d


@dataclass
class Spec:
    domain: str
    task: str
    subject: str
    embedding_style: str
    tone: str
    essential_info: List[AttributeValue]
    nonessential_sensitive_info: List[AttributeValue]
    # essential policy: "none" | "domain" | "addressed_person"
    essential_policy: str = "domain"
    # for "none" policy: a short freeform task description (non-sensitive)
    task_brief: Optional[str] = None
    confusion_kind: Optional[str] = None  # None | "shared_attr" | "over_removal_trap"
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["essential_info"] = [a.to_dict() for a in self.essential_info]
        d["nonessential_sensitive_info"] = [
            a.to_dict() for a in self.nonessential_sensitive_info
        ]
        return d


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class SamplerConfig:
    num_essential_min: int = 1
    num_essential_max: int = 2
    num_nonessential_min: int = 1
    num_nonessential_max: int = 3

    # Probability of producing a "confusion" sample.
    confusion_rate: float = 0.15

    # Distributions over diversity axes. None => uniform.
    style_weights: Optional[Dict[str, float]] = None
    subject_weights: Optional[Dict[str, float]] = None
    tone_weights: Optional[Dict[str, float]] = None
    domain_weights: Optional[Dict[str, float]] = None
    task_weights: Optional[Dict[str, float]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_THIRD_PARTY_MODIFIERS = [
    "third_party_relative",
    "third_party_coworker",
    "third_party_friend",
    "third_party_acquaintance",
]


def _weighted_choice(
    options: List[str],
    weights: Optional[Dict[str, float]],
    rng: random.Random,
) -> str:
    if not weights:
        return rng.choice(options)
    w = [weights.get(o, 1.0) for o in options]
    return rng.choices(options, weights=w, k=1)[0]


def _sample_attr_with_value(
    attribute: str,
    rng: random.Random,
    *,
    subject_modifier: Optional[str] = None,
) -> AttributeValue:
    return AttributeValue(
        attribute=attribute,
        value=sample_value(attribute, rng),
        subject_modifier=subject_modifier,
    )


# ---------------------------------------------------------------------------
# Core sampler
# ---------------------------------------------------------------------------

class Sampler:
    def __init__(self, cfg: SamplerConfig, rng: Optional[random.Random] = None) -> None:
        self.cfg = cfg
        self.rng = rng or random.Random()

    # ---- main entry --------------------------------------------------------
    def sample(self) -> Spec:
        if self.rng.random() < self.cfg.confusion_rate:
            return self._sample_confusion()
        return self._sample_standard()

    # ---- standard ----------------------------------------------------------
    def _sample_standard(self) -> Spec:
        domain = _weighted_choice(DOMAINS, self.cfg.domain_weights, self.rng)
        task = _weighted_choice(TASKS, self.cfg.task_weights, self.rng)
        policy = TASK_ESSENTIAL_POLICY.get(task, "domain")

        if policy == "none":
            return self._build_none_policy_spec(domain, task)
        if policy == "addressed_person":
            return self._build_addressed_person_spec(domain, task)
        return self._build_domain_policy_spec(domain, task)

    # ---- policy: none ------------------------------------------------------
    def _build_none_policy_spec(self, domain: str, task: str) -> Spec:
        """essential_info=[]; sample a TASK_BRIEFS entry; oversample NE.

        Since no sensitive attribute is essential here, we lean a bit harder
        on NE count -- the user is "padding" a task-driven request with
        irrelevant personal context.
        """
        briefs = TASK_BRIEFS.get(task, [f"a typical {task} request"])
        brief = self.rng.choice(briefs)

        # Slightly boost NE count for none-policy so the rewriter has more
        # to remove, but cap at the configured max.
        n_ne_min = max(self.cfg.num_nonessential_min, 2)
        n_ne_max = self.cfg.num_nonessential_max
        n_ne = self.rng.randint(n_ne_min, max(n_ne_min, n_ne_max))

        ne_attrs = self.rng.sample(ATTRIBUTES, k=min(n_ne, len(ATTRIBUTES)))
        ne = [_sample_attr_with_value(a, self.rng) for a in ne_attrs]

        return Spec(
            domain=domain,
            task=task,
            subject=_weighted_choice(SUBJECTS, self.cfg.subject_weights, self.rng),
            embedding_style=_weighted_choice(
                EMBEDDING_STYLES, self.cfg.style_weights, self.rng
            ),
            tone=_weighted_choice(TONES, self.cfg.tone_weights, self.rng),
            essential_info=[],
            nonessential_sensitive_info=ne,
            essential_policy="none",
            task_brief=brief,
            confusion_kind=None,
        )

    # ---- policy: addressed_person ------------------------------------------
    def _build_addressed_person_spec(self, domain: str, task: str) -> Spec:
        forced = TASK_FORCED_ESSENTIAL.get(task, ["name"])
        if not forced:
            forced = ["name"]
        essential = [_sample_attr_with_value(a, self.rng) for a in forced]
        # Optional second essential drawn from the domain pool.
        domain_pool = [a for a in DOMAIN_ESSENTIAL_POOL.get(domain, []) if a not in forced]
        if domain_pool and self.rng.random() < 0.4:
            essential.append(_sample_attr_with_value(self.rng.choice(domain_pool), self.rng))

        ne = self._sample_nonessential(
            essential_attrs={a.attribute for a in essential},
        )

        return Spec(
            domain=domain,
            task=task,
            subject=_weighted_choice(SUBJECTS, self.cfg.subject_weights, self.rng),
            embedding_style=_weighted_choice(
                EMBEDDING_STYLES, self.cfg.style_weights, self.rng
            ),
            tone=_weighted_choice(TONES, self.cfg.tone_weights, self.rng),
            essential_info=essential,
            nonessential_sensitive_info=ne,
            essential_policy="addressed_person",
            task_brief=None,
            confusion_kind=None,
        )

    # ---- policy: domain ----------------------------------------------------
    def _build_domain_policy_spec(self, domain: str, task: str) -> Spec:
        n_e = self.rng.randint(
            self.cfg.num_essential_min, self.cfg.num_essential_max
        )
        pool = list(DOMAIN_ESSENTIAL_POOL.get(domain, []))
        if not pool:
            pool = self.rng.sample(ATTRIBUTES, k=min(3, len(ATTRIBUTES)))
        e_attrs = self.rng.sample(pool, k=min(n_e, len(pool)))
        essential = [_sample_attr_with_value(a, self.rng) for a in e_attrs]

        ne = self._sample_nonessential(essential_attrs={a.attribute for a in essential})

        return Spec(
            domain=domain,
            task=task,
            subject=_weighted_choice(SUBJECTS, self.cfg.subject_weights, self.rng),
            embedding_style=_weighted_choice(
                EMBEDDING_STYLES, self.cfg.style_weights, self.rng
            ),
            tone=_weighted_choice(TONES, self.cfg.tone_weights, self.rng),
            essential_info=essential,
            nonessential_sensitive_info=ne,
            essential_policy="domain",
            task_brief=None,
            confusion_kind=None,
        )

    # ---- non-essential picking ---------------------------------------------
    def _sample_nonessential(self, *, essential_attrs: Set[str]) -> List[AttributeValue]:
        n_ne = self.rng.randint(
            self.cfg.num_nonessential_min, self.cfg.num_nonessential_max
        )
        pool = [a for a in ATTRIBUTES if a not in essential_attrs]
        attrs = self.rng.sample(pool, k=min(n_ne, len(pool)))
        return [_sample_attr_with_value(a, self.rng) for a in attrs]

    # ---- confusion sampling ------------------------------------------------
    def _sample_confusion(self) -> Spec:
        kind = self.rng.choices(
            ["shared_attr", "over_removal_trap"], weights=[0.6, 0.4], k=1
        )[0]
        if kind == "shared_attr":
            return self._sample_shared_attribute()
        return self._sample_over_removal_trap()

    def _sample_shared_attribute(self) -> Spec:
        """Same attribute type in E and NE; the NE version is marked with a
        third-party subject_modifier so the generator can phrase it naturally
        (e.g. "my coworker also has X" -- but the exact wording is up to the
        generator, NOT a hardcoded template)."""
        # Bias toward domains where shared_attr makes contextual sense.
        domain = _weighted_choice(
            ["Health_And_Wellness", "Personal_Relationships",
             "Financial_And_Corporate", "Employment_And_Applications"],
            self.cfg.domain_weights,
            self.rng,
        )
        # Pick a task whose policy keeps essential meaningful (not "none").
        task_candidates = [t for t in TASKS
                           if TASK_ESSENTIAL_POLICY.get(t, "domain") != "none"]
        task = _weighted_choice(task_candidates, self.cfg.task_weights, self.rng)

        pool = DOMAIN_ESSENTIAL_POOL.get(domain, ATTRIBUTES[:5])
        # Prefer attributes that plausibly apply to multiple subjects
        # (health/relationship/family-oriented); fall back to any pool item.
        preferred = [
            a for a in pool
            if a in {"physical_health", "mental_health", "allergies",
                     "disabilities", "medications", "family_history",
                     "financial_situation", "employment", "diet_type",
                     "religious_beliefs"}
        ]
        shared = self.rng.choice(preferred or pool)

        e_value = sample_value(shared, self.rng)
        ne_value = sample_value(shared, self.rng)
        modifier = self.rng.choice(_THIRD_PARTY_MODIFIERS)

        essential = [AttributeValue(shared, e_value)]
        ne = [AttributeValue(shared, ne_value, subject_modifier=modifier)]
        more = self._sample_nonessential(essential_attrs={shared})[:2]
        ne.extend(more)

        return Spec(
            domain=domain,
            task=task,
            subject="self",
            embedding_style=_weighted_choice(
                EMBEDDING_STYLES, self.cfg.style_weights, self.rng
            ),
            tone=_weighted_choice(TONES, self.cfg.tone_weights, self.rng),
            essential_info=essential,
            nonessential_sensitive_info=ne,
            essential_policy="domain",
            task_brief=None,
            confusion_kind="shared_attr",
            notes=[
                f"E and NE share attribute={shared}; the NE one belongs to a "
                f"different subject ({modifier}) -- the generator must phrase "
                f"this naturally."
            ],
        )

    def _sample_over_removal_trap(self) -> Spec:
        """Addressed-person task; tests the rewriter against over-removal of
        names/dates that are actually essential to the task."""
        forced_task = self.rng.choice([
            "Communication_Generation",
            "Story_And_Script_Generation",
            "Song_And_Poem_Generation",
            "Character_Description_Generation",
        ])
        domain = _weighted_choice(
            ["Personal_Relationships", "Employment_And_Applications",
             "Hobbies_And_Habits", "Religion"],
            self.cfg.domain_weights,
            self.rng,
        )
        spec = self._build_addressed_person_spec(domain, forced_task)
        spec.confusion_kind = "over_removal_trap"
        spec.notes = [
            "Trap: name (and optionally a domain attr) is essential because "
            "the task addresses or refers to a specific person; rewriter must "
            "not over-redact."
        ]
        return spec


# ---------------------------------------------------------------------------
# convenience
# ---------------------------------------------------------------------------

def make_default_sampler(seed: Optional[int] = None) -> Sampler:
    return Sampler(SamplerConfig(), random.Random(seed))
