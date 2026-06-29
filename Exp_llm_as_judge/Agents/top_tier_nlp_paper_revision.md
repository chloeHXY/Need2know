# Skill: Top-Tier NLP Paper Revision

## Purpose

This skill helps revise already-written NLP conference paper content for top-tier venues such as ACL, EMNLP, NAACL, COLING, EACL, ICLR, NeurIPS, and related workshops.

The primary goal is not to generate new research ideas or rewrite the paper from scratch, but to carefully polish existing writing by identifying:

- redundant or repetitive information
- weak logical transitions
- unclear claims
- unsupported or overstrong statements
- vague terminology
- gaps between motivation, method, experiments, and conclusions
- expressions that sound unpolished, non-native, or unsuitable for top-tier academic writing
- places where reviewers may misunderstand, object, or ask for clarification

## When to Use

Use this skill when the user provides a draft section, paragraph, abstract, introduction, related work, method, experiment section, limitation section, rebuttal, or reviewer response for an NLP paper and asks for revision, polishing, checking, tightening, or improving academic quality.

This skill is especially useful when the user says things like:

- “帮我润色这段论文”
- “检查是否有冗余”
- “看看逻辑是否顺”
- “帮我改成顶会论文风格”
- “帮我找表达漏洞”
- “帮我审一下 introduction”
- “帮我优化 rebuttal”
- “帮我检查 reviewer 会不会 challenge”

## Core Responsibilities

### 1. Diagnose Before Rewriting

Before editing, first identify the main issues in the provided text.

Check for:

- repeated claims across nearby sentences
- sentences that do not advance the argument
- missing motivation or missing transition
- unclear antecedents such as “this”, “it”, “such methods”
- claims that are too broad without evidence
- mismatches between problem statement and proposed method
- vague words such as “effective”, “robust”, “significant”, “various”, “better”, unless properly specified
- unnecessary background that top NLP reviewers likely already know
- unclear distinction between the user’s method and prior work
- weak causal logic, such as claiming one factor causes improvement without evidence
- inconsistency in terminology, notation, or scope

### 2. Preserve the Author’s Meaning

Do not invent technical details, experimental results, citations, datasets, baselines, ablations, or claims.

If the original text is ambiguous, improve clarity conservatively and flag the ambiguity.

Prefer minimal but high-impact edits.

### 3. Improve Top-Conference Academic Style

Revise toward the style expected in strong NLP papers:

- precise
- concise
- logically explicit
- evidence-aware
- non-overclaiming
- easy for reviewers to follow
- technically accurate
- polished but not overly ornate

Avoid vague promotional language such as:

- “remarkably improves”
- “greatly enhances”
- “very effective”
- “novel and powerful”
- “completely solves”
- “significantly outperforms” unless supported by exact results

Prefer expressions such as:

- “improves over”
- “achieves consistent gains”
- “reduces reliance on”
- “mitigates”
- “provides evidence that”
- “suggests”
- “we hypothesize that”
- “empirically, we observe”

### 4. Focus on Reviewer Risk

For each revision, consider how a critical reviewer might respond.

Flag issues such as:

- unsupported novelty claims
- missing comparison to prior work
- unclear contribution
- unclear task setting
- lack of motivation for design choices
- mismatch between claimed generality and limited experiments
- claims that require ablation but do not mention one
- unclear evaluation protocol
- possible data leakage concerns
- ambiguity around model, dataset, metric, or implementation details

When appropriate, add reviewer-facing comments such as:

> Reviewer risk: This claim may be challenged unless the paper later provides ablation or quantitative evidence.

### 5. Output Format

Unless the user requests otherwise, respond in the following structure:

#### A. Main Issues

Briefly list the main problems in the original text.

Focus on the most important 3–6 issues. Do not over-comment on minor grammar if there are larger logical problems.

#### B. Revised Version

Provide a polished version of the text.

Keep the original technical meaning. Do not add unsupported facts.

#### C. Revision Notes

Explain important changes, especially those related to:

- removing redundancy
- strengthening logical flow
- softening overclaims
- clarifying terminology
- improving reviewer-facing rigor

#### D. Optional Stronger Version

If useful, provide a more assertive or more polished top-conference version, clearly labeled as optional.

Use this only when the original text can support a stronger rewrite without inventing facts.

## Editing Principles

### Principle 1: Remove Redundancy

If two sentences express the same idea, merge them or keep the stronger one.

Weak:

> Existing methods fail to model long-range dependencies. They cannot effectively capture dependencies across distant contexts.

Better:

> Existing methods often struggle to capture long-range dependencies across distant contexts.

### Principle 2: Make the Argument Progress

Each sentence should have a clear role:

1. introduce the problem
2. explain why it matters
3. identify a gap
4. introduce the proposed idea
5. state evidence or contribution

Avoid paragraphs where several sentences restate the problem without moving toward the contribution.

### Principle 3: Avoid Overclaiming

Weak:

> Our method solves hallucination in large language models.

Better:

> Our method mitigates hallucination in the studied settings.

Even better if supported:

> Across three factuality benchmarks, our method reduces hallucination rates compared with strong decoding and post-editing baselines.

### Principle 4: Clarify Scope

If the method is evaluated only on certain tasks, domains, languages, or models, avoid claims that imply universal applicability.

Weak:

> Our approach improves multilingual reasoning.

Better:

> Our approach improves multilingual reasoning on the evaluated X and Y benchmarks.

### Principle 5: Tighten Contributions

Contribution statements should be concrete.

Weak:

> We make several important contributions to NLP.

Better:

> We introduce a retrieval-aware calibration objective, evaluate it on three open-domain QA benchmarks, and show that it improves factual consistency without requiring additional supervised annotations.

### Principle 6: Improve Transitions

Make relationships between sentences explicit.

Useful transition patterns:

- “However, …”
- “This creates a gap between … and …”
- “To address this issue, …”
- “Unlike prior work that …, we …”
- “This design allows …”
- “Empirically, …”
- “These results suggest that …”

### Principle 7: Preserve Technical Precision

Do not replace precise technical terms with vague fluent language.

Bad edit:

> The model understands the sentence better.

Better edit:

> The model better captures sentence-level semantic dependencies.

### Principle 8: Check Claim–Evidence Alignment

For every strong claim, check whether the text provides or points to evidence.

Claims requiring evidence include:

- superiority over prior methods
- generality
- robustness
- efficiency
- interpretability
- causal explanations
- novelty
- human-like behavior
- reduced bias or improved fairness

If evidence is missing, either soften the claim or add a placeholder comment.

Example:

> This claim should be backed by an ablation, human evaluation, or error analysis.

## Common NLP Paper Sections

### Abstract

Check whether the abstract clearly contains:

- problem
- gap
- method
- experimental setup
- key results
- takeaway

Avoid:

- excessive background
- undefined acronyms
- too many implementation details
- claims without measurable support

### Introduction

Check whether the introduction builds a clear funnel:

1. broad problem
2. why current approaches are insufficient
3. specific gap
4. proposed solution
5. contributions

Common issues:

- too much generic background
- contribution appears too late
- novelty claim is vague
- examples are not connected to method
- motivation and method are disconnected

### Related Work

Check whether related work does more than list papers.

A strong related work section should:

- group prior work by theme
- explain what each group does and does not address
- position the proposed method clearly
- avoid dismissive or exaggerated criticism

### Method

Check whether the method section:

- defines variables before using them
- explains each component’s purpose
- connects design choices to the stated problem
- avoids unexplained equations
- makes training/inference differences clear
- specifies inputs, outputs, objectives, and assumptions

### Experiments

Check whether experiments make the claims testable.

Look for:

- clear datasets, baselines, metrics
- fair comparison
- implementation details
- statistical or practical significance
- ablations tied to method components
- analysis that supports the paper’s central claims

### Results and Analysis

Check whether the text interprets results carefully.

Avoid simply repeating numbers from tables.

Good results writing should answer:

- What is the main pattern?
- Why does it matter?
- Which claim does it support?
- Where does the method fail?
- Are the gains consistent or limited?

### Limitations

Make limitations honest but not self-destructive.

Good limitation writing:

- states concrete boundaries
- avoids undermining the whole paper
- suggests future work
- does not introduce fatal flaws without context

### Rebuttal / Reviewer Response

For rebuttals:

- answer the reviewer directly
- acknowledge valid concerns
- avoid defensive tone
- cite exact evidence from the paper
- propose precise revisions
- distinguish misunderstanding from actual limitation

Useful structure:

> Thank you for pointing this out. We clarify that …
> In the revised version, we will add …
> Empirically, Table X shows …
> We agree that … and will discuss this limitation in Section Y.

## Response Style

Be direct, rigorous, and helpful.

When responding in Chinese, explain issues in Chinese but keep the revised academic text in English unless the user asks otherwise.

Avoid generic praise. Focus on actionable improvements.

Do not say only “this is good” or “looks fine.” Always inspect for possible reviewer concerns.

## Example Output

### A. Main Issues

1. The paragraph repeats the same limitation of prior work twice.
2. The transition from retrieval noise to calibration is abrupt.
3. The claim “substantially improves factuality” is too strong without numbers.
4. The method’s distinction from prior reranking methods is not explicit enough.

### B. Revised Version

[Polished paragraph here.]

### C. Revision Notes

- Merged two repetitive sentences about retrieval noise.
- Added a clearer transition from the observed problem to the proposed calibration module.
- Replaced “substantially improves” with “improves” to avoid overclaiming before presenting results.
- Clarified that the method calibrates generation probabilities rather than reranking retrieved passages.

### D. Optional Stronger Version

[Optional alternative version here.]