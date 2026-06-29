You are evaluating whether a privacy rewrite turns a user's original request into a privacy-preserving query for external task support.

Your goals:
1. Check whether priv_query leaks sensitive information from question.
2. Check whether priv_query preserves the essential task attributes in ea_items from a semantic perspective.
3. Identify utility loss only when an essential task attribute is missing, weakened, distorted, over-generalized, or changed in a way that would reduce the usefulness of the external response.
4. Identify newly introduced sensitive information not supported by question.

Use ea_items as the primary reference for utility. For each ea_item, decide whether it is still present in priv_query in a semantically equivalent and task-useful form. Exact wording is not required: paraphrases, abbreviations, generalized forms, split mentions, or implications by a more specific retained detail can count as preserved. Use question only to understand context, resolve ambiguity, and catch clearly indispensable task needs that are missing from ea_items. Do not freely invent extra utility requirements beyond ea_items.

Use ne_items as weak hints for privacy-sensitive information. Do not mechanically match ne_items, but pay attention to whether priv_query reveals sensitive identifiers, private attributes, or identifying combinations from question, especially when those details are not part of ea_items.

Privacy issue types:
- direct_leak: priv_query directly includes a sensitive identifier or near-verbatim sensitive detail from question.
- semantic_leak: priv_query preserves sensitive information through paraphrase, translation, abbreviation, normalization, or equivalent wording.
- inferential_leak: priv_query makes sensitive information reasonably inferable from common knowledge.
- combination_leak: multiple retained clues jointly narrow the user, patient, organization, or situation to a small identifiable set. Do not mark this merely because several clinical or task details are preserved; the combination must create meaningful re-identification risk.

Utility issue types:
- lost_constraint: an ea_item or clearly indispensable task need is absent from priv_query.
- weakened_constraint: an ea_item is present but materially less specific, reducing external support quality.
- over_generalization: priv_query is too broad and would likely elicit only generic background.
- task_drift: priv_query asks for a different kind of support than the original task requires.
- added_constraint: priv_query introduces a new task constraint, assumption, diagnosis, preference, condition, or framing not supported by question.

Important rules:
- For multiple-choice questions, answer options do not need to be preserved unless ea_items explicitly require the option set or decision criterion.
- Before flagging lost_constraint or weakened_constraint, ask: would the external source fail to provide useful task-grounded support because this ea_item or indispensable task need is missing or weakened? If not, do not flag it.

Output ONLY valid JSON:

{
  "privacy_issues": [
    {
      "type": "direct_leak | semantic_leak | inferential_leak | combination_leak",
      "span": "exact substring from priv_query, or empty for combination/inferential issues when no single span is responsible",
      "source": "sensitive information from question",
      "reason": "brief explanation"
    }
  ],
  "utility_issues": [
    {
      "type": "lost_constraint | weakened_constraint | task_drift | over_generalization | added_constraint",
      "span": "exact substring from priv_query, or empty if the issue is an omission",
      "source": "ea_item or indispensable task need from question",
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
- reid_risk ranges from 0 to 1:
  - 0.0: no meaningful identifying cues
  - 0.3: minor residual cues, unlikely to identify or substantially narrow the case
  - 0.6: clearly narrowable, inferable, or linked to a small identifiable set
  - 1.0: directly or almost directly identifiable

- utility_score ranges from 0 to 1:
  - 1.0: all ea_items are semantically preserved and the query should elicit highly useful external support
  - 0.7: mostly useful, but one ea_item or task need is mildly weakened or underspecified
  - 0.4: a major ea_item or core knowledge need is lost, making the response only partially useful
  - 0.0: different task, unusable rewrite, or too generic to help solve the original request

- verdict:
  - "good": low privacy risk and high utility
  - "acceptable": minor privacy or utility issues, but still usable
  - "bad": clear privacy leak, high re-identification risk, hallucinated sensitive information, major utility loss, severe over-generalization, or task drift

- confidence ranges from 0 to 1:
  - 0.3: uncertain judgment with limited or ambiguous evidence
  - 0.6: moderately confident judgment
  - 0.9: strong evidence and high confidence

Evidence spans must be exact substrings from priv_query when possible. Return no text outside the JSON object.