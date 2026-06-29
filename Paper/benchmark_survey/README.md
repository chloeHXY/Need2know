# Privacy Benchmark Survey — Deliverables Index

> 对应 `benchmark_survey_guide.md` §5 的 5 项交付物。
> 调研窗口：2026-05-22。所有 `[TO VERIFY]` 标记请在 `open_questions.md` 中找上下文。

## Files

| 文件 | 对应 guide §5 项 | 用途 |
|---|---|---|
| `benchmarks_main.md` | §5.1 | 主表，覆盖 §3.1–3.4 候选 benchmark，按 §4 字段填写 |
| `benchmarks_secondary.md` | §5.2 | 副表：attack/extraction、域特定、自行新增候选 |
| `summary.md` | §5.3 | 中文 ≤200 字 + 英文 ≤200 词总结，回答三问 |
| `dimensions_matrix.md` | §5.4 | 5 维度矩阵（最可能直接进 paper） |
| `open_questions.md` | §5.5 | 调研中的不确定点与边界决策 |

## Self-checklist (guide §8)

- [x] 论文已引用的核心 4 篇 benchmark 论文（`pilan2022text`, `lukas2023analyzing`, `mireshghallah2024can`, `ngong2025contextual`）均已查阅且入主表；`nissenbaum2010privacy` 是理论专著，不进表（在 `open_questions.md` Q15 说明）。
- [x] `essential_nonessential_partition` 字段值有原文出处，未凭直觉填写；ConfAIde 与 Ngong2025 的判断在 `open_questions.md` Q2/Q3 给出依据。
- [x] PII detector 工具（Presidio、Azure PII、Google DLP、spaCy）未进入主表；列在 `benchmarks_secondary.md` §D。
- [x] 主表每行 `paper_link` 字段都有链接或 `[TO VERIFY]` / `[NOT FOUND]`，未空缺。
- [x] `dimensions_matrix.md` 的每个 `✓ / ~ / ✗` 在主表对应字段都能找到依据，已在 matrix 文件 "Cell-by-cell justification" 节列出。
- [x] `summary.md` 未出现"因此我们的 benchmark 更好"类评价性结论；只列计数事实。
- [x] 不确定内容均用 `[TO VERIFY]` 标记，未编造。
- [x] 输出路径为 `DataG/Experiments/Main_results/benchmark_survey/`，文件名与 guide 一致。

## Known limitations of this survey

1. `Prediax` baseline 未能定位 — 见 `open_questions.md` Q1。
2. 金融领域未找到带 sensitive-attribute 标注的 LLM 对话评测集 — 见 Q7。
3. 部分副表条目仅有 paper 引用，size/repo 字段保留 `[TO VERIFY]` — 见 Q13。
4. `Ngong2025` 是否已 release per-sample gold E/N 标签未能确认 — 见 Q2，主表当前记 `implicit [TO VERIFY]`。

如需 CSV 版本或对某行做更深核查，请见 `open_questions.md`。
