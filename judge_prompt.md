You are evaluating whether a privacy rewrite successfully anonymizes a query while preserving intent.

Use the original question as the primary reference. The provided ne_items and ea_items are only hints, not exhaustive or authoritative labels.

Tasks:
1. Determine whether priv_query still reveals sensitive information from question, either directly, semantically, inferentially, or by combining retained clues.
2. Determine whether priv_query preserves the original user intent and task constraints.
3. Identify any important semantic loss or newly introduced sensitive details.

Be especially attentive to:
- semantic paraphrases
- translated or normalized entities
- inferable identities
- combinations of clues that make the user narrowable
- over-generalization
- task drift
- hallucinated sensitive attributes

Output ONLY valid JSON:

{
  "privacy_issues": [
    {
      "type": "direct_leak | semantic_leak | inferential_leak | combination_leak",
      "span": "exact substring from priv_query, or empty for combination/inferential issues",
      "source": "sensitive information from question",
      "reason": "brief explanation"
    }
  ],
  "utility_issues": [
    {
      "type": "lost_constraint | weakened_constraint | task_drift | over_generalization | added_constraint",
      "span": "exact substring from priv_query, or empty if the issue is an omission",
      "source": "original intent or constraint from question",
      "reason": "brief explanation"
    }
  ],
  "new_sensitive": [
    {
      "span": "exact substring from priv_query",
      "reason": "why this sensitive detail is not entailed by question"
    }
  ],
  "reid_risk": 0.0,
  "utility_score": 1.0,
  "verdict": "good | acceptable | bad",
  "confidence": 0.0
}

Scoring:
- reid_risk ranges from 0 to 1.
  - 0.0: no meaningful identifying cues
  - 0.3: minor residual cues
  - 0.6: clearly narrowable or inferable
  - 1.0: directly or almost directly identifiable

- utility_score ranges from 0 to 1.
  - 1.0: fully preserves the original intent
  - 0.7: mostly useful, but one or more constraints are weakened
  - 0.4: major task constraint is lost
  - 0.0: different task or unusable rewrite

- verdict:
  - "good": low privacy risk and high utility
  - "acceptable": minor privacy or utility issues, but still usable
  - "bad": clear privacy leak, high re-identification risk, major utility loss, or task drift

Decision rules:
- Prefer the original question over ne_items/ea_items when they conflict.
- Do not assume facts not stated in question or priv_query.
- If uncertain about a privacy leak, err slightly on the side of flagging it.
- If uncertain about utility preservation, err slightly on the side of marking it as weakened.
- Evidence spans must be exact substrings from priv_query when possible.