# Privacy Benchmark Survey — Main Table

> 主表：覆盖 §3.1–3.4 候选 benchmark。字段对应 guide §4。
> 所有信息来自论文/官方 repo。无法核实的字段用 `[TO VERIFY]`。
> 不下评价性结论，只列事实。

---

## Index of benchmarks in this table

1. TAB (Text Anonymization Benchmark)
2. i2b2 / n2c2 2014 De-identification
3. WikiPII (Wikipedia-derived biographical PII)  *[TO VERIFY canonical version]*
4. Lukas2023 PII Leakage Evaluation Suite
5. ConfAIde
6. Ngong2025 — Safeguarding Contextual Privacy (ShareGPT-based)
7. PrivacyLens
8. CI-Bench
9. ProPILE
10. PrivQA (Chen et al., 2023)
11. PUPA (PAPILLON)
12. PrivLM-Bench

---

## 1. TAB (Text Anonymization Benchmark)

| field | value |
|---|---|
| `name` | TAB |
| `paper_citation` | Pilán, Lison, Øvrelid, Papadopoulou, Sánchez, Batet — "The Text Anonymization Benchmark (TAB): A Dedicated Corpus and Evaluation Framework for Text Anonymization", *Computational Linguistics*, 48(4), 2022 |
| `paper_link` | https://direct.mit.edu/coli/article/48/4/1053/113021 (also https://arxiv.org/abs/2202.00443) |
| `repo_link` | https://github.com/NorskRegnesentral/text-anonymization-benchmark ; HF: https://huggingface.co/datasets/ildpil/text-anonymization-benchmark |
| `release_year` | 2022 |
| `task_format` | text de-id |
| `granularity` | span (with semantic category and direct/quasi-identifier flag) |
| `pii_categories_covered` | PERSON, CODE, LOC, ORG, DEM (demographic), DATETIME, QUANTITY, MISC; each span additionally tagged `DIRECT` vs `QUASI` identifier |
| `non_pii_sensitive_covered` | partial — DEM (demographic) and quasi-identifier categories cover some sensitive attributes (e.g. ethnicity, health refs in court cases) but the benchmark does not target health/finance/family/whereabouts as a separate evaluable axis. |
| `essential_nonessential_partition` | no — TAB annotates which spans are identifiers and whether masking each is needed for re-identification protection; it does not give per-sample "task-essential information to retain" vs "non-essential to suppress" sets. |
| `utility_evaluation` | partial — utility is approximated by *information loss* over masked spans (recall/precision over identifier spans + an information-theoretic IL metric); no downstream task answer-quality evaluation. |
| `privacy_metric` | entity-level recall/precision of identifier masking; weighted by re-identification risk; specifically evaluates direct-identifier recall and quasi-identifier mention recall. |
| `domain_coverage` | legal (European Court of Human Rights court cases) |
| `language` | en |
| `size` | 1,268 English court cases |
| `intended_use` | benchmark + evaluation framework for text anonymization systems |
| `relation_to_us` | partial overlap |
| `gap_vs_our_setting` | (1) PII/identifier-centric, no E/N partition; (2) single legal domain only; (3) utility is information-loss proxy, not task answer quality. |
| `notes` | v1.0 release. The annotation distinguishes DIRECT vs QUASI identifiers — useful for re-id risk analysis, but distinct from "essential to task" vs "non-essential to task" partitioning. |

---

## 2. i2b2 / n2c2 2014 De-identification

| field | value |
|---|---|
| `name` | i2b2/UTHealth 2014 De-identification (n2c2 2014) |
| `paper_citation` | Stubbs & Uzuner — "Annotating longitudinal clinical narratives for de-identification: The 2014 i2b2/UTHealth corpus", *Journal of Biomedical Informatics*, 2015 |
| `paper_link` | https://pmc.ncbi.nlm.nih.gov/articles/PMC4978170/ |
| `repo_link` | Hosted via DBMI Harvard / n2c2 portal: https://n2c2.dbmi.hms.harvard.edu/data-sets ; HF mirror: https://huggingface.co/datasets/bigbio/n2c2_2014_deid |
| `release_year` | 2014 (corpus) / 2015 (paper) |
| `task_format` | text de-id |
| `granularity` | span |
| `pii_categories_covered` | 18 PHI categories: NAME (patient/doctor/username), PROFESSION, LOCATION (street, city, state, country, zip, hospital, organization, other), AGE, DATE, CONTACT (phone, fax, email, URL, IP), IDs (MRN, license, SSN, etc.) |
| `non_pii_sensitive_covered` | no — corpus is focused on HIPAA-style PHI removal. Although the underlying notes mention diseases, the annotation schema does not treat health-condition descriptions as sensitive items to be evaluated; they are intentionally retained. |
| `essential_nonessential_partition` | no — by design: the goal is to remove identifiers while keeping clinical content fully intact. There is no per-sample "task-essential information" set to retain vs "non-essential sensitive context" set to suppress. |
| `utility_evaluation` | no — challenge metrics are F1 over PHI spans only. |
| `privacy_metric` | entity-level F1 (token-/span-level), HIPAA-PHI strict and i2b2-PHI strict variants. |
| `domain_coverage` | medical (longitudinal clinical narratives, diabetic patients) |
| `language` | en |
| `size` | ~1,304 records, 296 patients (per challenge release) |
| `intended_use` | shared task for clinical text de-identification systems |
| `relation_to_us` | partial overlap |
| `gap_vs_our_setting` | (1) HIPAA-PHI only, no non-PII contextual disclosure; (2) no E/N partition; (3) single clinical domain. |
| `notes` | Earlier i2b2 2006 challenge (Uzuner et al.) is a smaller predecessor focusing on 8 PHI categories. The 2014 release expanded to 18 PHI categories. |

---

## 3. WikiPII / Wikipedia-derived biographical PII

| field | value |
|---|---|
| `name` | WikiPII (Wikipedia biographies for sanitization evaluation) |
| `paper_citation` | Often cited via Lison, Pilán, Sánchez, Batet, Øvrelid — "Anonymisation Models for Text Data: State of the Art, Challenges and Future Directions", ACL 2021. Pilán et al. 2022 (TAB) also evaluate on Wikipedia biographies. *[TO VERIFY whether "WikiPII" denotes a single canonical release; multiple Wikipedia-bio sanitization sets exist.]* |
| `paper_link` | https://aclanthology.org/2021.acl-long.323/ ; secondary use described in https://hackernoon.com/datasets-for-evaluating-text-sanitization-techniques |
| `repo_link` | `[TO VERIFY]` — not a single canonical dataset card; some replications shared on GitHub (e.g. NorskRegnesentral). |
| `release_year` | 2021 (most-cited variant) |
| `task_format` | text de-id |
| `granularity` | span |
| `pii_categories_covered` | PERSON, LOCATION, DATE, ORGANIZATION, NUMERIC, MISC (varies per replication) |
| `non_pii_sensitive_covered` | no |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | no — typically reported as masking F1 against gold PII spans. |
| `privacy_metric` | entity-level recall/precision over PII spans. |
| `domain_coverage` | general (encyclopedic biographies) |
| `language` | en |
| `size` | `[TO VERIFY]` — varies across releases (commonly a few hundred biographies). |
| `intended_use` | evaluating text-sanitization / re-identification protection on factual biographical text. |
| `relation_to_us` | partial overlap |
| `gap_vs_our_setting` | (1) PII spans only; (2) no E/N partition; (3) no task-utility evaluation. |
| `notes` | Multiple non-canonical "WikiPII" variants exist; the user should confirm which release they intend to cite. |

---

## 4. Lukas2023 PII Leakage Evaluation Suite

| field | value |
|---|---|
| `name` | (no fixed name) — released as `analysing_pii_leakage` |
| `paper_citation` | Lukas, Salem, Sim, Tople, Wutschitz, Zanella-Béguelin — "Analyzing Leakage of Personally Identifiable Information in Language Models", IEEE S&P 2023 |
| `paper_link` | https://arxiv.org/abs/2302.00539 ; https://ieeexplore.ieee.org/document/10179300 |
| `repo_link` | https://github.com/microsoft/analysing_pii_leakage |
| `release_year` | 2023 |
| `task_format` | attack/extraction (PII extraction, PII reconstruction, PII inference attacks against fine-tuned LMs) |
| `granularity` | attribute-type (PII categories within fine-tuning corpora) |
| `pii_categories_covered` | PERSON-NAME, EMAIL, PHONE, ADDRESS, DATE, ORG, URL, etc. (categories detected/scored against a PII tagger over training corpora ECHR, Enron, Yelp). |
| `non_pii_sensitive_covered` | no |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | no (privacy-only, paired with perplexity for utility check on the LM, not a downstream task). |
| `privacy_metric` | game-based: extraction success rate, inference-attack accuracy (AUC), reconstruction success rate; tagged-PII recall. |
| `domain_coverage` | legal (ECHR), email (Enron), reviews (Yelp) |
| `language` | en |
| `size` | not a standalone "test set" — three fine-tuning corpora used as evaluation harness |
| `intended_use` | rigorous game-based evaluation of PII leakage from fine-tuned language models. |
| `relation_to_us` | complementary (it is an attack/leakage harness, not a contextual-integrity benchmark) |
| `gap_vs_our_setting` | (1) PII-only; (2) operates at training-data leakage level, not user-prompt level; (3) no E/N partition. |
| `notes` | This is best logged as an attack harness; we mirror it in `benchmarks_secondary.md` as well, as guide §4 instructs `attack/extraction` items to also appear there. |

---

## 5. ConfAIde

| field | value |
|---|---|
| `name` | ConfAIde |
| `paper_citation` | Mireshghallah, Kim, Zhou, Tsvetkov, Sap, Shokri, Choi — "Can LLMs Keep a Secret? Testing Privacy Implications of Language Models via Contextual Integrity Theory", ICLR 2024 |
| `paper_link` | https://arxiv.org/abs/2310.17884 ; https://openreview.net/forum?id=gmg7t8b4s0 |
| `repo_link` | https://github.com/skywalker023/confAIde ; https://confaide.github.io/ |
| `release_year` | 2023 (arXiv) / 2024 (ICLR) |
| `task_format` | MCQ / Likert rating (Tier 1–3) and open-ended generation with judge (Tier 4 / Tier 2.a meeting-summary) |
| `granularity` | sample-level (each item is one CI scenario / one info-flow tuple) |
| `pii_categories_covered` | varies by tier; Tier 1 enumerates ~10 information types (SSN, religious views, sexual orientation, health, location, work info, family details, etc.). |
| `non_pii_sensitive_covered` | yes — explicitly covers non-PII sensitive types (health condition, religious belief, sexual orientation, family details, mental health, infidelity, etc.); these are central to Tier 1–3. |
| `essential_nonessential_partition` | no — ConfAIde judges *whether sharing a piece of information is appropriate given (actor, recipient, transmission principle, purpose)*. It does **not** annotate, per task, the set of information that must be preserved to complete a goal vs the set that should be suppressed. Tier 4 evaluates whether the model leaks a secret while still producing a meeting summary, but the "what is essential to the summary" set is implicit, not annotated. |
| `utility_evaluation` | partial — Tier 4 measures "summary quality" (judged) jointly with whether the secret is leaked (judged); Tier 1–3 are privacy-judgment only. |
| `privacy_metric` | Tier 1–3: correlation/agreement with human annotators on appropriateness ratings; Tier 4: secret-leakage rate (judge-based). |
| `domain_coverage` | general; Tier 4 uses workplace meeting scenario. |
| `language` | en |
| `size` | Tier 1: ~98 info types × contexts; Tier 2: 98 vignettes × actors × principles → ~270 + 98 (a/b) items; Tier 3: 270 items; Tier 4: ~20 hand-crafted meeting scripts (numbers per official site). *[TO VERIFY exact counts in current repo release]* |
| `intended_use` | benchmark for contextual privacy reasoning of instruction-tuned LLMs. |
| `relation_to_us` | directly comparable (closest contextual-integrity benchmark) |
| `gap_vs_our_setting` | (1) no per-sample E/N partition; (2) Tier 4 utility is judge-based summary score, not task-grounded answer correctness; (3) does not target query rewriting. |
| `notes` | Guide §9 explicitly warns this row is the most error-prone: ConfAIde tests *info-flow appropriateness*, not *task-essential vs non-essential* labels. We mark `essential_nonessential_partition = no`, with the caveat that Tier 4 implicitly distinguishes "secret" from "summary content". |

---

## 6. Ngong2025 — Safeguarding Contextual Privacy in Conversational Agents

| field | value |
|---|---|
| `name` | (no short benchmark name; framework name "Contextual Privacy Framework"; evaluation built on ShareGPT subset) |
| `paper_citation` | Ngong, Kadhe, Wang, Sattigeri, Daly, Rawat, Aggarwal — "Protecting Users From Themselves: Safeguarding Contextual Privacy in Interactions with Conversational Agents", ACL 2025 Findings (also NeurIPS 2024 workshop / SafeGenAi) |
| `paper_link` | https://arxiv.org/abs/2502.18509 ; https://aclanthology.org/2025.findings-acl.1343/ ; https://openreview.net/forum?id=ZTexorZQqT |
| `repo_link` | `[TO VERIFY]` — paper does not advertise a self-contained benchmark download; evaluation uses ShareGPT samples plus the framework's own labels. |
| `release_year` | 2024 (workshop) / 2025 (ACL Findings) |
| `task_format` | dialogue / prompt rewriting (the framework rewrites user inputs to remove non-essential context before sending to a remote LCA) |
| `granularity` | span + sample-level (CI-tuple labels: data-subject, sender, recipient, attribute type, transmission principle) |
| `pii_categories_covered` | uses an attribute taxonomy derived from Nissenbaum's CI: identifiers + sensitive attributes (health, financial, family, location, relationship, etc.) — primary focus is contextual sensitive attributes, not surface PII. |
| `non_pii_sensitive_covered` | yes — explicitly covers non-PII contextual disclosures (health, family, finance, third-party identity, etc.) as the core target. |
| `essential_nonessential_partition` | implicit / partial — the framework's premise is that *task-relevant* information should pass through and *task-irrelevant sensitive context* should be filtered, and rewritten outputs are evaluated for both. However, the public artifact does not appear to ship a per-sample gold partition of "essential vs non-essential" tokens; the partition is produced on-the-fly by the framework and judged by an LLM evaluator on ShareGPT. *[TO VERIFY whether the released artifact includes per-sample gold E/N labels.]* |
| `utility_evaluation` | yes — utility ("task fulfillment" or "response quality") is judged after rewriting; reported alongside contextual-privacy gain. |
| `privacy_metric` | judge-based contextual privacy score (whether rewriting preserves context-appropriate info flow); plus PII removal counts. |
| `domain_coverage` | general (ShareGPT covers many domains; analysis is not domain-stratified). |
| `language` | en |
| `size` | evaluation uses a sampled subset of ShareGPT conversations (`[TO VERIFY exact n]`). |
| `intended_use` | local intermediary that reformulates user input to a remote LCA so contextual privacy is preserved. |
| `relation_to_us` | directly comparable (this is the closest CI-based rewriting framework; shares the goal of preserving task utility while suppressing non-essential sensitive context). |
| `gap_vs_our_setting` | (1) no released gold E/N partition per sample; (2) no domain-stratified medical/legal/finance challenge sets; (3) utility is a single LLM-judge score, not paired with grounded task accuracy. |
| `notes` | Guide §9: confirm whether this is a *taxonomy/methodology* paper or a *dataset* paper. Based on its public artifact, it is best described as **methodology + framework + small evaluation set**, not a standalone benchmark release. |

---

## 7. PrivacyLens

| field | value |
|---|---|
| `name` | PrivacyLens |
| `paper_citation` | Shao, Li, Lin, et al. — "PrivacyLens: Evaluating Privacy Norm Awareness of Language Models in Action", NeurIPS 2024 (Datasets & Benchmarks Track) |
| `paper_link` | https://arxiv.org/abs/2409.00138 ; https://papers.nips.cc/paper_files/paper/2024/hash/a2a7e58309d5190082390ff10ff3b2b8-Abstract-Datasets_and_Benchmarks_Track.html |
| `repo_link` | https://github.com/SALT-NLP/PrivacyLens ; project page https://salt-nlp.github.io/PrivacyLens/ |
| `release_year` | 2024 |
| `task_format` | tool-use / agent trajectory (multi-level: privacy-sensitive seed → vignette → agent trajectory with tools) |
| `granularity` | sample-level (each scenario carries a "data subject – data type – sender – recipient – purpose" CI tuple plus a leakage label on the agent's final action) |
| `pii_categories_covered` | drawn from U.S. privacy regulations + literature on vulnerable groups (health, finance, location, contact info, employment, family, sexual orientation, etc.). |
| `non_pii_sensitive_covered` | yes — explicitly designed around CI-style sensitive attributes that are not necessarily PII (medical condition, financial hardship, family history, mental health, etc.). |
| `essential_nonessential_partition` | no — PrivacyLens annotates whether disclosing a given attribute *to a specified recipient under a specified norm* is a privacy violation. The benchmark does not give, per task, the set of essential information vs non-essential sensitive information that should be retained vs suppressed in a rewritten query. |
| `utility_evaluation` | partial — agent task helpfulness is judged in addition to privacy leakage; both reported. |
| `privacy_metric` | leakage rate of the agent's final action (judge-based against the privacy norm). |
| `domain_coverage` | multi-domain — derived from 493 privacy-sensitive seeds spanning health, finance, family, employment, etc. |
| `language` | en |
| `size` | 493 privacy-sensitive seeds; expanded into vignettes and agent trajectories. |
| `intended_use` | evaluating privacy-norm awareness of LM agents in action. |
| `relation_to_us` | directly comparable (most closely shares the CI orientation and joint privacy/utility evaluation philosophy). |
| `gap_vs_our_setting` | (1) no per-sample E/N partition; (2) targets agent action leakage, not query rewriting in user→cloud setting; (3) utility is judge-based helpfulness, not task-grounded accuracy. |
| `notes` | This benchmark is the most natural external comparator on the joint axis "non-PII sensitive coverage + utility evaluation". |

---

## 8. CI-Bench

| field | value |
|---|---|
| `name` | CI-Bench |
| `paper_citation` | Cheng, Wan, Mukherjee, et al. (Google DeepMind) — "CI-Bench: Benchmarking Contextual Integrity of AI Assistants on Synthetic Data", arXiv 2024 |
| `paper_link` | https://arxiv.org/abs/2409.13903 |
| `repo_link` | `[TO VERIFY]` — no public release of the synthetic data was clearly indicated at the time of the arXiv version we located; check latest. |
| `release_year` | 2024 |
| `task_format` | tool-use / dialogue (assistants must decide whether to share user information with third-party tools/recipients given a CI norm) |
| `granularity` | sample-level (CI tuple) |
| `pii_categories_covered` | broad set of personal information types per CI taxonomy (medical, professional, family, calendar, etc.). |
| `non_pii_sensitive_covered` | yes — covers contextual sensitive attributes (health, finance, family, etc.). |
| `essential_nonessential_partition` | no — labels whether a specific information flow is appropriate; does not annotate per task essential vs non-essential split. |
| `utility_evaluation` | partial — joint evaluation includes task completion success when the model correctly shares only appropriate fields. |
| `privacy_metric` | accuracy on appropriate-vs-inappropriate flow decisions; rate of inappropriate disclosures. |
| `domain_coverage` | multi-domain (synthetic, spanning at least: healthcare, finance, work, family, calendar, social) |
| `language` | en |
| `size` | `[TO VERIFY]` — paper reports a large synthetic generation pipeline (thousands of scenarios). |
| `intended_use` | benchmarking AI assistants' CI-aware information-sharing decisions over synthetic but structured data. |
| `relation_to_us` | partial overlap |
| `gap_vs_our_setting` | (1) synthetic data only; (2) decision-level evaluation, not generation-level rewriting; (3) no E/N partition. |
| `notes` | A complementary comparator to PrivacyLens on the agent-decision side. |

---

## 9. ProPILE

| field | value |
|---|---|
| `name` | ProPILE |
| `paper_citation` | Kim, Yun, Lee, Gubri, Yoon, Oh — "ProPILE: Probing Privacy Leakage in Large Language Models", NeurIPS 2023 (Spotlight) |
| `paper_link` | https://arxiv.org/abs/2307.01881 ; https://proceedings.neurips.cc/paper_files/paper/2023/hash/420678bb4c8251ab30e765bc27c3b047-Abstract-Conference.html |
| `repo_link` | `[TO VERIFY official repo]` — paper-level project page on https://s-t-a-i.github.io/publication/siwon2023neurips/ |
| `release_year` | 2023 |
| `task_format` | attack/extraction (probing for PII leakage from pretrained / instruction-tuned LMs using user-supplied PII tuples) |
| `granularity` | attribute-type (probes ask whether the LM emits the rest of a PII tuple given a partial prompt) |
| `pii_categories_covered` | typical PII tuples (e.g. (name, email), (name, phone), (name, affiliation, address), etc.) drawn from Common Crawl–based pretraining data. |
| `non_pii_sensitive_covered` | no |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | no (probing tool, not utility-paired). |
| `privacy_metric` | likelihood of correct completion of held-out PII fields; black-box and white-box probing reconstruction rate. |
| `domain_coverage` | general web corpus |
| `language` | en (extends to other langs in some experiments — `[TO VERIFY]`) |
| `size` | not a fixed-size test set; users supply their own PII tuples. |
| `intended_use` | probing tool that lets data subjects test whether their PII can be reconstructed from an LM. |
| `relation_to_us` | complementary |
| `gap_vs_our_setting` | (1) attack tool, not a task benchmark; (2) PII-only; (3) no E/N partition. |
| `notes` | Logged here for completeness; also mirrored in `benchmarks_secondary.md` as attack/extraction. |

---

## 10. PrivQA (Chen et al., 2023)

| field | value |
|---|---|
| `name` | PrivQA |
| `paper_citation` | Chen, Mendes, Das, Xu, Ritter — "Can Language Models be Instructed to Protect Personal Information?", ICLR 2024 (preprint 2023) |
| `paper_link` | https://arxiv.org/abs/2310.02224 ; https://openreview.net/pdf?id=1vqHTUTod9 |
| `repo_link` | https://llm-access-control.github.io/ |
| `release_year` | 2023 (preprint) / 2024 (ICLR) |
| `task_format` | open QA + MCQ (the model is instructed to *withhold* certain personal-info categories about specific entities while answering text and image questions) |
| `granularity` | attribute-type (per protected category: nationality, occupation, residence, etc.) |
| `pii_categories_covered` | PERSON, NATIONALITY, RESIDENCE, OCCUPATION, FAMILY-RELATION, EDUCATION, etc. (Wikipedia / image-grounded) |
| `non_pii_sensitive_covered` | partial — includes attributes like family-relation, residence — these straddle PII vs sensitive-context. Health/finance/whereabouts (real-time) are not central. |
| `essential_nonessential_partition` | no — the instruction defines a *protected set* of attributes to withhold; what counts as "essential to the user's task" is implicit (the user's question itself) rather than annotated. |
| `utility_evaluation` | yes — utility is QA accuracy on non-protected questions; privacy is leakage rate on protected categories. The benchmark is explicitly designed to study the privacy/utility trade-off. |
| `privacy_metric` | leakage rate (refusal vs disclosure) on protected-attribute questions; QA accuracy on control questions. |
| `domain_coverage` | general (Wikipedia entities + images) |
| `language` | en |
| `size` | thousands of QA items across text and image modalities (`[TO VERIFY]` exact n in latest release). |
| `intended_use` | evaluating whether LMs can be instructed to withhold specified personal-information categories. |
| `relation_to_us` | partial overlap |
| `gap_vs_our_setting` | (1) categorical *withholding* rather than rewriting; (2) protected set is global per run, not per-sample E/N; (3) entity-centric (Wikipedia), not user-prompt rewriting. |
| `notes` | Closest existing benchmark that *jointly* evaluates utility and protection — but it does so via "withhold the whole category" rather than "preserve task-essential, suppress non-essential". |

---

## 11. PUPA (PAPILLON)

| field | value |
|---|---|
| `name` | PUPA — Private User Prompt Annotations |
| `paper_citation` | Siyan, Yadav, Khatri, Hill, McKeown, Hashemi, Potts, Zaharia, Singhvi — "PAPILLON: PrivAcy Preservation from Internet-based and Local Language Model Ensembles", NAACL 2025 |
| `paper_link` | https://arxiv.org/abs/2410.17127 ; https://aclanthology.org/2025.naacl-long.173/ |
| `repo_link` | https://github.com/Columbia-NLP-Lab/PAPILLON ; https://github.com/darshan-yadav/PAPILLON ; HF dataset card linked from the repo |
| `release_year` | 2024/2025 |
| `task_format` | prompt rewriting (small local LM rewrites a user prompt that contains PII into a privacy-preserving prompt for a powerful but untrusted remote LM). |
| `granularity` | sample-level (each item is a user prompt with PII span annotations + reference assistant response) |
| `pii_categories_covered` | PERSON, EMAIL, PHONE, ADDRESS, ID, ORG, DATE-OF-BIRTH, etc. — drawn from real WildChat / user-LLM logs. |
| `non_pii_sensitive_covered` | partial — because items are real user prompts, some include non-PII sensitive context (family info, health), but these are not labeled as a separate evaluable category; the benchmark's privacy metric counts PII leakage. |
| `essential_nonessential_partition` | no — PUPA labels PII spans within the prompt and provides a reference assistant response. There is no per-sample annotation of "context that must be preserved" vs "non-essential sensitive context". |
| `utility_evaluation` | yes — response quality vs the unprotected reference response is judged (LLM-judge pairwise / quality score). |
| `privacy_metric` | leakage = whether PII spans appear in the rewritten prompt sent to the remote LM (entity-level). |
| `domain_coverage` | general user prompts (mix of writing assistance, coding, advice, etc., from WildChat-style logs). |
| `language` | en (predominantly) |
| `size` | 901 user prompts containing PII (per published statistics). |
| `intended_use` | benchmark for local–remote LLM split that preserves response quality while reducing PII exposure. |
| `relation_to_us` | directly comparable (most direct baseline for our query-rewriting setting). |
| `gap_vs_our_setting` | (1) PII-only privacy metric, no non-PII sensitive coverage as a graded axis; (2) no E/N partition; (3) no domain-stratified medical/legal/finance challenge sets. |
| `notes` | This is the most direct comparator to our task definition. The "Prediax" name in guide §3.4 is `[TO VERIFY]` — we could not locate a paper of that exact name; it may refer to PrivacyRestore (Zhang et al., 2024) or to the framework name from a different paper. We logged what we did find; please confirm. |

---

## 12. PrivLM-Bench

| field | value |
|---|---|
| `name` | PrivLM-Bench |
| `paper_citation` | Li, Guo, Li, Fan, Hu, Liu, Chan, Yao, Yao, Song — "PrivLM-Bench: A Multi-level Privacy Evaluation Benchmark for Language Models", ACL 2024 |
| `paper_link` | https://arxiv.org/abs/2311.04044 ; https://aclanthology.org/2024.acl-long.4/ |
| `repo_link` | https://github.com/HKUST-KnowComp/PrivLM-Bench |
| `release_year` | 2023 (arXiv) / 2024 (ACL) |
| `task_format` | attack/extraction (membership inference, data extraction, embedding inversion against fine-tuned LMs) + downstream task (sentiment, NLI, etc.) |
| `granularity` | sample-level for tasks; attribute-/record-level for attacks. |
| `pii_categories_covered` | indirect — PII detected within Enron, GLUE-derived corpora; the benchmark is more about training-data leakage than explicit PII categories. |
| `non_pii_sensitive_covered` | no |
| `essential_nonessential_partition` | no |
| `utility_evaluation` | yes — downstream task accuracy is reported alongside privacy attacks (so the privacy/utility trade-off of DP fine-tuning can be plotted). |
| `privacy_metric` | MIA AUC; data extraction success rate; embedding inversion accuracy. |
| `domain_coverage` | general (GLUE-style + Enron) |
| `language` | en |
| `size` | multiple sub-tasks; total `[TO VERIFY]` |
| `intended_use` | unified benchmark for evaluating empirical privacy of fine-tuned / DP-fine-tuned LMs. |
| `relation_to_us` | complementary |
| `gap_vs_our_setting` | (1) training-data leakage focus, not user-prompt CI; (2) no E/N partition; (3) no non-PII sensitive context. |
| `notes` | Logged here because it is one of the most-cited "privacy benchmark for LMs" 2024 references; would otherwise be miscounted as a contextual benchmark. |

---

## End of main table.

Self-added candidates (beyond guide §3 list): **PrivLM-Bench, PrivQA, PUPA, CI-Bench**. Justification: they are the most-cited 2023–2024 benchmarks adjacent to our claim and must be on any reviewer's mental list.
