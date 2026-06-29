# Privacy-rewrite evaluator: findings

- Total samples scored: **2000** (our=500, papillon=500, prediax=500, PUFT=500)

## 1. Overall verdict and scores

- Verdict mix (ALL): good 28.65%, acceptable 27.25%, bad 44.1%.
- Mean reid_risk: **0.2042** (median 0.0, std 0.3378).
- Mean utility_score: **0.6968** (median 0.7, std 0.3134).
- Pearson(reid, utility) = **0.1166**, Spearman = **0.1215**.
- Per-dataset verdict breakdown:
    - **our**: good 44.4%, acceptable 23.2%, bad 32.4%; reid mean=0.149, util mean=0.7818.
    - **papillon**: good 39.0%, acceptable 28.8%, bad 32.2%; reid mean=0.0426, util mean=0.7172.
    - **prediax**: good 12.2%, acceptable 38.8%, bad 49.0%; reid mean=0.5782, util mean=0.7874.
    - **PUFT**: good 19.0%, acceptable 18.2%, bad 62.8%; reid mean=0.047, util mean=0.5008.

## 2. Privacy issues (ALL)

- Samples with at least one privacy issue: **30.55%**, with multiple distinct privacy issues: **6.15%**.
    - `direct_leak`: in **24.65%** of samples (874 instances).
    - `semantic_leak`: in **11.8%** of samples (448 instances).
    - `inferential_leak`: in **0.25%** of samples (5 instances).
    - `combination_leak`: in **0.0%** of samples (0 instances).
- Mean reid_risk by privacy issue type: see `02_privacy_issue_reid_risk.csv`.

## 3. Utility issues (ALL)

- Samples with at least one utility issue: **56.15%**, with multiple distinct utility issues: **2.3%**.
    - `lost_constraint`: in **51.7%** of samples (2748 instances).
    - `weakened_constraint`: in **2.85%** of samples (78 instances).
    - `over_generalization`: in **0.0%** of samples (0 instances).
    - `task_drift`: in **2.55%** of samples (64 instances).
    - `added_constraint`: in **1.35%** of samples (30 instances).
- Mean utility_score by utility issue type: see `03_utility_issue_utility_score.csv`.

## 4. New sensitive attributes

- Samples introducing new sensitive details: **43** (2.15%).
- Total new_sensitive items: **63**.
- Top categories (by item count):
    - other: 59
    - location/place: 4

## 5. Privacy-utility tradeoff

- High-utility & low-risk (ideal, util>0.7 & risk<=0.5): **31.0%**.
- High-utility & high-risk: **12.9%**.
- Low-utility & high-risk (worst case): **8.2%**.
- Low-utility & low-risk: **28.1%**.

## 6. Failure patterns (ALL)

- excessive abstraction causing intent loss: **51.7%**
- preserving overly specific descriptors: **30.3%**
- still-identifiable paraphrases (semantic leak): **11.8%**
- weakened-but-not-lost constraint: **2.85%**
- task drift / wrong task: **2.55%**
- introducing unrelated sensitive attributes: **2.15%**
- added unnecessary constraint: **1.35%**
- inferable from retained clues (inferential / combination): **0.25%**

## 7. Headline takeaways

- `our` has the highest rate of `good` verdicts (44.4%), while `PUFT` has the most `bad` verdicts (62.8%).
- reid_risk and utility_score are positively correlated (Pearson=0.1166) — keeping more useful detail also keeps more identifying detail, the classic tradeoff.
- Dominant privacy failure mode: `direct_leak` (24.65% of samples), followed by `semantic_leak` (11.8%).
- Dominant utility failure mode: `lost_constraint` (51.7% of samples), followed by `weakened_constraint` (2.85%).