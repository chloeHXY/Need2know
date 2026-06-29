\section{Introduction}
\label{sec:intro}

Large language models (LLMs) are increasingly accessed as remote
services that users delegate everyday, professional, and high-stakes
tasks to~\citep{ouyang2022training,achiam2023gpt}.%
\footnote{Citations to be verified against the camera-ready bibliography.}
In practice, users rarely send only the minimal information required
to solve the task. A request for a recipe is accompanied by a
disclosed allergy; a request to draft an email is prefaced with the
user's medical condition, family situation, employer, or financial
state. Once such content leaves the local device, it is exposed to a
remote model whose retention, logging, and downstream use the user
cannot fully control~\citep{mireshghallah2024can,ngong2025contextual}.
Privacy-preserving delegation therefore must decide, on a
\emph{per-request} basis, which user information should be forwarded
as task context and which should not.

Recent work formulates this setting as
\textbf{privacy-conscious delegation}: a trusted local agent rewrites
the user's prompt before sending it to a stronger but potentially
untrusted remote LLM~\citep{siyan2024papillon}. The objective is not to
prevent remote access altogether, but to grant the remote model
\emph{enough} context to produce a high-quality answer while
withholding sensitive content that does not contribute to the task.
We retain this framing and ask a more basic question: what \emph{is}
the right disclosure target, and how should a benchmark measure
whether a delegation agent meets it?

\paragraph{Why PII-centric benchmarks are insufficient.}
Existing privacy benchmarks for LLMs are predominantly organized
around explicit personally identifiable information
(PII)~\citep{pilan2022text,lukas2023analyzing}. PII redaction conflates
two distinct decisions: whether a span is sensitive, and whether it
should be sent to the remote model for the current task. Consider the
same disclosure embedded in two requests:
\textit{(A) ``I'm allergic to peanuts. What snacks are safe for me to
bring on a hike?''}, versus
\textit{(B) ``I'm allergic to peanuts. Can you help me write a Python
script to rename files?''}
In (A), the allergy is the \emph{evidence} on which a useful answer
depends; redacting it silently degrades utility. In (B), the same
span is irrelevant to the task and forwarding it constitutes an
unnecessary disclosure. A faithful benchmark for delegation must
penalize \emph{both} failure modes---\textbf{over-disclosure}
(non-essential sensitive content reaches the remote LLM) and
\textbf{over-removal} (task-essential context is stripped)---which
PII-centric evaluations cannot separate.

\paragraph{Contextual integrity as the disclosure target.}
We ground the disclosure decision in
\textbf{contextual integrity} (CI)~\citep{nissenbaum2010privacy},
which holds that the appropriateness of an information flow is
determined by its context, not by an intrinsic ``sensitivity'' label.
Instantiated for delegation, CI yields a concrete criterion---
\emph{task necessity for remote assistance}: information should flow
to the remote LLM if and only if it is required to fulfill the user's
current request at acceptable quality. We operationalize this
criterion by annotating every request with two disjoint span sets:
the \textbf{task-essential} set
$\mathcal{E}$, whose removal demonstrably degrades the answer, and
the \textbf{task-non-essential sensitive} set
$\mathcal{N}$, which is disclosed by the user but should not be
forwarded. The $(\mathcal{E},\mathcal{N})$ partition is what makes
both over-disclosure and over-removal directly measurable.

\paragraph{A CI-grounded benchmark from three complementary
sources.}
Building such a benchmark requires labels that are simultaneously
controllable, distributionally realistic, and stress-tested in
domains where the privacy--utility tension is sharpest. We therefore
combine three sources. (i)~A \emph{reverse-synthesis} pipeline samples
a semantic skeleton---domain, task, subject, and the
$(\mathcal{E},\mathcal{N})$ partition---and renders it into a natural
prompt; an independent heterogeneous judge re-extracts the labels and
must agree with the sampler before a sample is admitted, yielding
labels that are correct \emph{by construction}.
(ii)~A \emph{natural anchor} curated from real
WildChat~\citep{zhao2024wildchat} prompts verifies that the same
$(\mathcal{E},\mathcal{N})$ protocol applies to organic user
language. (iii)~A \emph{medical challenge} split targets the
hardest case for delegation, where symptoms, medications, and
history are simultaneously highly sensitive and answer-bearing,
making over-removal a first-class failure mode.

\paragraph{From annotation to training signal.}
Because $\mathcal{E}$ and $\mathcal{N}$ are span-level and disjoint,
they double as a supervision signal: we train a local delegation
agent that is rewarded for preserving $\mathcal{E}$ in its rewritten
prompt and penalized for leaking $\mathcal{N}$ to the remote LLM.
The agent therefore does not learn a fixed list of sensitive
categories; it learns that the same kind of information should be
kept in some contexts and suppressed in others.

\paragraph{Findings.}
On both general-domain and medical splits, the CI-trained agent
attains a more favorable privacy--utility trade-off than PII
redaction and prior rewriting/delegation baselines, reducing
non-essential disclosure without sacrificing answer quality. The
medical split is the most informative: there, redaction-style
defenses appear to ``protect'' the user but in fact suppress
answer-bearing evidence, illustrating that explicit modeling of
$(\mathcal{E},\mathcal{N})$ is necessary, not optional, for
privacy-conscious delegation.

\paragraph{Contributions.}
\begin{itemize}
    \item We \textbf{reformalize privacy-conscious delegation under
    contextual integrity}, replacing PII-style sensitivity labels with
    a per-request criterion of task necessity for remote assistance.
    \item We release a \textbf{CI-grounded benchmark} in which every
    request is annotated with disjoint task-essential
    ($\mathcal{E}$) and task-non-essential sensitive ($\mathcal{N}$)
    spans, enabling joint evaluation of \emph{over-disclosure} and
    \emph{over-removal}---failure modes that PII-centric benchmarks
    cannot distinguish.
    \item We build the benchmark from \textbf{three complementary
    sources}: a reverse-synthesis pipeline with construction-time
    label agreement, a natural WildChat anchor for distributional
    grounding, and a medical challenge split that targets
    answer-bearing sensitive evidence.
    \item We use the $(\mathcal{E},\mathcal{N})$ annotations as
    \textbf{optimization signals} to train a local delegation agent,
    and show empirically that it improves the privacy--utility
    trade-off over PII redaction and prior delegation baselines,
    most notably on the over-removal-sensitive medical split.
\end{itemize}
