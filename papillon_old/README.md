
# `papillon_old/` 目录说明

> **状态：已弃用 / 历史快照（5/16–5/18）。新工作请直接用 [`papillon/`](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/README.md)。**

这是 PAPILLON 流水线的 **最初版本**。当时整个测试集只考虑 `ability == "privacy"` 一种情形，因此：

- `step3_aggregator.py` 没有 Med 选项字母保留逻辑、`MAX_WORKERS=8`、模型默认 `llama_inference`；
- `step4_1_eval.py` 只在 `ability == "privacy"` 走 Q_AL pairwise，**没有 wild、Med 走法和现版略有不同**；
- 没有 `step5_anoy.py`（也就没有 5_qwen / 5_llama / 5_ds 这套 PII 打标产物）；
- 没有 qwen523 / qwen7b 的产出对照，只有 llama_inference 这一套 priv_query。

> 本目录所有文件的 mtime 范围：**2026-05-16 14:39 → 2026-05-18 16:08**，之后不再变动。

历史上之所以会被复制成新目录而保留旧的，主要是因为：要给 [step3_aggregator.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/step3_aggregator.py) 加 `MED_LETTER_INSTRUCTION`、给 step4 加 wild 分支、给 step1/step3 切换 Creator 模型 (`llama_inference → qwen523`)，担心改坏老结果，就把整个目录拷贝去 `papillon/` 继续迭代，这里冻住。

---

## 文件清单

> 与 [`papillon/`](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/README.md) 同名的脚本，含义都一样，区别详见上文。这里只列出本目录的实际状态。

### 脚本

| 文件 | 上次更新 | 作用（与 `papillon/` 的差异） |
|---|---|---|
| [prompt.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/prompt.py) | 2026-05-16 14:39 | Creator + aggregator prompt（与 papillon/ 一字不差）。|
| [skills.md](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/skills.md) | 2026-05-16 14:47 | 最初的需求文档（与 papillon/ 一字不差）。|
| [step1_creator.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/step1_creator.py) | 2026-05-17 17:28 | Step 1 批量 Creator。**MODEL = `llama_inference`**（papillon/ 主版本里已经切到 `qwen523`），输出列名 `priv_query`，默认输出文件 `step1_priv_query.parquet`。|
| [step1_creator_single.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/step1_creator_single.py) | 2026-05-18 13:56 | 单条 Creator（与 `papillon/` 完全一致）。|
| [step2_remote.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/step2_remote.py) | 2026-05-16 14:53 | Step 2 远程 GPT-4o 回答 priv_query。和 papillon/ 唯一差别是 INPUT_PATH 默认指向 `step1_priv_query.parquet`（而不是 `step1_qwen523_priv_query.parquet`）。|
| [step3_aggregator.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/step3_aggregator.py) | 2026-05-16 14:54 | Step 3 信息聚合。MODEL = `llama_inference`，`MAX_WORKERS=8`，**没有 `MED_LETTER_INSTRUCTION`、没有 ability 注入逻辑**——只把 (q, remote_answer) 套 aggregator 模板返回。这是和 papillon/ 最大的差异。|
| [step4_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/step4_eval.py) | 2026-05-16 14:54 | 早期单一 privacy 路径的 Q_AL pairwise 评测（与 `papillon/` 一致，未变）。|
| [step4_1_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/step4_1_eval.py) | 2026-05-17 17:26 | 混合能力评测的早期版：**privacy 走 Q_AL，Med 走选项字母 judge（不传 user_query）**，没有 wild 分支；输出默认到 `inference/mix_data/step4_eval_result.parquet`。|
| [find_over_abstract.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/find_over_abstract.py) | 2026-05-18 13:23 | 启发式找过度抽象的 q'（与 `papillon/` 一字不差）。|
| [abstract_examples.jsonl](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/abstract_examples.jsonl) | 2026-05-18 16:08 | 早期跑出的过度抽象 case set。|

### 数据文件

| 文件 | 上次更新 | 说明 |
|---|---|---|
| [test.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/test.parquet) | 2026-05-17 17:23 | 原始测试集快照。|
| [0_.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/0_.parquet) | 2026-05-17 17:28 | step1 的实际输入（约 540KB，比 papillon/ 的 0_.parquet 小很多——说明当时只跑了 privacy 子集）。|
| [step1_priv_query.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/step1_priv_query.parquet) | 2026-05-17 17:29 | llama_inference Creator 输出。|
| [step2_remote_answer.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/step2_remote_answer.parquet) | 2026-05-17 17:31 | 远端 GPT-4o 答案。|
| [step3_final_answer.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/step3_final_answer.parquet) | 2026-05-17 17:34 | aggregator 融合答案。|

> 没有 `5_*.parquet` / step5 / step4_eval_result：当时整条链路只跑到 step3_final_answer，step4 输出落到 `inference/mix_data/step4_eval_result.parquet`，而不是这个目录里。

---

## 与其他 `papillon_*` 目录的关系

| 目录 | 角色 |
|---|---|
| **`papillon_old/`**（本目录） | 最初版（5/16–5/18），仅 privacy ability，已冻结。|
| `papillon_pupa/` | 5/17 一次性快照，结构与本目录几乎相同，但换了带 `pii_units` 列的输入并多了 `step5_privacy.py`。|
| `papillon_privacy/` | 后来独立出来的隐私评测分支，只评 `pp_priv_query` 列的泄漏率。|
| `papillon/` | 现役主版本（5/19+），加入了 Med 支持、qwen523、step5_anoy、wild 分支等。|

