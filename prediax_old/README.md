
# `prediax_old/` 目录说明（**废弃，仅保留作历史快照**）

> 当前请一律使用 [/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/README.md) 主版本。
> 本目录为 **5/17 的初版**，测试集还是早期小样本（~510 KB）、`3_eval.py` 还没有把 `wild` 并入 privacy 分支、且没有 5_/6_ 系列补丁。

---

## 来历

PrediaX 路线（Presidio 脱敏 → GPT-4o 直接回答 → 多能力评测）的最早一版产物。从 `prediax_old → prediax` 的演化路径：

1. **5/17**：在小样本 `test_with_priv_query.parquet` (~510 KB) 上一次性跑完 `1_anoy.py → 2_inference.py → 3_eval.py → 4_priv_eval.py`，结果保存到本目录。
2. **5/19**：换成全量 `test_with_priv_query.parquet` (~3.3 MB) 重跑全链路，并把 `3_eval.py` 改成把 `wild` ability 也走 Q_AL pairwise 分支 → 复制到 `prediax/`。
3. **5/20**：又在 `prediax/` 里补了 `5_overwrite_priv_query.py`（用 `question_anonymized` 覆盖 `priv_query`） + `6_eval_by_ability_excl_wild_top50.py`（按 ability 分桶 + wild top-50 排除评测）。

也就是说 `prediax_old/` 之所以被另外保留下来，是因为换了测试集 + 改了 `3_eval.py` 的 ability 路由逻辑，作者复制了一份新目录单独跑，原目录就此冻结。

---

## 文件清单

| 文件 | 上次更新时间 | 说明 |
|---|---|---|
| `test_with_priv_query.parquet` | 2026-05-17 17:46 | 5/17 的小样本输入（~510 KB），数据量约为新版 (`prediax/test_with_priv_query.parquet`, ~3.3 MB) 的 1/6。|
| [1_anoy.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax_old/1_anoy.py) | 2026-05-17 17:52 | 用 Microsoft Presidio 给 `extra_info["question"]` 打 PII 标，新增顶层列 `question_anonymized` + `question_pii_entities`。**与 `prediax/1_anoy.py` 文件内容完全一致**（diff 为空）。`anoy` 是 anonymize 缩写。|
| `0_.parquet` | 2026-05-17 17:53 | `1_anoy.py` 在小测试集上的输出（~630 KB）。|
| [2_inference.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax_old/2_inference.py) | 2026-05-17 17:54 | 读 `0_.parquet` 的 `question_anonymized` 列，多线程调 GPT-4o（Venus 代理），把回答写入 `anony_answer` 列。**与 `prediax/2_inference.py` 完全一致**（diff 为空）。|
| `2_.parquet` | 2026-05-17 17:56 | `2_inference.py` 输出（~730 KB），含 `anony_answer`。|
| [3_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax_old/3_eval.py) | 2026-05-17 17:57 | 混合能力评测：`anony_answer` 当 C_L、`gpt_answer` 当 C_T。privacy 走 Q_AL pairwise，Med 走 GPT-4o 单选一致性。**与 `prediax/3_eval.py` 唯一的差异**：privacy 分支只判 `ability.lower() == "privacy"`，没有 `or "wild"`，所以这一版里 `wild` 行会落到"unknown"分支被跳过、不计入指标。|
| `3_eval_result.parquet` | 2026-05-17 17:58 | `3_eval.py` 输出的 per-row 评测结果（~211 KB）。|
| [4_priv_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/prediax_old/4_priv_eval.py) | 2026-05-17 21:04 | priv_query（脚本里把 `PRIV_QUERY_COL` 重定向为 `question_anonymized`）相对原始 question 的 PII/NE 泄漏 + ea 保留率评测，复用 `z_eval/eval_privacy/com_privacy_score.py`。**与 `prediax/4_priv_eval.py` 完全一致**（diff 为空）。|
| `4_priv_eval.parquet` | 2026-05-17 21:05 | `4_priv_eval.py` 输出（~273 KB），per-row 含 `pii_items / pii_leak_flags / pii_coverage / pii_bert_p / ne_* / ea_*` 等明细。|

本目录**没有** `5_*` / `6_*` 系列文件（那是 5/20 才在 `prediax/` 里补上的）。

### 完整修改时间一览（按时间排序）

```
2026-05-17 17:46:43   test_with_priv_query.parquet
2026-05-17 17:52:36   1_anoy.py
2026-05-17 17:53:08   0_.parquet
2026-05-17 17:54:24   2_inference.py
2026-05-17 17:56:51   2_.parquet
2026-05-17 17:57:40   3_eval.py
2026-05-17 17:58:23   3_eval_result.parquet
2026-05-17 21:04:05   4_priv_eval.py
2026-05-17 21:05:38   4_priv_eval.parquet
```

> 时间是文件系统的 mtime（最近一次写入）。可以看到本目录所有文件都在 5/17 当天产生，之后再没有动过。

---

## 与 `prediax/` 的差异速查

| 维度 | `prediax_old/` (本目录, 废弃) | `prediax/` (主版本) |
|---|---|---|
| 时间 | 5/17 一次性跑完 0~4 | 5/19 跑 0~4，5/20 补 5/6 |
| 测试集大小 | ~510 KB（早期小样本） | ~3.3 MB（全量） |
| `1_anoy.py` | 同 | 同 |
| `2_inference.py` | 同 | 同 |
| `3_eval.py` | privacy 分支只处理 `privacy`，`wild` 行被当作 unknown 跳过 | privacy 分支处理 `privacy` **和 `wild`** |
| `4_priv_eval.py` | 同 | 同 |
| `5_overwrite_priv_query.py` | **没有** | 有 |
| `5_.parquet` / `5_eval.parquet` / `5_eval.csv` | **没有** | 有 |
| `6_eval_by_ability_excl_wild_top50.py` | **没有** | 有 |

---

## 不要在这里跑新实验

如果你不是为了回溯历史结果或重现 5/17 的小样本数字，请直接使用 `/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/` 主版本，并参考其 README 的命令清单。

