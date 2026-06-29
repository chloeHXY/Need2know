
# `prediax/` 与 `prediax_old/` 目录说明

这两个目录保存的是 **PrediaX 路线（Presidio 脱敏 → GPT-4o 直接回答 → 多能力评测）** 的全量产物，是另一条对照基线（与 `inference/mix_data/` 的"helperAnswer + merge inference"主流水线并行存在）。

> ⚠️ **关于"prediax / prediax_old"两个目录**
> - `prediax_old` 是 **5/17 的初版小样本快照**：测试集 `test_with_priv_query.parquet` 仅 ~510 KB，只评测 `ability == privacy / Med`；
> - `prediax` 是 **5/19 起的当前主版本**：用更大的 `test_with_priv_query.parquet`（~3.3 MB）重跑全链路，并把 `wild` ability 也并入 privacy 那条分支跑 Q_AL 评测；
> - `prediax` 还在 **5/20** 新增了 `5_*` / `6_*` 两个补丁脚本，用来"用脱敏 question 直接覆盖 priv_query"再做一次按 ability 分桶 + wild top-50 排除的评测。
>
> 当前以 `prediax/` 为准；`prediax_old/` 仅作为历史快照保留。

---

## 流水线总览

PrediaX 的核心思想：**不让模型读到原始 question，而是直接用脱敏后的 question 去问 GPT-4o**，然后对它的回答做（a）答案质量评测和（b）priv_query 隐私泄漏评测。

```
test_with_priv_query.parquet
        │
        ▼
  1_anoy.py            (Presidio 给 extra_info["question"] 打 PII 标 → question_anonymized + question_pii_entities)
        │
        ▼
   0_.parquet
        │
        ▼
  2_inference.py       (把 question_anonymized 直接喂给 GPT-4o → anony_answer)
        │
        ▼
   2_.parquet
        │
        ├─────────────────────────────────────────────────────────────┐
        ▼                                                              ▼
  3_eval.py                                                  4_priv_eval.py
  (混合能力答案质量评测：                                  (priv_query=question_anonymized
   privacy/wild 走 Q_AL pairwise；                          相对原 question 的 PII/NE 泄漏率
   Med 走 GPT-4o 单选一致性)                                 + ea 保留率，复用 com_privacy_score)
        │                                                              │
        ▼                                                              ▼
  3_eval_result.parquet                                          4_priv_eval.parquet
```

`prediax/` 还多了一段 5_/6_ 的 **"用 question_anonymized 覆盖 priv_query 后再按 ability 分桶评测"** 补丁：

```
   0_.parquet
        │
        ▼
  5_overwrite_priv_query.py   (df["priv_query"] = df["question_anonymized"])
        │
        ▼
   5_.parquet
        │
        ▼
  6_eval_by_ability_excl_wild_top50.py
  (按 ability 分桶的 PII/NE 泄漏率，
   并按 mix_data/wild_pii_leak_sorted.json 排掉 top-50 wild)
        │
        ▼
   5_eval.parquet  +  5_eval.csv
```

---

## `prediax/` 文件清单（**当前主版本，5/19 ~ 5/20**）

### 输入

| 文件 | 上次更新时间 | 说明 |
|---|---|---|
| `test_with_priv_query.parquet` | 2026-05-19 20:56 | 输入测试集（~3.3 MB），含 `extra_info`（其中有 `question` / `ne` / `ea` / `key_spans` / `answer_label` 等）、`priv_query`、`gpt_answer`、`ability`（取值 `privacy` / `Med` / `wild`）等列。**这是 5/19 的全量版**，比 `prediax_old/` 的版本大约多 6~7 倍数据。|

### 阶段脚本与产物

| 顺序 | 文件 | 上次更新时间 | 用途 |
|---|---|---|---|
| 1 | [1_anoy.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/1_anoy.py) | 2026-05-19 20:55 | 用 Microsoft Presidio 的 `AnalyzerEngine + AnonymizerEngine` 给 `extra_info["question"]` 打 PII 标签：新增**顶层**列 `question_anonymized`（脱敏后文本）和 `question_pii_entities`（list[str]，原始 PII 文本片段）。其它列原样保留。默认 IO：`test_with_priv_query.parquet → 0_.parquet`。文件名 `anoy` 是 anonymize 缩写。|
| 1.out | `0_.parquet` | 2026-05-19 20:58 | `1_anoy.py` 输出（~4.0 MB），后续阶段的统一入口。|
| 2 | [2_inference.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/2_inference.py) | 2026-05-19 20:55 | 读 `0_.parquet` 的 `question_anonymized` 列（**注意：不是 priv_query**），多线程（默认 16 worker）调 GPT-4o（Venus 代理 `vxlvrEY2AbE0DmrJreMHBlEN@5325`），system prompt 是 `"Please answer the question and provide the answer directly, without explanation."`，把回答写入新列 `anony_answer`。默认 IO：`0_.parquet → 2_.parquet`。**这就是 PrediaX 的"模型回答"**——它压根没读原始 question，而是读脱敏版。|
| 2.out | `2_.parquet` | 2026-05-19 21:03 | `2_inference.py` 输出（~4.5 MB），含 `anony_answer`。|
| 3 | [3_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/3_eval.py) | 2026-05-19 21:04 | 混合能力评测（与 `inference/mix_data/3_eval.py` 同构）：`anony_answer` 当作 C_L、`gpt_answer` 当作 C_T。<br/>• `ability == privacy` 或 `wild` → 走 Q_AL pairwise 判定（A/B 互换两次取一致性，否则取 s1）；<br/>• `ability == Med` → GPT-4o 单选一致性 prompt（与 `extra_info["answer_label"]` 比对，输出 0/1）。<br/>默认 IO：`2_.parquet → 3_eval_result.parquet`。**关键差异**：相比 `prediax_old/3_eval.py`，这版把 `wild` 也并入 privacy 分支（见下文"两目录差异"小节）。|
| 3.out | `3_eval_result.parquet` | 2026-05-19 21:13 | `3_eval.py` 输出的 per-row 评测结果（~1.8 MB），含 `score / s1 / s2 / response_A / response_B` 等列。|
| 4 | [4_priv_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/4_priv_eval.py) | 2026-05-19 20:55 | priv_query（**这里指 `question_anonymized`，被脚本顶部常量 `PRIV_QUERY_COL = "question_anonymized"` 重定向**）相对原始 question 的隐私泄漏评测。复用 `z_eval/eval_privacy/com_privacy_score.py` 的 `coverage` + `_bert_p_rescaled` 原语，阈值与训练时一致：cov≥1.0 或 bertP>0.3 视为泄漏；ea 项 cov≥0.5 或 bertP>0.3 视为保留。会先用 `extra_info["key_spans"] + extra_info["ea"]` 拼成 haystack 过滤本就该保留的内容；并对 `question_pii_entities` 做 MCQ 选项串噪声过滤。输出 sample-level / pii-item / ne-item 泄漏率 + ea 保留率。默认 IO：`2_.parquet → 4_priv_eval.parquet`。|
| 4.out | `4_priv_eval.parquet` | 2026-05-19 20:55 | `4_priv_eval.py` 输出（~273 KB），per-row 含 `pii_items / pii_leak_flags / pii_coverage / pii_bert_p / ne_* / ea_*` 等明细。|
| 5 | [5_overwrite_priv_query.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/5_overwrite_priv_query.py) | 2026-05-20 02:24 | **5/20 新增的补丁**。功能极简：读 `0_.parquet`，把 `priv_query` 列直接用 `question_anonymized` 列覆盖（保留其它列），输出 `5_.parquet`。目的是让下游评测脚本（默认读 `priv_query`）可以直接复用，把"PrediaX 脱敏版 question"当作 priv_query 来比对。|
| 5.out | `5_.parquet` | 2026-05-20 02:24 | `5_overwrite_priv_query.py` 输出（~4.4 MB），结构同 `0_.parquet`，但 `priv_query` 列已被替换为 `question_anonymized`。|
| 6 | [6_eval_by_ability_excl_wild_top50.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/6_eval_by_ability_excl_wild_top50.py) | 2026-05-20 02:27 | **5/20 新增**。直接 `importlib` 加载 `inference/0_privacy/0_eval.py` 复用其原语，在 `5_.parquet` 上做按 `ability` 分桶（privacy / Med / wild / __overall__）的 PII/NE 泄漏 + ea 保留率评测；并按 `inference/mix_data/wild_pii_leak_sorted.json` 排掉前 50 条高泄漏 wild 样本（保留行但打 `excluded_from_stats` 标记）。匹配通过 `(question, priv_query)` 文本对、question 文本、row_index 三种方式。本脚本里 sample-level 泄漏改为**只看 NE 泄漏**（与 `inference/0_privacy/0_eval_by_ability_excl_wild_top50.py` 一致）。默认 IO：`5_.parquet → 5_eval.parquet`，summary CSV → `5_eval.csv`。|
| 6.out | `5_eval.parquet` | 2026-05-20 02:27 | `6_*.py` 的 per-row 输出（~1.7 MB）。|
| 6.out | `5_eval.csv` | 2026-05-20 02:27 | `6_*.py` 的 per-ability summary 表（~750 B），列名见脚本里的 `_Bucket.as_summary_row`。|

### 完整修改时间一览（按时间排序）

```
2026-05-19 20:55:06   1_anoy.py
2026-05-19 20:55:07   2_inference.py
2026-05-19 20:55:08   4_priv_eval.parquet
2026-05-19 20:55:08   4_priv_eval.py
2026-05-19 20:56:57   test_with_priv_query.parquet
2026-05-19 20:58:43   0_.parquet
2026-05-19 21:03:50   2_.parquet
2026-05-19 21:04:40   3_eval.py
2026-05-19 21:13:04   3_eval_result.parquet
--- 5/20 补丁 ---
2026-05-20 02:24:22   5_overwrite_priv_query.py
2026-05-20 02:24:27   5_.parquet
2026-05-20 02:27:04   6_eval_by_ability_excl_wild_top50.py
2026-05-20 02:27:36   5_eval.parquet
2026-05-20 02:27:36   5_eval.csv
```

> 时间是文件系统的 mtime（最近一次写入）；`*.parquet` 的 mtime 即对应的脚本一次跑完写盘的时间。

---

## `prediax_old/` 文件清单（**5/17 初版，已废弃**）

| 文件 | 说明 |
|---|---|
| `test_with_priv_query.parquet` | 5/17 的小样本输入（~510 KB），数据量约为新版的 1/6。|
| `0_.parquet` | 旧版 `1_anoy.py` 在小测试集上的输出（~630 KB）。|
| [1_anoy.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax_old/1_anoy.py) | **与 `prediax/1_anoy.py` 文件内容完全一致**（diff 为空）。|
| `2_.parquet` | 旧版 `2_inference.py` 输出（~730 KB）。|
| [2_inference.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax_old/2_inference.py) | **与 `prediax/2_inference.py` 完全一致**（diff 为空）。|
| `3_eval_result.parquet` | 旧版 3_eval 评测结果（~211 KB）。|
| [3_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax_old/3_eval.py) | **唯一与新版有差异的脚本**：privacy 分支只判 `ability.lower() == "privacy"`，没有 `or "wild"`。即在这一版里 `wild` 行会落到"unknown"分支被跳过。|
| `4_priv_eval.parquet` | 旧版 4_priv_eval 输出（~273 KB）。|
| [4_priv_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax_old/4_priv_eval.py) | **与 `prediax/4_priv_eval.py` 完全一致**（diff 为空）。|

`prediax_old/` 中**没有** `5_*` / `6_*` 系列文件，因为那两步是 5/20 才补上的。

---

## 两个目录的差异速查

| 维度 | `prediax/` (主版本) | `prediax_old/` (废弃) |
|---|---|---|
| 时间 | 5/19 跑 0~4，5/20 补 5/6 | 5/17 一次性跑完 0~4 |
| 测试集大小 | ~3.3 MB（全量） | ~510 KB（早期小样本） |
| `1_anoy.py` | 同 | 同 |
| `2_inference.py` | 同 | 同 |
| `3_eval.py` | privacy 分支处理 `privacy` **和 `wild`** 两种 ability | privacy 分支只处理 `privacy`，`wild` 行被当作 unknown 跳过 |
| `4_priv_eval.py` | 同 | 同 |
| `5_overwrite_priv_query.py` | 有 | **没有** |
| `5_.parquet` / `5_eval.parquet` / `5_eval.csv` | 有（5/20 产出） | **没有** |
| `6_eval_by_ability_excl_wild_top50.py` | 有 | **没有** |

---

## 复刻当前主版本的命令

```bash
cd /group/40047/eiraxyhuang/workspace/fc/DataG/prediax

# Step 1: Presidio anonymize
python 1_anoy.py
# in : test_with_priv_query.parquet
# out: 0_.parquet  (+ question_anonymized, question_pii_entities)

# Step 2: GPT-4o answers the anonymized question directly
python 2_inference.py
# in : 0_.parquet
# out: 2_.parquet  (+ anony_answer)

# Step 3: mixed-ability quality eval (privacy/wild Q_AL + Med single-choice)
python 3_eval.py
# in : 2_.parquet
# out: 3_eval_result.parquet

# Step 4: privacy leakage of question_anonymized vs original question
python 4_priv_eval.py
# in : 2_.parquet
# out: 4_priv_eval.parquet

# Step 5 (5/20 补丁): treat question_anonymized as priv_query
python 5_overwrite_priv_query.py
# in : 0_.parquet
# out: 5_.parquet  (priv_query := question_anonymized)

# Step 6 (5/20 补丁): per-ability leak eval, drop wild top-50
python 6_eval_by_ability_excl_wild_top50.py
# in : 5_.parquet
# out: 5_eval.parquet, 5_eval.csv
```

---

## 与 `inference/mix_data/` 主流水线的关系

PrediaX 是 **mix_data 主流水线的一个对照基线**：

| 维度 | `inference/mix_data/`（主） | `prediax/`（基线） |
|---|---|---|
| 模型回答路径 | 部署模型读 `original question + helperQuery + helperAnswer` 做 merge 推理 → `merge_inference_answer` | GPT-4o 直接读 `question_anonymized` → `anony_answer` |
| 模型是否能看到原 question | 看得到 | 看不到（只看 Presidio 脱敏版） |
| 答案质量评测 | `mix_data/3_eval.py` (同结构 prompt) | `prediax/3_eval.py` (同结构 prompt) |
| 隐私评测 | `inference/0_privacy/0_eval_by_ability*.py` | `prediax/4_priv_eval.py` + `prediax/6_*.py` |
| top-50 wild 排除依赖文件 | `mix_data/wild_pii_leak_sorted.json` | 同（被 `prediax/6_*.py` 引用） |

