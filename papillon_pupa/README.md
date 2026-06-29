
# `papillon_pupa/` 目录说明

> **状态：实验性中间快照（5/17）。新工作请直接用 [`papillon/`](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/README.md)。**

> 命名解释：butterfly (papillon) 之前的形态是 **pupa（蛹）**——所以这个目录的语义是"papillon 的中间形态"。它是从 [`papillon_old/`](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/README.md) 拷过来后做了一次小修改，在 step3_final_answer 后面加了一个**针对 PII 泄漏率**的评测脚本 `step5_privacy.py`，跑出 `step5_privacy_result.parquet` 后就被搁置了——后续主线工作转去了 `papillon/` (Med 能力支持等)，所以这里冻结。

---

## 1. 这个目录在做什么

整体链路与 [`papillon_old/`](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_old/README.md) **几乎一模一样**（step1→step2→step3→step4），主要差异有两点：

1. **输入数据 [0_.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/0_.parquet) 自带 `pii_units` 列**（用 `||` 连接的 PII span 字符串），是上游另外一条 PII 打标流水线的产物。其他几个目录的 `0_.parquet` 没有这一列。
2. **新增 [step5_privacy.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/step5_privacy.py)**：用 `pii_units` 当 ground truth，量化 step1 输出 `priv_query` 把多少 PII 泄漏出去了。这是这个目录存在的唯一动机。

step5_privacy 的判定标准与 `inference/0_privacy/0_eval.py` 完全一致：

```
对每个 pii_unit C ∈ pii_units:
    coverage(priv_query, C) >= 1.0          → 词面 / Jaccard 泄漏
 OR BERTScore P_rescaled(C, priv_query) > 0.3 → 语义泄漏
样本只要有 ≥1 个 pii_unit 被标 leaked，就视作 sample-level leak。
```

阈值与 `z_eval/eval_privacy/com_privacy_score.py` 的训练时 reward 对齐。

---

## 2. 文件清单

### 脚本

| 文件 | 上次更新 | 作用 |
|---|---|---|
| [prompt.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/prompt.py) | 2026-05-17 22:54 | Creator + aggregator prompt（与 papillon/ / papillon_old/ 一字不差）。|
| [skills.md](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/skills.md) | 2026-05-17 22:54 | 同上，最初版需求文档。|
| [step1_creator.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/step1_creator.py) | 2026-05-17 22:58 | 与 `papillon_old/step1_creator.py` 仅有路径差别（默认输入 `papillon_pupa/0_.parquet`，输出 `step1_priv_query.parquet`），MODEL 也是 `llama_inference`。|
| [step2_remote.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/step2_remote.py) | 2026-05-17 22:59 | 同 papillon_old，路径换成 papillon_pupa。|
| [step3_aggregator.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/step3_aggregator.py) | 2026-05-17 23:00 | 同 papillon_old：**没有 Med 选项字母强制保留**、`MAX_WORKERS=8`、MODEL `llama_inference`。和 papillon/ 不一样。|
| [step4_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/step4_eval.py) | 2026-05-17 22:54 | 早期 privacy 单路径 Q_AL pairwise 评测（与 papillon_old / papillon 一致）。|
| [step4_1_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/step4_1_eval.py) | 2026-05-17 23:04 | 混合能力评测早期版（与 papillon_old 一致；只支持 `ability == "privacy"` 走 Q_AL，没有 wild）。|
| [step5_privacy.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/step5_privacy.py) | 2026-05-17 23:13 | **本目录新增**：评 step1 输出 priv_query 对 `pii_units` 的泄漏率 + 样本级泄漏率。复用 `z_eval/eval_privacy/com_privacy_score.py` 的 `coverage / _bert_p_rescaled` 原语。默认 `step1_priv_query.parquet → step5_privacy_result.parquet`。|

### 数据文件

| 文件 | 上次更新 | 说明 |
|---|---|---|
| [test.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/test.parquet) | 2026-05-17 22:54 | 原始测试集快照。|
| [0_.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/0_.parquet) | 2026-05-17 22:57 | step1 输入。**关键差异：自带 `pii_units` 列**，作为 step5_privacy.py 的 ground truth。|
| [step1_priv_query.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/step1_priv_query.parquet) | 2026-05-17 22:59 | step1 (`llama_inference`) Creator 输出。|
| [step2_remote_answer.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/step2_remote_answer.parquet) | 2026-05-17 23:00 | step2 远端答案。|
| [step3_final_answer.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/step3_final_answer.parquet) | 2026-05-17 23:01 | step3 aggregator 融合答案。|
| [step4_eval_result.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/step4_eval_result.parquet) | 2026-05-17 23:05 | step4_1_eval 输出。|
| [step5_privacy_result.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_pupa/step5_privacy_result.parquet) | 2026-05-17 23:16 | step5_privacy.py 的 per-row 输出（每行包含 `pii_items / pii_leak_flags / pii_coverage / pii_bert_p / sample_leak`）。|

> 整个目录所有文件的 mtime 都集中在 **2026-05-17 22:54 → 2026-05-17 23:16**，**前后不到 25 分钟就跑完了整条链路（step1→step5）**，之后不再变动。换句话，这个目录是一个"一次性跳跃产生的调试现场"。

---

## 3. 与其他 `papillon_*` 目录的关系

| 目录 | 角色 |
|---|---|
| `papillon_old/` | 最初版（5/16–5/18）。本目录基本是它 5/17 的 **fork**。|
| **`papillon_pupa/`**（本目录） | papillon_old + step5_privacy。冻结于 5/17。|
| `papillon_privacy/` | 另一条隐私评测分支，评 `pp_priv_query` 列（papillon 后处理版本）。|
| `papillon/` | 现役主版本，加入 Med 能力、qwen523、step5_anoy（Presidio 打标）等。本目录的 `step5_privacy.py` 与 `papillon/` 的 `step5_anoy.py` **目的完全不同**：前者是评泄漏率，后者是给 question 打 Presidio PII 标签。|

