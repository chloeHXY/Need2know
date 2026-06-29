# Introduction 中文整理稿

## 0. Introduction 的核心任务

本文 Introduction 需要完成的不是泛泛介绍 LLM 隐私风险，而是建立一条清晰论证链：随着用户把任务委托给远程强模型，隐私保护的关键不再只是检测 PII，而是判断哪些用户信息应当作为任务上下文流向远程 LLM。现有 benchmark 主要围绕 PII 泄漏，无法系统评测 Privacy-Conscious Delegation 中的两类核心失败：不必要披露（over-disclosure）和过度删除（over-removal）。因此，本文基于 Contextual Integrity 构造显式区分 task-essential 与 task-non-essential 信息的 benchmark，并进一步将该标注转化为训练本地委托代理的信号。

---

## 1. 推荐叙事结构

| 段落 | 功能 | 核心问题 |
|---|---|---|
| Para 1 | 引入系统场景 | 为什么远程 LLM 委托会带来新的隐私问题？ |
| Para 2 | 定义任务 | 什么是 Privacy-Conscious Delegation？ |
| Para 3 | 说明现有 benchmark 不足 | 为什么 PII-centric benchmark 不够？ |
| Para 4 | 给出理论 framing | 为什么需要 Contextual Integrity？ |
| Para 5 | 定义 benchmark 标签 | 什么是 `E/N` 分区？ |
| Para 6 | 概述数据与方法 | 我们如何构造 benchmark，并如何利用它训练？ |
| Para 7 | 摘要实验发现 | 结果说明了什么？ |
| Para 8 | 列贡献 | 本文贡献是什么？ |

---

## 2. 中文 Introduction 草稿

大型语言模型正在成为用户完成日常任务、专业咨询和复杂推理的重要入口。为了获得更强的任务求解能力，用户往往需要把请求委托给能力更强的远程模型。然而，真实用户请求很少只包含完成任务所需的最小信息。用户常常在提问时顺带披露疾病、用药、家庭关系、财务压力、住址、身份背景或第三方信息。这些信息一旦随原始 query 发送给远程 LLM，就可能造成不必要的隐私暴露。

本文研究 **Privacy-Conscious Delegation**：一个可信本地代理在把用户请求委托给能力更强、但潜在不可信的远程 LLM 之前，需要选择性决定哪些信息可以被披露，哪些信息应被删除或泛化。这个任务的目标不是简单阻断远程模型访问用户信息，而是在隐私保护和任务支持之间做上下文决策：远程 LLM 应获得足够信息来高质量完成用户任务，但不应接收与任务无关的敏感个人披露。

要系统研究这一问题，首先需要看到隐私披露决策本身是高度上下文依赖的。例如，考虑同一条敏感信息在两个请求中的作用：

A: “I’m allergic to peanuts. What snacks are safe for me to bring on a hike?”
B: “I’m allergic to peanuts, but can you help me write a Python script to rename files?”

在 A 中，用户的花生过敏信息是任务求解所必需的上下文；如果本地代理删除这条信息，远程 LLM 将无法给出安全、有用的零食建议。相反，在 B 中，同一条过敏信息与文件重命名脚本无关；将其发送给远程 LLM 只会造成不必要的敏感披露。这个简单例子说明，Privacy-Conscious Delegation 的核心问题不是判断某个 span 是否属于 PII 或敏感信息，而是判断它在当前任务中是否应当流向远程 LLM。

这个缺口表明，隐私保护委托不能被充分理解为 PII redaction 问题。关键不在于某个 span 是否属于 PII，也不只在于它是否敏感，而在于它是否应该作为任务解决的关键上下文流向一个潜在不可信的远程 LLM。本文采用 Contextual Integrity 作为理论基础，是因为 CI 恰好提供了判断“什么信息在什么任务下可以被披露给谁”的规范框架。在我们的场景中，这一规范被具体化为 **task necessity for remote assistance**：如果某条信息是远程模型提供有效任务支持所必需的，它应被保留并随委托请求发送；如果它虽然敏感但对任务无实质帮助，则应在委托前删除或泛化。

基于这一 framing，我们将每个用户请求标注为两个互补集合：task-essential spans \(\mathcal{E}\) 和 task-non-essential sensitive spans \(\mathcal{N}\)。\(\mathcal{E}\) 表示虽然可能敏感、但删除后会削弱任务完成质量的信息；\(\mathcal{N}\) 表示用户在请求中披露了、但不应继续发送给远程 LLM 的敏感信息。这个分区使 benchmark 能同时评测两类 CI 失败：over-disclosure，即 \(\mathcal{N}\) 被不必要地暴露给远程模型；over-removal，即 \(\mathcal{E}\) 被过度删除，导致远程模型无法提供有效支持。

我们据此构造一个 CI-grounded benchmark。该 benchmark 包含三类互补数据。第一，通用场景数据通过反向合成获得：我们先采样 domain、task、subject、敏感属性以及 \(\mathcal{E}/\mathcal{N}\) 分区，再让生成模型将这一语义骨架渲染为自然用户 query，并通过独立 judge 重新抽取标签以进行一致性过滤。第二，我们引入真实 WildChat 用户请求作为锚点，检验同一套标注协议是否适用于自然语言分布，并作为合成数据之外的 OOD probe。第三，我们构造医学挑战集，专门测试 over-removal：医学信息高度敏感，但症状、病史、检查结果和用药往往也是答案所依赖的关键证据。

这个 benchmark 不仅用于评测，也提供了可操作的训练信号。基于显式的 \(\mathcal{E}/\mathcal{N}\) 标注，我们训练本地委托代理在重写用户请求时惩罚 task-non-essential 敏感信息泄漏，同时奖励 task-essential 上下文保留。由此，模型学习的不是固定的 PII masking 规则，而是在具体任务情境下决定哪些内容应随委托请求发送给远程 LLM：同一类敏感信息在某些任务中应被保留，在另一些任务中应被抑制。

实验在通用场景和医学挑战集上评估 privacy--utility trade-off。结果表明，相比传统 PII redaction 和已有 query rewriting / delegation baseline，基于 CI 的委托代理能够更好地降低不必要敏感披露，同时保留支持任务完成的关键信息。尤其在医学场景中，敏感信息往往同时是 answer-bearing evidence；该结果说明，仅追求删除敏感内容会造成隐蔽的任务失败，而显式建模 task-essential 与 task-non-essential 信息对于 Privacy-Conscious Delegation 是必要的。

---

## 3. 贡献列表中文版本

本文贡献可以概括为四点：

1. **问题重构。** 我们将 Privacy-Conscious Delegation 重新刻画为面向远程 LLM 的上下文披露控制问题。基于 Contextual Integrity，我们不再按某段内容是否属于 PII 或敏感类型来判断是否披露，而是按它是否应作为任务解决的关键上下文发送给远程 LLM 来判断。

2. **CI-grounded benchmark。** 我们构建了一个面向 Privacy-Conscious Delegation 的 CI-grounded benchmark，每个样本显式标注 task-essential spans \(\mathcal{E}\) 和 task-non-essential sensitive spans \(\mathcal{N}\)，从而能够同时评测 over-disclosure 与 over-removal。

3. **互补数据构造。** 该 benchmark 结合反向合成的通用场景数据、真实 WildChat 用户请求锚点和医学挑战集。反向合成保证覆盖与标签可控，真实锚点检验自然分布泛化，医学集专门测试敏感信息同时作为答案证据时的过度删除问题。

4. **训练与实证验证。** 我们将 \(\mathcal{E}/\mathcal{N}\) 标注转化为本地委托代理的优化信号，惩罚不必要披露并奖励任务必要信息保留。实验显示，该代理相比 PII redaction 和已有 delegation / rewriting baseline 获得更好的 privacy--utility trade-off，尤其缓解医学场景中的 over-removal。

---

## 4. 可翻译成英文的 contribution bullets

```latex
Our contributions are as follows:

\begin{itemize}
    \item We ground Privacy-Conscious Delegation in Contextual Integrity, reframing privacy protection as contextual disclosure control rather than PII redaction. In this setting, the key question is whether a span should be sent to the remote LLM as task-solving context.

    \item We introduce a CI-grounded benchmark with explicit $\mathcal{E}/\mathcal{N}$ annotations, separating task-essential spans that should be preserved from task-non-essential sensitive spans that should be suppressed. This enables direct evaluation of both over-disclosure and over-removal.

    \item We construct the benchmark from three complementary sources: reverse-synthesized general-domain queries for controllable coverage, natural WildChat anchors for distributional grounding, and a medical challenge split targeting cases where sensitive information is also answer-bearing.

    \item We train a local delegation agent using these annotations as optimization signals, and show that it improves the privacy--utility trade-off over PII redaction and prior delegation / rewriting baselines, especially on over-removal-sensitive medical queries.
\end{itemize}
```

---

## 5. 写作注意点

- 不要写成“我们提出 Privacy-Conscious Delegation”这样的强 claim，因为 PUPA/PAPILLON 已经提出该任务。更准确的说法是：我们将 Privacy-Conscious Delegation 基于 Contextual Integrity 重新形式化。
- 不要说“没有 Privacy-Conscious Delegation benchmark”，因为 PUPA 存在。更稳的说法是：据我们所知，尚无公开 benchmark 在该场景下以 CI 语境下的任务必要披露为核心，并显式标注 task-essential 与 task-non-essential 敏感信息。
- 不要把贡献写成“我们有 3,167 条数据”。数据规模可以在 Data 或 Experiments 中报告，Introduction 中更重要的是说明数据的理论功能和评测能力。
- 不要只强调降低泄漏。本文真正的主张是：隐私保护委托必须同时避免 over-disclosure 和 over-removal。
- `rewriter` 最好作为实现机制出现，顶层问题定义应使用 `Privacy-Conscious Delegation` 或 `delegation agent`。
