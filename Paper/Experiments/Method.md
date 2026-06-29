# Method

In this section, we formalize the privacy-preserving query rewriting task as a
reinforcement learning (RL) problem (\S\ref{sec:framework}), present a composite
reward that jointly enforces non-essential privacy non-disclosure and task utility
(\S\ref{sec:reward}), and describe the on-policy training procedure based on
Group Relative Policy Optimization (GRPO) (\S\ref{sec:policy}).

## Framework Overview

**Problem setup.** Given a user query x, which may contain both information necessary to complete the task and sensitive information unrelated to the task, the policy model \pi_\theta generates a rewritten query y \sim \pi_\theta(\cdot \mid x). This rewritten query is forwarded to an external untrusted retriever or a remote LLM. The optimization objective is to retain as much of the information required to complete the original task as possible while minimizing the leakage of unnecessary sensitive information.

**Pipeline.** At inference time, the rewritten query $y$ is sent to an
untrustworthy external Large Language Models; the retrieved evidence is then recombined with the
original $x$ on the trusted side to produce the final answer. Our scope is
limited to learning $\pi_\theta$ that produces $y$; the downstream answerer is
frozen and is not part of the optimization loop.

## Reward Design

The reward is designed to jointly enforce three properties: (i) penalize the
disclosure of non-essential information in the rewritten query, (ii) reward
the preservation of task-essential content, and (iii) discourage verbosity avoid reward hacking.

**Notation.** Given an input
query $x$, a rewritten query $y$, the set of
*essential* spans $\mathcal{E}=\{e_i\}_{i=1}^{n}$ and the set of *non-essential* spans  $\mathcal{N}=\{c_j\}_{j=1}^{K}$. For two strings $a, b$, define the token-level Jaccard coverage
$$\mathrm{cov}(a, b) \;=\; \frac{|T(a) \cap T(b)|}{|T(b)|},$$
where $T(\cdot)$ is the lowercased, stop-word-filtered, alphanumeric token
multiset. Let $P_{\text{r}}(a, b) \in (-\infty, 1]$ denote the rescaled
BERTScore precision [TO VERIFY: cite Zhang et al., 2020] computed with a
`roberta-large` backbone.

**Privacy reward $R_{\text{priv}}$.** A rewrite is considered inadmissible if it contains any non-essential sensitive span. For each
$c \in \mathcal{N}$ we discard $c$ if it lexically overlaps with any span in
$\mathcal{E}$. For the remaining $\mathcal{N}^\prime \subseteq \mathcal{N}$, leakage is
declared whenever either lexical or semantic disclosure exceeds its threshold:
$$R_{\text{priv}}(y) \;=\;
\begin{cases}
-1, & \exists\, c \in \mathcal{N}^\prime:\; \mathrm{cov}(y, c) \geq 1.0 \;\;\lor\;\; P_{\text{r}}(y, c) > \tau_{\text{priv}},\\
\phantom{-}0, & \text{otherwise},
\end{cases}$$
with $\tau_{\text{priv}} = 0.3$. An empty output is also assigned $R_{\text{priv}} = -1$
to prevent the policy from trivially evading the constraint by emitting
nothing. Because $R_{\text{priv}}(y) = -1$ saturates the lower bound of $R$,
any leakage strictly dominates the contribution of the other terms.

**Essential-preservation reward.** Conditional on $R_{\text{priv}}(y) = 0$,
$R_{\text{ess}}$ measures how much of $\mathcal{E}$ is retained by $y$. Let
$$\rho(y) \;=\; \frac{1}{|\mathcal{E}|}\sum_{e \in \mathcal{E}} \phi(y, e)
\;\in\; [0, 1]$$
be the fraction of essential spans recovered by $y$. We use a smoothed
recall
$$R_{\text{ess}}(y) \;=\; \rho(y)^{\,\gamma},\qquad \gamma = 0.4,$$
which gives partial credit to outputs
that preserve some essential information while still favoring complete
preservation.

**Length penalty.** To prevent the policy from inflating $\rho(y)$ by simply
copying long stretches of the input, we apply a brevity factor
$$L_{\text{brev}}(y) \;=\; \min\!\Bigl(1,\; \frac{\alpha\,|x|}{|y|}\Bigr)
\;\in\; (0, 1],\qquad \alpha = 0.5,$$
This factor is $1$ when $y$ is no longer than the target length, and decays
for overly long rewrites. Since it is multiplicative, it can only reduce the
utility reward and cannot compensate for missing essential information.

**Final reward.** Combining the three terms, the final reward is
$${\;R(y) \;=\;
\begin{cases}
-1, & R_{\text{priv}}(y) = -1, \\[4pt]
\rho(y)^{\,\gamma}\;\cdot\;L_{\text{brev}}(y), & R_{\text{priv}}(y) = 0.
\end{cases}\;}$$
This design makes privacy a hard constraint: any non-essential disclosure
receives the minimum reward. The policy is rewarded for retaining task-essential information while avoiding unnecessarily verbose outputs. The smoothed recall term provides graded rewards, which is
important for producing within-group reward variance under GRPO.

## Policy Training

We optimize $\pi_\theta$ with GRPO using reward $R(y)$. For each query
$(x)$ we draw $G$ rollouts $\{y_i\}_{i=1}^{G}$ from $\pi_\theta$ and compute
their rewards $\{R_i\}_{i=1}^{G}$. The group-relative advantage is
$$\hat A_i =\frac{R_i - \text{mean}(\{R_j\}_{j=1}^G)}{\text{std}(\{R_j\}_{j=1}^G)+\epsilon}$$
The objective function of GRPO is:
$$
\mathcal{L}_{\text{GRPO}}=-\mathbb{E}_{x, \{y_i\}}\left[\sum_{i=1}^{G}A_i\log \pi_\theta(y_i \mid x)-\beta D_{\mathrm{KL}}(\pi_\theta || \pi_{\text{ref}})\right]
$$