# Survey Summary

> 仅陈述事实；不下评价性结论。所依据的字段值见 `benchmarks_main.md` / `benchmarks_secondary.md` / `dimensions_matrix.md`。

---

## 中文总结（≤ 200 字）

在主表覆盖的 12 个 privacy-related benchmark 中，**没有任何一个明确为每个样本同时给出 essential 与 non-essential 两个分离集合**；`Ngong2025` 在框架层面假设了这一区分，但其公开评测并未发布 gold per-sample 划分，因此记为 `implicit`（`[TO VERIFY]`）。**同时评估 utility 与 privacy** 的有 4 个明确（`Ngong2025`, `PrivQA`, `PUPA`, `PrivLM-Bench`），加上部分支持的 4 个共 8 个（再加 `TAB`, `ConfAIde`, `PrivacyLens`, `CI-Bench`）。**覆盖非 PII 敏感属性**（健康/财务/家庭/行踪/第三方身份）的明确为 4 个（`ConfAIde`, `Ngong2025`, `PrivacyLens`, `CI-Bench`），部分覆盖（含偶发 / 未单独评估）共 7 个（再加 `TAB`, `PrivQA`, `PUPA`）。

---

## English summary (≤ 200 words)

Across the 12 privacy-related benchmarks logged in the main table, **none provide an explicit per-sample partition into essential and non-essential information**; `Ngong2025` assumes such a split inside its framework but, to our knowledge, does not release per-sample gold labels, so we record it as `implicit` (marked `[TO VERIFY]`). **Joint privacy and utility evaluation** is explicit in 4 benchmarks (`Ngong2025`, `PrivQA`, `PUPA`, `PrivLM-Bench`); counting partial cases (`~`), 8 benchmarks report some form of utility alongside privacy (`TAB`, `ConfAIde`, `PrivacyLens`, `CI-Bench` additionally). **Coverage of non-PII sensitive attributes** (health, finance, family, whereabouts, third-party identity) is explicit in 4 benchmarks (`ConfAIde`, `Ngong2025`, `PrivacyLens`, `CI-Bench`); counting partial cases, 7 benchmarks touch non-PII sensitive context (`TAB`, `PrivQA`, `PUPA` additionally). De-identification benchmarks (`TAB`, `i2b2/n2c2`, `WikiPII`) and PII-leakage attack harnesses (`Lukas2023`, `ProPILE`, `PrivLM-Bench`, `lm-extraction-benchmark`) are PII-centric and do not target contextual non-essential disclosure as an evaluable axis. These statements are descriptive; no evaluative conclusion about which benchmark is sufficient or insufficient for a given research goal is drawn here.

---

## Per-question fact list

**Q1. Benchmarks that explicitly provide essential vs non-essential partition per sample:**
- None. Closest: `Ngong2025` provides this distinction at framework level, not as released per-sample gold labels (`[TO VERIFY]`).

**Q2. Benchmarks that jointly evaluate utility preservation and privacy leakage:**
- Explicit (`✓`): `Ngong2025`, `PrivQA`, `PUPA`, `PrivLM-Bench` (4).
- Partial (`~`, utility is a proxy or limited to a subset): `TAB` (information-loss proxy), `ConfAIde` (Tier 4 only), `PrivacyLens` (helpfulness judge), `CI-Bench` (task-completion).

**Q3. Benchmarks that cover non-PII sensitive attributes (health / finance / family / whereabouts / third-party identity):**
- Explicit (`✓`): `ConfAIde`, `Ngong2025`, `PrivacyLens`, `CI-Bench` (4).
- Partial (`~`, sensitive attributes appear but are not a separately evaluated axis): `TAB` (DEM/quasi-identifier), `PrivQA` (residence, family relation as protected categories), `PUPA` (incidentally present in real user prompts).
