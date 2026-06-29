# Dimensions Matrix — 5-axis comparison

> 行：主表中的 benchmark；列：5 个维度。
> 单元格取值：`✓` = 明确支持；`~` = 部分支持 / 隐式 / 仅小部分样本；`✗` = 不支持。
> 每个 `✓ / ~ / ✗` 的依据可在 `benchmarks_main.md` 对应行中核对。

| Benchmark | Explicit PII coverage | Non-PII sensitive coverage | Essential / Non-essential partition | Utility evaluation | Multi-domain (≥3 domains) |
|---|:---:|:---:|:---:|:---:|:---:|
| TAB | ✓ | ~ | ✗ | ~ | ✗ |
| i2b2 / n2c2 2014 De-id | ✓ | ✗ | ✗ | ✗ | ✗ |
| WikiPII | ✓ | ✗ | ✗ | ✗ | ✗ |
| Lukas2023 (PII Leakage) | ✓ | ✗ | ✗ | ✗ | ~ |
| ConfAIde | ~ | ✓ | ✗ | ~ | ~ |
| Ngong2025 (Contextual Privacy) | ~ | ✓ | ~ | ✓ | ~ |
| PrivacyLens | ~ | ✓ | ✗ | ~ | ✓ |
| CI-Bench | ~ | ✓ | ✗ | ~ | ✓ |
| ProPILE | ✓ | ✗ | ✗ | ✗ | ✗ |
| PrivQA (Chen 2023) | ✓ | ~ | ✗ | ✓ | ✗ |
| PUPA (PAPILLON) | ✓ | ~ | ✗ | ✓ | ✗ |
| PrivLM-Bench | ~ | ✗ | ✗ | ✓ | ✗ |

---

## Cell-by-cell justification (one line per non-trivial cell)

**TAB**
- `Explicit PII = ✓`: 8 entity categories incl. PERSON / LOC / ORG / DATETIME / CODE / DEM.
- `Non-PII sensitive = ~`: DEM (demographic) and quasi-identifier flags catch some sensitive context, but not health/finance/family as separate eval axes.
- `E/N partition = ✗`: identifier vs quasi-identifier ≠ task-essential vs non-essential.
- `Utility = ~`: information-loss proxy, no downstream task answer-quality eval.
- `Multi-domain = ✗`: legal court cases only.

**i2b2 / n2c2 2014**
- `PII = ✓`: 18 PHI categories.
- `Non-PII sensitive = ✗`: clinical content retained, not annotated as sensitive-to-suppress.
- `E/N = ✗`: by design — keep clinical content.
- `Utility = ✗`: F1 over PHI spans only.
- `Multi-domain = ✗`: clinical only.

**WikiPII**
- `PII = ✓`: standard NE categories.
- All other cells `✗`: pure span-level de-id.

**Lukas2023**
- `PII = ✓`: PII categories tagged across three corpora.
- `Non-PII sensitive = ✗`: not modeled.
- `E/N = ✗`: attack-time evaluation, no per-sample partition.
- `Utility = ✗`: privacy-only (perplexity is a model-level utility surrogate, not a task-utility eval — kept as ✗).
- `Multi-domain = ~`: legal (ECHR), email (Enron), reviews (Yelp).

**ConfAIde**
- `PII = ~`: Tier 1 enumerates info types incl. some PII (SSN), but PII *categorization* is not the focus.
- `Non-PII sensitive = ✓`: health, religion, sexual orientation, family, mental health, etc. are central.
- `E/N = ✗`: judges info-flow appropriateness; not per-task essential vs non-essential split. (Tier 4's "secret" is implicit, not annotated as such across the dataset.)
- `Utility = ~`: only Tier 4 evaluates summary quality alongside leakage.
- `Multi-domain = ~`: general scenarios; Tier 4 = workplace; not stratified across ≥3 explicit domains in our sense.

**Ngong2025**
- `PII = ~`: identifiers handled, but not category-stratified.
- `Non-PII sensitive = ✓`: explicit target.
- `E/N = ~`: framework's premise distinguishes essential vs non-essential, but no released *gold per-sample partition* `[TO VERIFY]`.
- `Utility = ✓`: judge-based response quality reported.
- `Multi-domain = ~`: ShareGPT covers many areas but eval is not domain-stratified.

**PrivacyLens**
- `PII = ~`: covers personal info but not PII-category-stratified the way TAB is.
- `Non-PII sensitive = ✓`: 493 seeds derived from privacy regulations + vulnerable-group literature.
- `E/N = ✗`: norm-violation labels, not per-task partition.
- `Utility = ~`: agent helpfulness judged alongside leakage.
- `Multi-domain = ✓`: health / finance / employment / family / etc.

**CI-Bench**
- `PII = ~`: handled but not the focus.
- `Non-PII sensitive = ✓`: contextual sensitive attributes per CI taxonomy.
- `E/N = ✗`: appropriate-flow labels, not per-task partition.
- `Utility = ~`: task-completion success measured.
- `Multi-domain = ✓`: synthetic generator spans multiple domains.

**ProPILE**
- `PII = ✓`: PII-tuple probing.
- All others `✗`: probing tool only.

**PrivQA (Chen 2023)**
- `PII = ✓`: protected attributes incl. PII types.
- `Non-PII sensitive = ~`: includes attributes like residence, family relation; health/finance not central.
- `E/N = ✗`: protected-set is global per run.
- `Utility = ✓`: QA accuracy on non-protected questions reported.
- `Multi-domain = ✗`: Wikipedia entities + images, not ≥3 distinct task domains in the medical/legal/finance sense.

**PUPA (PAPILLON)**
- `PII = ✓`: PII spans labeled in real user prompts.
- `Non-PII sensitive = ~`: incidentally present, not labeled as separate axis.
- `E/N = ✗`: PII spans labeled, but no "task-essential" set per item.
- `Utility = ✓`: response-quality vs no-rewrite reference, judge-based.
- `Multi-domain = ✗`: general user prompts, not domain-stratified.

**PrivLM-Bench**
- `PII = ~`: indirect — measures leakage of training-data records.
- `Non-PII sensitive = ✗`: not modeled.
- `E/N = ✗`: training-data leakage framing.
- `Utility = ✓`: downstream task accuracy paired with attacks.
- `Multi-domain = ✗`: GLUE-style + Enron.

---

## Counting summary (read off the matrix)

> Counts include `~` only where explicitly noted.

- **Benchmarks with `Essential / Non-essential partition = ✓`**: 0
- **Benchmarks with `Essential / Non-essential partition` ∈ {✓, ~}**: 1 (Ngong2025, partition is implicit / framework-internal, not gold-labeled per sample)
- **Benchmarks with `Utility evaluation = ✓`**: 4 (Ngong2025, PrivQA, PUPA, PrivLM-Bench)
- **Benchmarks with `Utility evaluation` ∈ {✓, ~}**: 8 (above + TAB, ConfAIde, PrivacyLens, CI-Bench)
- **Benchmarks with `Non-PII sensitive coverage = ✓`**: 4 (ConfAIde, Ngong2025, PrivacyLens, CI-Bench)
- **Benchmarks with `Non-PII sensitive coverage` ∈ {✓, ~}**: 7 (above + TAB, PrivQA, PUPA)
- **Benchmarks with `Multi-domain (≥3 domains) = ✓`**: 2 (PrivacyLens, CI-Bench)

These counts are stated as facts; no evaluative conclusion is drawn here per guide §5.3 / §8.
