# `inference` 目录说明

> 📅 文件最后修改时间快照采集于 **2026-06-29**（来自 `ls -la --time-style=long-iso`）。

本目录是隐私改写（priv-rewrite）+ 多能力评测（privacy / Med / wild）流水线的工作空间，主要负责：

1. 用 GPT-4o 生成参考答案（gpt_answer）；
2. 用 Presidio + GPT-4o 给原问题打 PII 标签；
3. 调用部署模型（llama_inference / qwen7b 等）做"helper-answer + original-question"的合并推理；
4. 用 GPT-4o LLM-as-Judge 对推理结果做成对评测（privacy / wild）和单选一致性评测（Med）；
5. 计算 priv_query 相对原始 question 的 PII / NE 泄漏率，以及 ea 保留率。

> ⚠️ **注意**：很多文件名是按照"运行顺序"加 `0_` / `1_` / `2_` 前缀的，并不代表层级或依赖关系；同时存在 `mix_data` (在用) 与 `mix_data_old` (废弃) 两个并行版本，请以下文说明为准。

---

## 顶层目录结构

```
inference/
├── 0_todo.md                  # 顶层任务清单：写推理脚本，给 question 加 gpt_answer
├── inference.py               # 用 GPT-4o 给 priv_query 生成 privq_gpt_answer
├── inference_gt.py            # 用 GPT-4o 给 extra_info["question"] 生成 gpt_answer (ground truth 参考答案)
├── inference_pii_gt.py        # 用 GPT-4o 给 question_anonymized 生成 question_anonymized_gpt_answer
│
├── test*.parquet              # 各阶段的测试集快照（见下文）
│
├── 0_privacy/                 # priv_query 的隐私泄漏评测套件 v0（基于 Presidio 打 PII 标签）
├── 1_privacy/                 # priv_query 的隐私泄漏评测套件 v1（基于 GPT-4o 打 PII 标签 + pp_priv_query 列）
├── judge/                     # gpt-4o-mini LLM-as-Judge 评测脚本
├── data524/                   # 5/24 数据快照入口（仅含 command.sh）
├── mix_data/                  # ★主用★ "GPT 参考答案 + 部署模型合并推理 + 评测" 全流水线
├── mix_data_old/              # 废弃的早期版本，仅保留作历史参考，不要再跑
└── __pycache__/               # 自动生成
```

### 子目录最后修改时间一览

| 子目录 | 最后修改时间 | 说明 |
|---|---|---|
| `0_privacy/` | 2026-05-20 01:01 | priv_query 隐私泄漏评测套件 v0（Presidio）。|
| `1_privacy/` | 2026-05-17 20:28 | priv_query 隐私泄漏评测套件 v1（GPT-4o PII）。|
| `judge/` | 2026-05-24 18:41 | gpt-4o-mini LLM-as-Judge 评测脚本与各 step 模型快照。|
| `data524/` | 2026-05-24 18:41 | 5/24 数据快照入口（仅含 `command.sh`）。|
| `mix_data/` | 2026-05-25 12:51 | ★主用★ 全流水线工作目录，仍在活跃使用。|
| `mix_data_old/` | 2026-05-17 20:10 | 废弃的早期版本（2026-05-17 之后未再修改）。|
| `__pycache__/` | 2026-05-11 14:16 | Python 编译缓存，可安全删除。|

---

## 顶层文件

| 文件 | 最后修改时间 | 用途 |
|---|---|---|
| [0_todo.md](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/0_todo.md) | 2026-05-15 16:24 | 顶层 TODO，记录最初两个推理需求（test.parquet 加 gpt_answer，以及对 anonymized jsonl 推理）。|
| [inference.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/inference.py) | 2026-05-12 02:48 | 读 `test_with_priv_query.parquet`，对 `priv_query` 字段调 GPT-4o，写出 `privq_gpt_answer` 列到 `test_with_priv_query_add_gptinfo.parquet`。System prompt = "Please answer the question and provide the answer directly, without explanation."。|
| [inference_gt.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/inference_gt.py) | 2026-05-15 17:11 | 读 `test.parquet`，从 `extra_info["question"]` 提问，用 GPT-4o 生成 `gpt_answer`，写出 `test_with_gpt_answer2.parquet`。这就是被各 `3_eval.py` 当作 C_T 的"标准答案"。|
| [inference_pii_gt.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/inference_pii_gt.py) | 2026-05-15 17:12 | 读 `test.anonymized.parquet` 的 `question_anonymized` 列，用 GPT-4o 生成 `question_anonymized_gpt_answer`，写出 `test.anonymized_gpt_answer.parquet`。文件名带 `pii_gt` 但**不是**做 PII 打标，而是"对脱敏后问题做推理"。|

### 顶层 parquet 数据快照（按生成顺序）

| 文件 | 最后修改时间 | 说明 |
|---|---|---|
| `test.parquet` | 2026-05-11 14:13 | 原始测试集（含 `extra_info`、`ability` 等字段）。|
| `test_with_priv_query.parquet` | 2026-05-11 16:05 | 由 rewriter 生成 `priv_query` 后的版本，作为后续流水线的输入。|
| `test_with_gpt_answer.parquet` | 2026-05-11 14:18 | `inference_gt.py` 早期产出快照。|
| `test_with_gpt_answer2.parquet` | 2026-05-12 03:20 | `inference_gt.py` 较新一次产出。|
| `test_with_priv_query_add_gptinfo.parquet` | 2026-05-11 16:09 | `inference.py` 输出，含 `privq_gpt_answer`。|
| `test.anonymized.parquet` | 2026-05-15 17:08 | Presidio 脱敏后的测试集。|
| `test.anonymized_gpt_answer.parquet` | 2026-05-15 17:13 | `inference_pii_gt.py` 输出，含 `question_anonymized_gpt_answer`。|

---

## `0_privacy/` —— priv_query 隐私泄漏评测 v0（Presidio PII）

输入：`test_with_priv_query_with_pii.parquet`（其 `question_pii_entities` 由 Presidio 打标）。

| 文件 | 最后修改时间 | 用途 |
|---|---|---|
| [0_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/0_privacy/0_eval.py) | 2026-05-19 22:20 | **核心**：用 Jaccard coverage (≥1.0) + BERTScore P_rescaled (>0.3) 双阈值，统计 priv_query 对 question 的 PII / NE 泄漏率，以及 ea 保留率（cov≥0.5 或 bertP>0.3）。会先用 `extra_info['key_spans']` + `extra_info['ea']` 拼成 haystack 过滤掉本就该保留的内容。复用了 `z_eval/eval_privacy/com_privacy_score.py` 的原语。|
| [0_eval_by_ability.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/0_privacy/0_eval_by_ability.py) | 2026-05-25 02:45 | 在 `0_eval.py` 的能力上**按 ability 分桶**输出指标（privacy / Med / wild / __overall__），并加了大小写不敏感的 haystack 过滤 + 同一行内 PII/NE 项去重。会额外把 `key_spans` 合入 ea 候选集。输出 parquet + summary csv。|
| [0_eval_by_ability_excl_wild_top50.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/0_privacy/0_eval_by_ability_excl_wild_top50.py) | 2026-05-20 02:15 | 在分桶评测的基础上，**根据 `mix_data/wild_pii_leak_sorted.json` 排掉 top-50 高泄漏的 wild 样本**再聚合（保留行但打 `excluded_from_stats` 标记）。匹配通过 `(question, priv_query)` 文本对、question 文本、row_index 三种方式。默认输入是 `papillon/5_qwen.parquet`。|
| `0_eval_result.parquet` | 2026-05-17 20:48 | `0_eval.py` 的执行产物（per-row 评测结果）。|
| `0_pp_eval_result.parquet` | 2026-05-17 20:35 | `0_eval.py` 在 pp 版本输入上的产物。|
| `test_with_priv_query_with_pii.parquet` | 2026-05-17 20:34 | 已含 Presidio PII 打标列的输入数据快照。|

---

## `1_privacy/` —— priv_query 隐私泄漏评测 v1（GPT-4o PII + pp_priv_query 列）

输入：`test_with_priv_query_pp.parquet`（`pp_*` 表示这是 papillon / 后处理版本的 priv_query）。

| 文件 | 最后修改时间 | 用途 |
|---|---|---|
| [0_pii_note.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/1_privacy/0_pii_note.py) | 2026-05-17 20:12 | 用 GPT-4o (Venus 代理) 给 `extra_info["question"]` 做 PII 打标（14 类 taxonomy + confidence），结果写回 `extra_info` 内的 `question_pii_entities` (list[str]) 与 `question_pii_entities_full` (list[dict])。输出 `test_with_priv_query_pp_with_pii.parquet`。这是相对 `0_privacy/` Presidio 方案的升级版。|
| [1_lift_pii_to_top.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/1_privacy/1_lift_pii_to_top.py) | 2026-05-17 20:17 | 把上一步嵌套在 `extra_info` 里的两个 PII 列**提升为 parquet 顶层列**（默认覆写原文件，自动备份 `.bak`），方便后续 `2_eval.py` 直接读 `question_pii_entities` 顶层列。|
| [2_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/1_privacy/2_eval.py) | 2026-05-17 20:28 | 与 `0_privacy/0_eval.py` 同样阈值、同样指标，但 **priv_query 列名改为 `pp_priv_query`**（因为这一支评的是 post-processed 版本），且不做 haystack/ea 过滤。输出 `2_pp_eval_result.parquet`。|
| `2_eval_result.parquet` | 2026-05-17 20:27 | `2_eval.py` 在原始 priv_query 输入上的产物。|
| `2_pp_eval_result.parquet` | 2026-05-17 20:28 | `2_eval.py` 在 pp_priv_query 输入上的产物。|
| `test_with_priv_query_pp.parquet` | 2026-05-17 19:46 | 输入快照（含 `pp_priv_query`）。|
| `test_with_priv_query_pp_with_pii.parquet` | 2026-05-17 20:18 | 经过 `0_pii_note.py` + `1_lift_pii_to_top.py` 后的中间结果。|

---

## `judge/` —— gpt-4o-mini LLM-as-Judge

| 文件 | 最后修改时间 | 用途 |
|---|---|---|
| [0_judge_gpt4o_mini.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/judge/0_judge_gpt4o_mini.py) | 2026-05-20 13:28 | 对 `llm_test_data/{our,papillon,prediax}.parquet` 三个文件，每行用 `judge_prompt.md` 作为 system prompt 调 gpt-4o-mini，要求返回 JSON `{verdict, reid_risk, utility_score, confidence}`。**支持断点续跑（按 `judge_ok` 列跳过）+ 周期 checkpoint + 用量/成本统计**。需要环境变量 `ENV_VENUS_OPENAPI_SECRET_ID`。输出 `<name>_judged.parquet` 与 sidecar usage json。|
| `0_step150.parquet` | 2026-05-24 18:36 | step150 baseline 模型产出快照。|
| `0_step150_wo_priv.parquet` | 2026-05-24 18:36 | step150 去掉 priv 奖励的消融模型产出。|
| `0_step150_wo_uti.parquet` | 2026-05-24 18:36 | step150 去掉 utility 奖励的消融模型产出。|
| `0_step200.parquet` | 2026-05-24 18:36 | step200 模型产出快照。|

---

## `data524/`

| 文件 | 最后修改时间 | 用途 |
|---|---|---|
| [command.sh](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/data524/command.sh) | 2026-05-24 18:37 | 一行命令：`bash mix_data/run_pipeline.sh data524/0_step150.parquet`，把 5/24 那天的 step150 模型产出灌进主流水线（注意：`mix_data/run_pipeline.sh` 当前在仓库内**未找到**，可能在工作机本地或已被清理）。|

---

## `mix_data/` —— ★主用流水线★

按文件名前缀的 `0_ → 1_ → 2_ → 3_ → 4_ → 5_/6_` 顺序串成一条数据加工 + 评测链路。**这是当前事实上的 default pipeline**，所有"按 ability 混合"评测都在这里跑。

### 主链路脚本（按运行顺序）

| 序号 | 脚本 | 最后修改时间 | 作用 |
|---|---|---|---|
| 0 | [0_add_gpt_answer.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_add_gpt_answer.py) | 2026-05-25 01:17 | 从 `0_gt_ref.parquet` 里按 `extra_info["question"]` 反查 `gpt_answer`，把这一列追加到目标 B 文件（**默认覆写 `0_.parquet`**）。用于把 GT 参考答案接力到当前要评测的模型产出上。|
| 1 | [1_inference.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/1_inference.py) | 2026-05-24 17:22 | 读 `0_.parquet` 的 `priv_query`，用 GPT-4o（带专门 system prompt：把 priv_query 当作"知识助手参考"返回 reference note）生成 `privq_gpt_answer`，写入 `1_.parquet`。这是"helperAnswer"的来源。|
| 2 | [2_merge_inference.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/2_merge_inference.py) | 2026-05-25 12:56 | **核心合并推理**。读 `1_.parquet`，按 `ability` 选择 prompt 模板（`PROMPT_TEMPLATE_privacy` / `PROMPT_TEMPLATE_Med`，`wild` 复用 privacy 模板），把 `original question + helperQuery (priv_query) + helperAnswer (privq_gpt_answer)` 喂给部署模型（默认 `qwen7b`，可改 `llama_inference` / `llama_inference2`），SSE 流式解析，结果写入 `merge_inference_answer` 列得到 `2_.parquet`。支持 `--resume`、`--limit`、`--workers`。|
| 3 | [3_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/3_eval.py) | 2026-05-24 17:48 | 对 `2_.parquet` 做混合能力评测：privacy/wild 走"互换 A/B 两次的 pairwise 判定"（与 `z_eval/eval.py` 一致），Med 走 GPT-4o 单选一致性判定。输出 per-row `3_eval_result.parquet` + stdout 各能力指标 + overall 平均。|
| 4 | [4_anoy.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/4_anoy.py) | 2026-05-24 18:01 | 用 Microsoft Presidio 给 `extra_info["question"]` 打 PII 标签，新增**顶层**列 `question_anonymized`、`question_pii_entities`，输出 `4_.parquet`。文件名 `anoy` 是 anonymize 的简写。|
| 5 | [5_filter_excluded.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/5_filter_excluded.py) | 2026-05-24 17:16 | 在 `test_with_priv_query.parquet` 上做"和评测时一致的 wild top-50 过滤"，产出 `_kept` 与 `_dropped` 两份 parquet。**注意：这个脚本是从测试集**本身**过滤，而 `0_eval_by_ability_excl_wild_top50.py` 是在评测聚合阶段排除。|
| 6 | [6_drop_top50.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/6_drop_top50.py) | 2026-05-25 12:51 | 同样按 `wild_pii_leak_sorted.json` top-K 过滤，但**针对模型产出 parquet**（如 `0_protectfrom_qwen7b.parquet`）做去除，输出新的 `0_.parquet`。和 5_ 的差别在于"针对哪个 parquet"以及顶部 INPUT/OUTPUT 常量配置。|

### `mix_data/` 主要数据文件

| 文件 | 最后修改时间 | 含义 |
|---|---|---|
| `test_with_priv_query.parquet` | 2026-05-24 17:16 | 主流水线输入（含 `priv_query`、`extra_info`、`ability`）。|
| `test_with_priv_query_dropped.parquet` | 2026-05-25 12:51 | `5_/6_` 过滤掉的行（带 `__exclude_reason`）。|
| `0_.parquet` | 2026-05-25 12:51 | 经 `0_add_gpt_answer.py` 追加 GT 参考答案后的当前主输入；也是 `6_drop_top50.py` 的默认输出。|
| `0_gt_ref.parquet` | 2026-05-24 17:20 | GT 参考答案库，`extra_info["question"] -> gpt_answer` 的映射来源。|
| `0_protectfrom.parquet` | 2026-05-24 20:00 | 早期 protector 模型输出的 priv_query 数据快照。|
| `0_protectfrom_qwen.parquet` | 2026-05-25 12:14 | qwen protector 模型产出。|
| `0_protectfrom_qwen7b.parquet` | 2026-05-25 12:51 | qwen7b protector 模型产出（**当前默认**）。|
| `0_step150.parquet` | 2026-05-25 00:02 | step150 模型快照（mix_data 版）。|
| `0_step150_real.parquet` | 2026-05-24 23:58 | step150 真实数据快照。|
| `0_step150_wo_priv.parquet` | 2026-05-24 23:58 | step150 去掉 priv 奖励消融。|
| `0_step150_wo_uti.parquet` | 2026-05-24 23:58 | step150 去掉 utility 奖励消融。|
| `0_step200.parquet` | 2026-05-24 23:58 | step200 模型快照。|
| `1_.parquet` | 2026-05-25 12:56 | `1_inference.py` 输出，含 `privq_gpt_answer`。|
| `2_.parquet` | 2026-05-25 13:15 | `2_merge_inference.py` 输出，含 `merge_inference_answer`。|
| `3_eval_result.parquet` | 2026-05-25 13:20 | `3_eval.py` 输出的 per-row 评测结果。|
| `4_.parquet` | 2026-05-25 13:22 | `4_anoy.py` 输出（含 Presidio 顶层 PII 列）。|
| `4_.parquet.bak.20260520_004357` | 2026-05-24 17:16 | `4_.parquet` 的历史备份（带时间戳）。|
| `4_.parquet.bak_before_dedup` | 2026-05-24 17:16 | 去重前的 `4_.parquet` 历史备份。|
| `4_eval_ability_.parquet` | 2026-05-25 13:23 | `0_privacy/0_eval_by_ability.py` 在 `4_.parquet` 上跑出的分桶评测 per-row 结果。|
| `4_priv_eval.parquet` | 2026-05-24 17:16 | `0_privacy/0_eval.py` 在 priv_query 上的 per-row 结果。|
| `4_priv_eval.csv` | 2026-05-24 17:16 | 上一行 parquet 的 CSV 版。|
| `4_sum.csv` | 2026-05-25 13:23 | 分桶评测的 summary 汇总表。|
| `step4_eval_result.parquet` | 2026-05-24 17:16 | `0_privacy/0_eval.py` 类脚本的产物快照。|
| `final_1945.parquet` | 2026-05-24 17:16 | 1945 行的阶段性最终版数据。|
| `last.parquet` | 2026-05-24 17:16 | 最近一次产出快照。|
| `merged_final_last.parquet` | 2026-05-24 17:16 | `final_1945.parquet` 与 `last.parquet` 合并版。|
| `wild_pii_leak.csv` / `wild_pii_leak.json` | 2026-05-24 17:16 | wild 子集的 PII 泄漏明细。|
| `wild_pii_leak_rows.csv` / `wild_pii_leak_rows.json` | 2026-05-24 17:16 | wild PII 泄漏行级展开版本。|
| `wild_pii_leak_sorted.csv` / `wild_pii_leak_sorted.json` | 2026-05-24 17:16 | 按 `n_pii` 降序排序版（**`*_sorted.json` 是 5_/6_/0_eval_by_ability_excl_wild_top50.py 的关键依赖**）。|
| `wild_dup_report.csv` | 2026-05-24 17:16 | wild 子集内的重复样本报告。|
| `4_wild_leak_classification.csv` | 2026-05-24 17:16 | 对 wild 泄漏样本人工/自动分类的结果。|
| `diff_4_vs_testpriv_lost.csv` | 2026-05-24 17:16 | `4_.parquet` 与 `test_with_priv_query.parquet` 之间丢失行的差异。|
| `diff_A_minus_B.csv` / `diff_B_minus_A.csv` | 2026-05-24 17:16 | A-B / B-A 集合差异。|
| `diff_orig_minus_5qwen_per_question.csv` | 2026-05-24 17:16 | 原始测试集 vs 5_qwen.parquet 的逐题差异（当前为空文件）。|
| `diff_wild_removed_from_A.csv` | 2026-05-24 17:16 | 从 A 集合中被剔除的 wild 行差异表。|
| `res.txt` | 2026-05-24 17:16 | 一次 3_eval 运行的 stdout 摘要（Med/privacy/wild/overall 准确率）。|
| `todo.md` | 2026-05-24 17:16 | 当时给 3_eval.py 的需求文档（含 Med 单选评测 prompt 原文）。|

---

## `mix_data_old/` —— **废弃** 早期版本（不要再跑）

与 `mix_data/` 同构，但是更早期：那时候只有 privacy 这一种 ability，2_merge_inference 还没分桶，评测里也没有 `wild`。**仅作为历史快照保留**。新工作请一律走 `mix_data/`。

> 该目录所有文件均在 **2026-05-17 15:29 ~ 17:35** 之间产生，之后未再修改。

主要差异：

| 老版文件 | 最后修改时间 | 现状 |
|---|---|---|
| [0_inference_gt.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data_old/0_inference_gt.py) | 2026-05-17 15:29 | 老的"给 question 生成 gpt_answer"脚本，等价于现在顶层的 `inference_gt.py`。|
| [0_inference_llama.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data_old/0_inference_llama.py) | 2026-05-17 16:58 | 老的"用 llama_inference 服务直接对 question 推理"baseline，输出 `llama_answer` 列到 `0_llama.parquet`。|
| [0_gt_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data_old/0_gt_eval.py) | 2026-05-17 17:16 | 单独评测 `gpt_answer` 在 ability=Med 上的准确率（只看 GT 答案对单选题对不对，不评 priv 流水线）。|
| [0_llama_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data_old/0_llama_eval.py) | 2026-05-17 17:00 | 把 `0_llama.parquet` 的 `llama_answer` 当作 C_L、`gpt_answer` 当作 C_T 做 pairwise 判定的早期版 3_eval。|
| `1_inference.py` | 2026-05-17 16:03 | 与 `mix_data/` 同名脚本的旧版，请直接看 `mix_data/` 的对应版本。|
| `2_merge_inference.py` | 2026-05-17 17:10 | 与 `mix_data/` 同名脚本的旧版，请直接看 `mix_data/` 的对应版本。|
| `3_eval.py` | 2026-05-17 17:11 | 与 `mix_data/` 同名脚本的旧版，请直接看 `mix_data/` 的对应版本。|
| `0_.parquet` | 2026-05-17 15:35 | 老链路第 0 步快照。|
| `0_llama.parquet` | 2026-05-17 16:58 | `0_inference_llama.py` 输出。|
| `0_llama_eval_result.parquet` | 2026-05-17 17:01 | `0_llama_eval.py` 输出。|
| `0_gt_eval_result.parquet` | 2026-05-17 17:17 | `0_gt_eval.py` 输出。|
| `1_.parquet` | 2026-05-17 16:04 | 老链路第 1 步快照。|
| `2_.parquet` | 2026-05-17 16:15 | 老链路第 2 步快照。|
| `2_1.parquet` | 2026-05-17 16:51 | 第 2 步多次跑的版本 1。|
| `2_2.parquet` | 2026-05-17 17:10 | 第 2 步多次跑的版本 2。|
| `3_eval_result.parquet` | 2026-05-17 16:41 | `3_eval.py` 主输出。|
| `3_1_eval_result.parquet` | 2026-05-17 16:52 | 多次评测的版本 1。|
| `3_2_eval_result.parquet` | 2026-05-17 17:12 | 多次评测的版本 2。|
| `step4_eval_result.parquet` | 2026-05-17 17:35 | 老链路 step4 评测产物（与 `mix_data/` 中同名文件不一定一致）。|
| `test_with_priv_query.parquet` | 2026-05-17 15:34 | 老链路输入快照。|
| `todo.md` | 2026-05-17 16:27 | 老链路 TODO。|

---

## 典型运行顺序速记

新一个模型 checkpoint 来了，想得到完整指标：

```text
   ┌─────────────────────────────────────────────────────────────┐
   │  test_with_priv_query.parquet  (含原始 question + priv_query)│
   └─────────────────────────────────────────────────────────────┘
                          │
                          ▼
        mix_data/6_drop_top50.py    （可选：先剔 wild top-50）
                          │
                          ▼
        mix_data/0_add_gpt_answer.py   （把 0_gt_ref.parquet 的 gpt_answer 接上）
                          │
                          ▼
        mix_data/1_inference.py        （priv_query → privq_gpt_answer，GPT-4o）
                          │
                          ▼
        mix_data/2_merge_inference.py  （部署模型 merge 推理，按 ability 选模板）
                          │
                          ▼
   ┌────────────────────────────┬──────────────────────────────┐
   │ mix_data/3_eval.py          │ mix_data/4_anoy.py            │
   │ → 答案质量（Med 准确率 +    │ → priv_query PII 打标          │
   │   privacy/wild Q_AL 平均）  │   ↓                            │
   └────────────────────────────┘ 0_privacy/0_eval_by_ability*.py│
                                 │ → PII / NE 泄漏率 + ea 保留率 │
                                 └──────────────────────────────┘
```

如果要做 LLM-as-Judge 形式的"我们 vs baseline"对比，则把上一步产物拷到 `llm_test_data/` 后跑 [judge/0_judge_gpt4o_mini.py](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/judge/0_judge_gpt4o_mini.py)。

