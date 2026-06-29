
# `papillon_privacy/` 目录说明

> **状态：单脚本评测分支，已冻结（所有文件 mtime = 2026-05-17 20:49）。** 用于评 PAPILLON 后处理过的 priv_query (`pp_priv_query` 列) 相对原始 question 的隐私泄漏 + ea 保留。

## 1. 这个目录在做什么

整个目录只有一件事：**对一份带有 `pp_priv_query` 列的 parquet 跑离线隐私评测**，量化它把多少 PII / 任务无关信息（NE）泄漏到了改写后的 query 里，以及保留了多少必要信息（ea）。

> 名字里的 `pp` 是 "post-processed"（papillon-后处理过的）priv_query。和 `inference/1_privacy/` 评的是同一种列。
>
> 为什么单独开一个目录而不是和 `papillon/` 合并？从 mtime 看（三个文件同为 2026-05-17 20:49），这个目录**甚至比 `papillon_pupa/` 还早几个小时**冻结的。当时应该是在 papillon 主线之外开的一个独立试验点：拿到上游跑出来的一批 `pp_priv_query`，只验证隐私指标（不跑生成流水线）。两者职责不同：
> - `papillon/` ⇒ 跑完整 5 步流水线，产 `final_answer` 并评答案质量；
> - `papillon_privacy/` ⇒ 只评隐私指标，不跑生成。

## 2. 文件清单

| 文件 | 上次更新 | 作用 |
|---|---|---|
| [0_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_privacy/0_eval.py) | 2026-05-17 20:49 | **唯一的评测脚本**。和 [inference/0_privacy/0_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/0_privacy/0_eval.py) 是同一份代码，只改了三处常量：<br>① `DEFAULT_INPUT` → `papillon_privacy/test_with_priv_query_with_pii.parquet`；<br>② `DEFAULT_OUTPUT` → `papillon_privacy/0_pp_eval_result.parquet`；<br>③ `PRIV_QUERY_COL = "pp_priv_query"`（不再读 `priv_query`）。<br>逻辑：对每行的 `question_pii_entities` 与 `extra_info["ne"]` 用 Jaccard coverage(≥1.0) + BERTScore P_rescaled(>0.3) 双阈值判定是否被泄漏到 `pp_priv_query` 里；同时对 `extra_info["ea"]` 用 cov≥0.5 / bertP>0.3 判 retention。会用 `extra_info['key_spans'] + ea` 拼成 haystack 把"本就该保留的内容"先过滤掉。最终打印 sample-level / pii item / ne item / ea retention 几个聚合率，并把 per-row 结果落盘。复用了 `z_eval/eval_privacy/com_privacy_score.py` 的原语，与训练时 reward 对齐。|
| [test_with_priv_query_with_pii.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_privacy/test_with_priv_query_with_pii.parquet) | 2026-05-17 20:49 | 评测输入。必须含 `pp_priv_query`、`extra_info`（带 `question / ne / ea / key_spans`）、`question_pii_entities` 三列。是 papillon 流水线的 priv_query 经过后处理后再打过 PII 标签的版本。|
| [0_pp_eval_result.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon_privacy/0_pp_eval_result.parquet) | 2026-05-17 20:49 | `0_eval.py` 的产物：每行包含 `pii_items / pii_leak_flags / pii_coverage / pii_bert_p / ne_* / ea_* / sample_leak` 等字段，可以直接拿去做后续切片分析。|

> 本目录三个文件的 mtime **全部定格在 2026-05-17 20:49**（同一分钟），之后不再变动：当时导入了一批带 `pp_priv_query` 列的评测输入，跑完一次 `0_eval.py` 后就冻住了；之后主体工作转去了 `papillon/`。

## 3. 关键指标与阈值（来自 0_eval.py 注释）

```
COV_THRESHOLD     = 1.0   # >=1.0 视为词面泄漏
BERT_THRESHOLD    = 0.3   # >0.3  视为语义泄漏
EA_COV_THRESHOLD  = 0.5   # >=0.5 视为 ea retained
EA_BERT_THRESHOLD = 0.3
```

输出指标：
- `sample-level leak rate (full / eligible)`：所有样本 / 至少含 1 个 pii or ne item 的样本里，有多少出现了任意一项泄漏。
- `pii item leak rate`：被泄漏的 pii item 数 / 全部 pii item 数。
- `ne item leak rate`：同上但针对 NE。
- `ea retention rate`：被保留的 ea item 数 / 全部 ea item 数。

## 4. 与其他 `papillon_*` 目录的关系

| 目录 | 时间跨度 | 角色 |
|---|---|---|
| `papillon_old/` | 2026-05-16 ~ 05-18 | 最初版主流水线，已弃用。|
| `papillon_pupa/` | 2026-05-17 22:54 ~ 23:16 | 中间快照，含 `step5_privacy.py`（评 `priv_query` 对 `pii_units` 的泄漏，但**不涉及 ne / ea**）。|
| **`papillon_privacy/`**（本目录） | 2026-05-17 20:49（三个文件同一分钟冻结） | 单独的隐私评测分支，评 `pp_priv_query`（后处理版）的 PII / NE 泄漏 + ea 保留率。**指标维度比 papillon_pupa/step5_privacy 多 ne 与 ea 两类**。|
| `papillon/` | 2026-05-19 ~ 05-25 | 现役主流水线，跑完整 5 步并产 `final_answer`。|

> 从 mtime 看，`papillon_privacy/` 反而是**三个旧目录里最早冻结的**一个（还早于 papillon_pupa 几个小时），不是后来才独立出来的。推测是当时为了跳过"跑生成流程"直接拿 `pp_priv_query` 验证隐私指标，跳过后、并未重启。

