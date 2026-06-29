# Privacy-rewrite evaluator: findings

- Total samples scored: **1500** (our=500, papillon=500, prediax=500)

## 1. Overall verdict and scores

- Verdict mix (ALL): good 10.27%, acceptable 81.73%, bad 8.0%.
- Mean reid_risk: **0.3407** (median 0.3, std 0.2616).
- Mean utility_score: **0.7206** (median 0.7, std 0.1342).
- Pearson(reid, utility) = **-0.4293**, Spearman = **-0.4374**.
- Per-dataset verdict breakdown:
    - **our**: good 10.4%, acceptable 84.2%, bad 5.4%; reid mean=0.2986, util mean=0.7194.
    - **papillon**: good 7.4%, acceptable 87.6%, bad 5.0%; reid mean=0.283, util mean=0.7126.
    - **prediax**: good 13.0%, acceptable 73.4%, bad 13.6%; reid mean=0.4404, util mean=0.7298.

## 2. Privacy issues (ALL)

- Samples with at least one privacy issue: **77.0%**, with multiple distinct privacy issues: **7.87%**.
    - `direct_leak`: in **30.2%** of samples (746 instances).
    - `semantic_leak`: in **3.0%** of samples (53 instances).
    - `inferential_leak`: in **10.47%** of samples (189 instances).
    - `combination_leak`: in **41.67%** of samples (680 instances).
- Mean reid_risk by privacy issue type: see `02_privacy_issue_reid_risk.csv`.

## 3. Utility issues (ALL)

- Samples with at least one utility issue: **86.2%**, with multiple distinct utility issues: **4.8%**.
    - `lost_constraint`: in **61.6%** of samples (1053 instances).
    - `weakened_constraint`: in **28.87%** of samples (466 instances).
    - `over_generalization`: in **0.07%** of samples (1 instances).
    - `task_drift`: in **0.13%** of samples (2 instances).
    - `added_constraint`: in **0.53%** of samples (8 instances).
- Mean utility_score by utility issue type: see `03_utility_issue_utility_score.csv`.

## 4. New sensitive attributes

- Samples introducing new sensitive details: **108** (7.2%).
- Total new_sensitive items: **130**.
- Top categories (by item count):
    - other: 85
    - contact/identifier: 15
    - location/place: 7
    - demographic/age/gender: 6
    - relationship/family: 6
    - medical/health: 5

## 5. Privacy-utility tradeoff

- High-utility & low-risk (ideal, util>0.7 & risk<=0.5): **11.4%**.
- High-utility & high-risk: **2.07%**.
- Low-utility & high-risk (worst case): **4.93%**.
- Low-utility & low-risk: **1.47%**.

## 6. Failure patterns (ALL)

- excessive abstraction causing intent loss: **61.6%**
- inferable from retained clues (inferential / combination): **50.67%**
- preserving overly specific descriptors: **32.73%**
- weakened-but-not-lost constraint: **28.87%**
- introducing unrelated sensitive attributes: **7.2%**
- still-identifiable paraphrases (semantic leak): **3.0%**
- added unnecessary constraint: **0.53%**
- task drift / wrong task: **0.13%**

## 7. Headline takeaways

- `prediax` has the highest rate of `good` verdicts (13.0%), while `prediax` has the most `bad` verdicts (13.6%).
- reid_risk and utility_score are negatively correlated (Pearson=-0.4293) — heavier anonymization helps privacy but hurts utility.
- Dominant privacy failure mode: `combination_leak` (41.67% of samples), followed by `direct_leak` (30.2%).
- Dominant utility failure mode: `lost_constraint` (61.6% of samples), followed by `weakened_constraint` (28.87%).
- Hallucinated/new sensitive details appear in 7.2% of rewrites — non-trivial and worth fixing in prompts.