# Privacy Benchmark Survey — Secondary Table

> 副表：attack/extraction 评测集、域特定数据集、自行新增候选，以及不确定是否升级到主表的边缘候选。
> 字段同主表。`[TO VERIFY]` 表示原文/官网未找到明确说明。

---

## A. Attack / Extraction harnesses

### A.1 Carlini et al. — GPT-2 Training Data Extraction

| field | value |
|---|---|
| `name` | (no fixed name) |
| `paper_citation` | Carlini, Tramèr, Wallace, Jagielski, Herbert-Voss, Lee, Roberts, Brown, Song, Erlingsson, Oprea, Raffel — "Extracting Training Data from Large Language Models", USENIX Security 2021 |
| `paper_link` | https://www.usenix.org/conference/usenixsecurity21/presentation/carlini-extracting ; https://www.usenix.org/system/files/sec21-carlini-extracting.pdf |
| `repo_link` | (project artifacts) https://nicholas.carlini.com/papers/ |
| `release_year` | 2021 |
| `task_format` | attack/extraction |
| `granularity` | sample-level (extracted strings / verified PII tuples) |
| `pii_categories_covered` | PERSON-NAME, EMAIL, PHONE, ADDRESS, ID, URL, code/secrets — extracted from GPT-2's training data. |
| `non_pii_sensitive_covered` | partial (incidentally, when extracted strings contain personal text) |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | no |
| `privacy_metric` | number of verifiable extractions; percentage memorized. |
| `domain_coverage` | general web corpus |
| `language` | en |
| `size` | manual verification set of ~600 hand-checked extractions in the original paper. |
| `intended_use` | demonstrate that LLMs memorize and emit training data verbatim. |
| `relation_to_us` | complementary |
| `gap_vs_our_setting` | (1) training-data extraction, not user-prompt rewriting; (2) PII-centric; (3) no E/N partition. |
| `notes` | Companion "lm-extraction-benchmark" challenge: https://github.com/google-research/lm-extraction-benchmark — provides 15k prefix–suffix targeted-extraction challenges from The Pile. |

### A.2 LM Extraction Benchmark (Google Research)

| field | value |
|---|---|
| `name` | lm-extraction-benchmark |
| `paper_citation` | Carlini et al. — "Quantifying Memorization Across Neural Language Models", ICLR 2023 (associated benchmark release) |
| `paper_link` | https://arxiv.org/abs/2202.07646 |
| `repo_link` | https://github.com/google-research/lm-extraction-benchmark |
| `release_year` | 2022 |
| `task_format` | attack/extraction (targeted: given prefix, recover suffix from training data) |
| `granularity` | sample-level (15k targeted prefix→suffix pairs) |
| `pii_categories_covered` | n/a (memorized text strings, often contain PII incidentally) |
| `non_pii_sensitive_covered` | no |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | no |
| `privacy_metric` | exact-suffix recall rate. |
| `domain_coverage` | general (The Pile) |
| `language` | en |
| `size` | 15,000 prefix→suffix challenge pairs |
| `intended_use` | targeted training-data extraction attack benchmark. |
| `relation_to_us` | complementary |
| `gap_vs_our_setting` | (1) memorization metric, not user-context disclosure; (2) no E/N partition; (3) no utility eval. |
| `notes` | — |

### A.3 Lukas2023 (mirror)

See main-table row #4. Mirrored here per guide §4: `task_format = attack/extraction` items should appear in this section as well. We do not duplicate the full row.

### A.4 ProPILE (mirror)

See main-table row #9. Mirrored here for the same reason.

---

## B. Domain-specific candidates

### B.1 MIMIC-III / MIMIC-IV (clinical notes — used for de-id experiments)

| field | value |
|---|---|
| `name` | MIMIC-III / MIMIC-IV (with de-id annotations supplied by data hosts) |
| `paper_citation` | Johnson et al. — "MIMIC-III, a freely accessible critical care database", *Scientific Data*, 2016 ; Johnson et al. — "MIMIC-IV", 2023. |
| `paper_link` | https://www.nature.com/articles/sdata201635 (III) ; https://www.nature.com/articles/s41597-022-01899-x (IV) |
| `repo_link` | https://physionet.org/content/mimiciii/ ; https://physionet.org/content/mimiciv/ |
| `release_year` | 2016 / 2023 |
| `task_format` | other (database; used as substrate for de-id and clinical QA) |
| `granularity` | record-level (notes have been pre-de-identified by hosts) |
| `pii_categories_covered` | HIPAA-PHI (already removed by data hosts; researchers can reintroduce synthetic PHI for de-id experiments). |
| `non_pii_sensitive_covered` | no (clinical content retained, but not split into essential vs non-essential per a downstream task). |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | n/a at corpus level; varies per derived task. |
| `privacy_metric` | n/a at corpus level. |
| `domain_coverage` | medical (ICU) |
| `language` | en |
| `size` | very large (millions of notes / events) |
| `intended_use` | research database for clinical NLP; substrate, not a privacy benchmark per se. |
| `relation_to_us` | partial overlap (we may use it as raw substrate for medical challenge set construction, not as a comparator). |
| `gap_vs_our_setting` | (1) not designed as a privacy benchmark; (2) no E/N partition; (3) requires DUA. |
| `notes` | Listed for completeness; it is *substrate*, not a published privacy benchmark. |

### B.2 LegalBench / privacy-relevant legal QA

| field | value |
|---|---|
| `name` | LegalBench (privacy-relevant subtasks) |
| `paper_citation` | Guha et al. — "LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning in LLMs", NeurIPS 2023 (D&B) |
| `paper_link` | https://arxiv.org/abs/2308.11462 |
| `repo_link` | https://github.com/HazyResearch/legalbench |
| `release_year` | 2023 |
| `task_format` | MCQ / open QA |
| `granularity` | sample-level |
| `pii_categories_covered` | none as a category; some subtasks reason about privacy law (e.g. CCPA, contract clauses). |
| `non_pii_sensitive_covered` | partial (privacy clauses, not direct user-data sensitive disclosures) |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | yes (task accuracy) |
| `privacy_metric` | none (legal-reasoning correctness, not privacy leakage) |
| `domain_coverage` | legal |
| `language` | en |
| `size` | 162 subtasks total; privacy-relevant fraction `[TO VERIFY]` |
| `intended_use` | legal-reasoning benchmark; not a privacy-leakage benchmark. |
| `relation_to_us` | out-of-scope but cited |
| `gap_vs_our_setting` | n/a — listed only to head off potential confusion with our legal-domain challenge set. |
| `notes` | — |

---

## C. Edge candidates that may or may not be in scope

### C.1 PrivacyRestore

| field | value |
|---|---|
| `name` | PrivacyRestore |
| `paper_citation` | Zhang, Du, et al. — "PrivacyRestore: Privacy-Preserving Inference in Large Language Models via Privacy Removal and Restoration", arXiv 2024 |
| `paper_link` | https://arxiv.org/abs/2406.01394 |
| `repo_link` | `[TO VERIFY]` |
| `release_year` | 2024 |
| `task_format` | prompt rewriting (remove privacy spans, restore in attention via activation steering on the local side) |
| `granularity` | span-level |
| `pii_categories_covered` | PERSON, LOCATION, DATE, MEDICAL-CONDITION, IDs (per evaluation tasks). |
| `non_pii_sensitive_covered` | partial — its medical evaluation includes condition spans; not framed as separate evaluation axis. |
| `essential_nonessential_partition` | no — defines a "privacy span" set per item, with the rest assumed retained. There is no annotated set of "task-essential" tokens distinct from privacy spans. |
| `utility_evaluation` | yes — task quality vs no-privacy baseline. |
| `privacy_metric` | leakage of privacy spans to remote model. |
| `domain_coverage` | medical, legal, general (per the paper's task setup). |
| `language` | en |
| `size` | `[TO VERIFY]` |
| `intended_use` | privacy-preserving inference framework with paired evaluation. |
| `relation_to_us` | directly comparable (closely related to our query-rewriting setting). |
| `gap_vs_our_setting` | (1) privacy-span framing, no E/N partition; (2) bespoke evaluation, not standardized as a public benchmark. |
| `notes` | We placed this in the secondary table because it is methodology-paired-with-evaluation, not a standalone benchmark release. |

### C.2 Preempt (Pr$\epsilon\epsilon$mpt)

| field | value |
|---|---|
| `name` | Preempt |
| `paper_citation` | Glukhov, Kandpal, et al. — "Pr$\epsilon\epsilon$mpt: Sanitizing Sensitive Prompts for LLMs", NDSS 2026 (preprint 2024–2025) |
| `paper_link` | https://arxiv.org/abs/2504.05147 ; https://www.cs.toronto.edu/~dglukhov/Preempt.pdf |
| `repo_link` | `[TO VERIFY]` |
| `release_year` | 2024 (preprint) / 2026 (NDSS) |
| `task_format` | prompt rewriting (cryptographic-style sanitization of sensitive tokens) |
| `granularity` | span/token-level |
| `pii_categories_covered` | PII (person, ID-like tokens) plus user-defined sensitive tokens. |
| `non_pii_sensitive_covered` | partial (user-specified sensitive tokens; no standard non-PII evaluation axis) |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | yes — utility = response equivalence after de-sanitization. |
| `privacy_metric` | formal privacy guarantee on substituted tokens; empirical leakage rate. |
| `domain_coverage` | general |
| `language` | en |
| `size` | `[TO VERIFY]` (small evaluation suite) |
| `intended_use` | system + evaluation of cryptographic prompt sanitization. |
| `relation_to_us` | complementary |
| `gap_vs_our_setting` | (1) token-replacement framing rather than CI-style rewriting; (2) no E/N partition; (3) small evaluation set. |
| `notes` | Listed because guide §3.4 explicitly mentions "local–remote LLM split inference + privacy filter" works. |

### C.3 InferDPT

| field | value |
|---|---|
| `name` | InferDPT |
| `paper_citation` | Tong, Chen, et al. — "InferDPT: Privacy-Preserving Inference for Closed-Box Large Language Models", IEEE TDSC 2025 (preprint arXiv 2310.12214, 2023) |
| `paper_link` | https://arxiv.org/abs/2310.12214 ; https://ieeexplore.ieee.org/document/10922117 |
| `repo_link` | https://github.com/mengtong0110/InferDPT |
| `release_year` | 2023 (preprint) / 2025 (TDSC) |
| `task_format` | prompt rewriting (DP perturbation of user prompt before remote inference) |
| `granularity` | token-level |
| `pii_categories_covered` | PII categories implicitly via DP-perturbed tokens; not category-stratified. |
| `non_pii_sensitive_covered` | no |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | yes — generation quality (BLEU/ROUGE/judge) on downstream tasks. |
| `privacy_metric` | DP-ε; empirical reconstruction-attack success rate. |
| `domain_coverage` | general |
| `language` | en |
| `size` | task-dependent |
| `intended_use` | DP-text-generation framework; evaluates utility/privacy on standard NLP tasks. |
| `relation_to_us` | complementary |
| `gap_vs_our_setting` | (1) DP at token level, no semantic E/N partition; (2) no non-PII sensitive coverage; (3) no domain-stratified eval. |
| `notes` | The user's `InferDPT_阅读笔记.md` and `new inferdpt.pdf` in the workspace suggest familiarity; included for cross-reference. |

### C.4 Priv-IQ / Priv-QA (Wang et al., 2025 — *not* the Chen 2023 PrivQA)

| field | value |
|---|---|
| `name` | Priv-QA (Wang et al., 2025) — distinct from Chen et al.'s PrivQA |
| `paper_citation` | "PRIV-QA: Privacy-Preserving Question Answering for Cloud Large Language Models", arXiv 2025 |
| `paper_link` | https://arxiv.org/abs/2502.13564 |
| `repo_link` | `[TO VERIFY]` |
| `release_year` | 2025 |
| `task_format` | prompt rewriting |
| `granularity` | sample-level / span-level |
| `pii_categories_covered` | PII + sensitive keywords |
| `non_pii_sensitive_covered` | partial — keyword-level, not CI-categorized. |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | yes — answer quality post-rewrite. |
| `privacy_metric` | leakage rate of privacy keywords to remote LLM. |
| `domain_coverage` | general (with sensitive-keyword test sets) |
| `language` | en |
| `size` | `[TO VERIFY]` |
| `intended_use` | privacy-preserving QA pipeline for cloud LLMs. |
| `relation_to_us` | complementary |
| `gap_vs_our_setting` | (1) keyword-level, not CI-level; (2) no E/N partition; (3) bespoke evaluation. |
| `notes` | Naming overlap with Chen 2023 PrivQA causes recurring confusion; we list both separately. |

### C.5 Priv-IQ

| field | value |
|---|---|
| `name` | Priv-IQ |
| `paper_citation` | "Priv-IQ: A Benchmark and Comparative Evaluation of Large Multimodal Models on Privacy", *AI* (MDPI) 2025 |
| `paper_link` | https://www.mdpi.com/2673-2688/6/2/29 |
| `repo_link` | `[TO VERIFY]` |
| `release_year` | 2025 |
| `task_format` | MCQ + multimodal QA |
| `granularity` | sample-level (per "competency": visual privacy, multilingual, privacy-law knowledge, etc.) |
| `pii_categories_covered` | varies across 8 competencies. |
| `non_pii_sensitive_covered` | partial (privacy-law and visual privacy components touch sensitive context) |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | n/a — privacy reasoning only. |
| `privacy_metric` | accuracy on privacy-related competency questions. |
| `domain_coverage` | multi-domain (law, visual, multilingual) |
| `language` | multi |
| `size` | `[TO VERIFY]` |
| `intended_use` | benchmarking multimodal LLMs' privacy intelligence. |
| `relation_to_us` | out-of-scope but cited (multimodal privacy reasoning, not query rewriting). |
| `gap_vs_our_setting` | n/a — listed for completeness. |
| `notes` | — |

### C.6 PrivAuditor

| field | value |
|---|---|
| `name` | PrivAuditor |
| `paper_citation` | "PrivAuditor: Benchmarking Data Protection Vulnerabilities in LLM Adaptation", NeurIPS 2024 (D&B Track) |
| `paper_link` | https://proceedings.neurips.cc/paper_files/paper/2024/hash/12b18a15dcd73e1991e9959a94375fab-Abstract-Datasets_and_Benchmarks_Track.html |
| `repo_link` | `[TO VERIFY]` |
| `release_year` | 2024 |
| `task_format` | attack/extraction (against fine-tuned/adapted LLMs) |
| `granularity` | sample-/record-level |
| `pii_categories_covered` | training-data PII implicit in adaptation corpora. |
| `non_pii_sensitive_covered` | no |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | partial — task accuracy on adapted tasks. |
| `privacy_metric` | leakage attack success across adaptation methods. |
| `domain_coverage` | general |
| `language` | en |
| `size` | `[TO VERIFY]` |
| `intended_use` | systematic comparison of fine-tuning methods' privacy leakage. |
| `relation_to_us` | complementary |
| `gap_vs_our_setting` | (1) training-data leakage focus; (2) no CI; (3) no E/N partition. |
| `notes` | — |

---

## D. Tools that are **NOT** benchmarks (per guide §2.3 — not in main table)

Listed only so reviewers do not confuse them with benchmarks:

- **Microsoft Presidio** — PII detection/anonymization SDK. https://github.com/microsoft/presidio
- **spaCy NER / Stanza NER** — generic NER, sometimes used as PII tagger.
- **Azure AI Language PII detection** — commercial PII detection service.
- **Google DLP API** — commercial PII detection service.

These are *detectors / anonymizers*, not labeled evaluation sets, and are deliberately excluded from the main table.

---

## End of secondary table.
