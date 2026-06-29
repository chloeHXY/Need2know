# Open Questions / Boundary decisions for the author

> 调研过程中发现的不确定点、相互矛盾的描述、需要作者决策的边界问题。
> 列得有点多 —— 按指南 §5.5 要求 "不要怕多"。

---

## Q1. `Prediax` baseline 的归属

Guide §3.4 列出 `Prediax` 作为我们论文中的 baseline。我没有在 arXiv / Google Scholar / Semantic Scholar 中检索到一篇名为 **Prediax** 的论文。最接近的命中是：

- **PrivacyRestore** (Zhang et al., arXiv 2406.01394, 2024)：privacy-preserving inference framework；
- **Pr$\epsilon\epsilon$mpt / Preempt** (NDSS 2026)：cryptographic prompt sanitization；
- **Priv-QA / Priv-IQ**（多个不同作者）。

**请确认**：`Prediax` 是否是上述某项的内部代号 / 拼写笔误？如果不是，请提供原文标题或链接，我据此补回主表。

---

## Q2. `Ngong2025` 是 dataset paper 还是 methodology paper？

Guide §9.2 明确警告这一点。我目前的判断（基于 arXiv 2502.18509 与 ACL Findings 2025 接收页面）：

- 它本质是 **methodology + framework** + **以 ShareGPT 为评测substrate 的小规模评测**。
- 我未能确认作者是否发布了**带 per-sample 标签**的可下载评测集；OpenReview 页面提到了"使用 ShareGPT 的样本进行评测"，但未明示 release artifact。

**请决策**：
- (a) 把它作为"taxonomy/methodology paper"对待，主表 `essential_nonessential_partition = no`；或
- (b) 视它已 release 的 artifact（若你确认存在）升级为 `implicit`。

我目前选了 (b) 并标 `[TO VERIFY]`。

---

## Q3. ConfAIde Tier 4 是否构成 implicit E/N 划分？

ConfAIde Tier 4 给出"会议脚本 + 一条秘密"，要求 LLM 在生成 summary 时不要泄露秘密。这隐含了 "summary 内容 = essential" / "secret = non-essential" 的结构，但：

- 数据集**未为每个样本提供 token/span 级别的"essential"集合**；
- "essential" 的范围由"任务是 summary"这一隐含约束决定；不是显式标注。

我把它记为 `essential_nonessential_partition = no`。**请确认**这一判断与你 paper 中 C1 的措辞是否一致。如果你想表达"ConfAIde 至少在 Tier 4 隐含一种二元划分"，我可以改成 `~` / `implicit`。

---

## Q4. WikiPII 的"权威版本"

我没有找到一个唯一的"WikiPII"数据集卡片。检索到的有：

- 引用自 Lison et al. ACL 2021 中针对 Wikipedia 传记的 sanitization 评测；
- 多个 GitHub 上的非官方 derivative。

**请确认**你 paper 想引用的是哪一个；当前主表用 `[TO VERIFY]` 占位。

---

## Q5. `relation_to_us` 字段中的 "directly comparable" 边界

我把以下记为 directly comparable：`ConfAIde`, `Ngong2025`, `PrivacyLens`, `PUPA`。理由：

- 前三者都是 CI 风格 + 含某种 utility 评估；
- `PUPA` 是与本论文最直接的 query-rewriting + utility-pair benchmark。

但 `PrivacyLens` 评估的是 **agent action**，不是 query rewriting；严格说与我们任务并非完全可比。**请决定**是否要把 PrivacyLens 降为 `partial overlap`。

---

## Q6. 是否要把 `WildChat` 列入

`WildChat`（Allen AI, ICLR 2024）是百万级真实对话日志，本身**不是隐私 benchmark**，但它是 PUPA 的源头数据，并经常被 privacy 研究当评测substrate。

我**没有**把它列入任何表，因为它没有 privacy 标签。**请确认**你是否需要它作为 raw substrate 出现在 paper 的 related work（不是对比表）。

---

## Q7. 医疗 / 金融 / 法律对照表的"对照价值"

Guide §3.5 要求收医疗、金融、法律领域中带 sensitive attribute 的对话数据集。当前我只找到：

- 医疗：`i2b2/n2c2 2014` (PHI only)、`MIMIC-III/IV`（substrate）；
- 法律：`TAB`（合规性来源）、`LegalBench`（不是隐私 benchmark）；
- 金融：**没有找到**带 sensitive-attribute 标注的 LLM 对话评测集。

**请决策**是否：
- (a) 接受"金融领域目前没有标准对照"作为 paper 的事实陈述；
- (b) 让我再花半天搜 finance domain 特化的工作（例如银行业对话 NER）。

---

## Q8. Carlini / lm-extraction-benchmark 的归类

我把它们都归到 `attack/extraction`，写在副表 §A 中。**请确认**：

- Paper 是否需要在主表也提及它们以建立"PII leakage 类 benchmark 全景"？
- 还是按 guide §4 的"attack 评测归副表"原则保持现状？

---

## Q9. ProPILE 主表 vs 副表的重复登记

ProPILE 既是"PII benchmark"又是"attack tool"。Guide §4 说 `task_format = attack/extraction` 应放副表。我目前**双登**：主表保留以保持完整性，副表 §A.4 只指回主表。**请确认**这种处理可以接受。

---

## Q10. "domain_coverage" 字段的判断标准

Multi-domain ≥ 3 我按以下解释：

- "domain" 指**任务/语料领域**（医疗、法律、金融、客服…），而非"话题词"；
- ConfAIde Tier 1–3 都是合成场景，不算 ≥3 实际领域；
- PrivacyLens 的 493 seed 横跨健康/财务/家庭/工作，算作 multi-domain。

**请确认**这个判断口径合你意。

---

## Q11. `pii_categories_covered` 字段的统一性

不同 benchmark 用不同的 PII 命名体系（HIPAA-PHI 18 类 vs spaCy NER 18 类 vs OntoNotes 18 类 vs ad-hoc）。我没有统一映射，主表里直接抄各自的术语。**请确认**是否需要我做一张"category 对齐表"，把它们映射到本论文使用的 PII taxonomy。

---

## Q12. 是否需要对 ConfAIde 的 Tier 1–4 拆成 4 行？

ConfAIde Tier 1–4 任务形态完全不同。当前主表是"一个 ConfAIde 一行"。**请决策**：

- (a) 保持单行（更紧凑，便于 paper 表格）；
- (b) 拆 4 行（更精确，但表格变长）。

---

## Q13. 副表中 `[TO VERIFY]` 数量较多

我对以下副表条目的字段不能完全核到原文：`Priv-IQ`, `Priv-QA (Wang 2025)`, `PrivAuditor`, `Preempt`, `PrivacyRestore` 的具体数据规模与代码 link。**请决定**是否需要我深挖这些条目（每个再花 1–2 小时），还是仅作为 "存在该方向" 的占位即可。

---

## Q14. 是否需要 CSV 副本

guide §5 提到 `.csv` 或 `.md` 任一即可。我交付的是 `.md` 表格（更适合直接放 paper appendix）。**请确认**你不需要 CSV 二进制副本，否则我用 pandas 再生成一份。

---

## Q15. 论文已引用文献覆盖核对

guide §8 第一项要求 5 个已引用文献被处理。我覆盖了：

- `pilan2022text` → 主表 #1 (TAB)
- `lukas2023analyzing` → 主表 #4
- `mireshghallah2024can` → 主表 #5 (ConfAIde)
- `ngong2025contextual` → 主表 #6

**未处理：**

- `nissenbaum2010privacy` —— 这是 Helen Nissenbaum 的 *Privacy in Context* 专著，**不是 benchmark**，不进表。但 paper 在 §3 引用它作为理论基石。

**请确认**：`nissenbaum2010privacy` 不进任何表是符合预期的处理。
