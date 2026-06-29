
# `papillon/` 目录说明

> 这是 PAPILLON 流水线 ([skills.md](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/skills.md)) 的 **当前主版本**。同目录树下还有三个并行版本：`papillon_old/`、`papillon_pupa/`、`papillon_privacy/`，关系详见每个目录自己的 README，本 README 末尾也有简表。

## 1. 流水线概述

PAPILLON 把"用户原始 query → LLM 答案"这一步拆成 5 步，让本地小模型只看到隐私化后的 query，让远程大模型只看到隐私化后的答案，再用本地模型把信息聚合回来：

```
extra_info["question"] = q              ──┐
                                          ▼
   step1_creator.py        本地模型 (qwen523) + Creator prompt   →  priv_query (q')
                                          ▼
   step2_remote.py         远程模型 (gpt-4o) 回答 q'              →  remote_answer (CR)
                                          ▼
   step3_aggregator.py     本地模型把 (q, CR) 融合                →  final_answer (CL)
                                          ▼
   step4_1_eval.py         按 ability 分桶评测 final_answer       →  step4_eval_result
                                          ▼
   step5_anoy.py           用 Presidio 给 question 打 PII 标签    →  question_pii_entities
```

> ⚠️ 注意：
> - 文件名里的 `step1 / step2 / ...` **不是依赖关系**，只是运行顺序前缀。
> - 所谓 `5_*.parquet` (`5_qwen / 5_llama / 5_ds`) 是 step5 输出的 PII 打标版，前缀的 `5` 同样只是顺序。
> - **本目录是从 `papillon_old/` 演化来的**：相对老版多了「Med 能力支持」「qwen523 / qwen7b 模型对照」「step5_anoy（Presidio PII 打标）」「Med 选项字母强制保留」「评测时把 wild 与 privacy 同样走 Q_AL pairwise」等改动。
>
> 历史上为什么会被复制成多个目录、每个目录现在的角色，见末尾的 [§4 与其他 papillon_* 目录的关系](#4-与其他-papillon_-目录的关系)。

---

## 2. 脚本

> 时间列是文件 `mtime`，能直接看出每段代码最后一次实际变更发生在哪天。

| 脚本 | 上次更新 | 作用 |
|---|---|---|
| [prompt.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/prompt.py) | 2026-05-19 21:06 | 定义两段核心 prompt：`Creator`（让本地模型把 q 改写成隐私保护版 q'，要求结构化输出 `[[[ ### createdPrompt ### ]]]` 段）与 `aggregator`（让本地模型把 q + 远端 CR 融合成 finalOutput）。后续脚本都从这里 import。|
| [skills.md](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/skills.md) | 2026-05-19 21:06 | 最初的需求文档，简单描述了 step1-step4 的任务。代码已经在它之外做了大量扩展（Med 支持、step5 等）。|
| [step1_creator.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step1_creator.py) | 2026-05-25 01:25 | **Step 1**：批量遍历输入 parquet，每行从 `extra_info["question"]` 取 q，调用本地服务（默认 `MODEL = "qwen523"`，URL `http://21.119.245.18:81/openapi/chat/completions`，SSE 流式），用 `prompt.Creator` 模板生成 q'，按正则抽取 `createdPrompt` 段写入 **`priv_query`** 列。支持 `--workers / --limit / --resume`。默认 IO：`0_.parquet → step1_qwen523_priv_query.parquet`。|
| [step1_creator_single.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step1_creator_single.py) | 2026-05-19 21:06 | Step 1 的**单条**调试版：`--content / --content-file / stdin` 三选一传入一条 q，打印 q'，方便临时跑 case。这里 MODEL 默认还是 `llama_inference`（不是 `qwen523`），因为只是给手工 debug 用。也提供 `run_single(content)` 让别的脚本 import 用。|
| [step2_remote.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step2_remote.py) | 2026-05-25 01:33 | **Step 2**：拿 step1 输出里每行的 `priv_query`，调用远程 GPT-4o（System prompt 与 inference/inference.py 一致：直接回答，不解释），把答案写入 **`remote_answer`** 列。默认输入 `step1_qwen523_priv_query.parquet → step2_remote_answer.parquet`。|
| [step3_aggregator.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step3_aggregator.py) | 2026-05-25 02:14 | **Step 3**：本地模型（`MODEL = "qwen523"`，`MAX_WORKERS=20`）拿 (q, remote_answer)，套 `prompt.aggregator` 模板生成最终回答 **`final_answer`**。**Med 增强**：当 `ability == "Med"` 时会在 prompt 末尾追加 `MED_LETTER_INSTRUCTION`，强制保留选项字母 `B. Quinidine` 这种格式，避免 step4 单选 judge 因为掉字母而误判。默认 `step2_remote_answer.parquet → step3_final_answer.parquet`。|
| [step4_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step4_eval.py) | 2026-05-19 21:06 | **早期版** Step 4：只做 privacy 一类——把 `final_answer` 当 C_L、`gpt_answer` 当 C_T 跑 z_eval 的 Q_AL 双向 pairwise 判定，**没有 Med 分桶**。已经被下面的 `step4_1_eval.py` 取代，仍保留作历史。|
| [step4_1_eval.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step4_1_eval.py) | 2026-05-25 02:19 | **当前主用** Step 4：按 `ability` 分桶评测 `merge_inference_answer/final_answer`。privacy 与 wild **都**走 Q_AL pairwise（`s1==s2 ? 1 : s1`），Med 走 GPT-4o 单选一致性 judge——并且把 user_query（带 A/B/C/D 选项列表）也传给 judge，让自由文本答案能映射回选项字母。默认 `step3_final_answer.parquet → step4_eval_result.parquet`。|
| [step5_anoy.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step5_anoy.py) | 2026-05-25 01:56 | **Step 5**：Presidio 给 `extra_info["question"]` 打 PII 标签，新增 **顶层** 列 `question_anonymized` 与 `question_pii_entities`（list[str]，原文 span）。原来的 `extra_info` 不动。注释里写的输入路径是 `prediax/test_with_priv_query.parquet`，但**实际默认输入是 `step1_qwen523_priv_query.parquet`，输出是 `5_qwen.parquet`**（注释陈旧、以代码为准）。这个脚本和"匿名化 q"无关；它打的是 q 的 PII 实体清单，给后面的隐私泄漏评测当 ground truth。|
| [find_over_abstract.py](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/find_over_abstract.py) | 2026-05-19 21:06 | 离线启发式工具：在 `step1_priv_query.parquet` 里找 **"过度抽象"** 的 q'——即原始 q 带具体 payload（要翻译/调试/写邮件/含引号代码块/邮箱手机号等），但 q' 把它压缩成"提供一份关于 X 的概览"这类空话。靠词典 + 正则打分，输出 top-K 到 stdout 或 jsonl。**不需要模型**，纯规则筛选。|
| [abstract_examples.jsonl](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/abstract_examples.jsonl) | 2026-05-19 21:06 | `find_over_abstract.py --out` 跑出来的 top-K 过度抽象样例，已检查过的人肉 case set，可以拿来评估 Creator 的失败模式。|

---

## 3. 数据文件

> 同一个 `step1_*` 文件名后缀代表不同 Creator 模型的产出，方便横向对比。

### Step 0 / 输入

| 文件 | 上次更新 | 说明 |
|---|---|---|
| [test.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/test.parquet) | 2026-05-19 21:06 | 原始测试集（与 `inference/test.parquet` 同源，含 `extra_info`、`ability` 等）。|
| [0_.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/0_.parquet) | 2026-05-25 01:26 | step1 的实际输入。基于 test.parquet 做了 ability 调整或行筛选后的版本。|

### Step 1 产出（不同 Creator 模型对照）

| 文件 | 上次更新 | Creator 模型 | 备注 |
|---|---|---|---|
| [step1_priv_query.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step1_priv_query.parquet) | 2026-05-20 00:58 | `llama_inference` (llama-3.1-8b-instruct) | `find_over_abstract.py` 的默认输入。|
| [llama_inference_step1_priv_query.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/llama_inference_step1_priv_query.parquet) | 2026-05-20 01:02 | `llama_inference` 的另一份快照 | 与上一份同源，命名不同。|
| [step1_priv_query_qwen7b.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step1_priv_query_qwen7b.parquet) | 2026-05-19 21:55 | `qwen7b` | 早期 qwen 7B 跑出来的 baseline。|
| [step1_qwen523_priv_query.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step1_qwen523_priv_query.parquet) | 2026-05-25 01:33 | `qwen523` | **当前主用**，step2/step3/step5 默认从这里读。|

### Step 2 / 3 产出

| 文件 | 上次更新 | 说明 |
|---|---|---|
| [step2_remote_answer.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step2_remote_answer.parquet) | 2026-05-25 01:38 | 远程 GPT-4o 对 priv_query 的回答 (`remote_answer`)。|
| [step3_final_answer.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step3_final_answer.parquet) | 2026-05-25 02:19 | 本地 aggregator 融合后的最终答案 (`final_answer` / `merge_inference_answer`)。|
| [step4_eval_result.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step4_eval_result.parquet) | 2026-05-25 02:24 | step4_1_eval.py 的 per-row 评测结果（含分桶 score）。|

### Step 5 PII 打标产出（按 Creator 模型分桶）

| 文件 | 上次更新 | 说明 |
|---|---|---|
| [5_.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/5_.parquet) | 2026-05-19 22:20 | 最早一次 Presidio 打标产物（命名最朴素）。|
| [5_llama.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/5_llama.parquet) | 2026-05-20 01:26 | 在 `step1_priv_query.parquet` (llama_inference) 上 Presidio 打标。|
| [5_qwen.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/5_qwen.parquet) | 2026-05-25 01:57 | 在 `step1_qwen523_priv_query.parquet` 上 Presidio 打标，**当前主用**（被 `inference/0_privacy/0_eval_by_ability_excl_wild_top50.py` 引用）。|
| [5_ds.parquet](/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/5_ds.parquet) | 2026-05-20 01:23 | "ds" = DSPy 版 Creator 的产物快照（PAPILLON 原作者的 DSPy 流程跑出来的 priv_query 拿来对比）。|

### Step 5 后续的隐私 / 质量评测产物

| 文件 | 上次更新 | 来源脚本 | 含义 |
|---|---|---|---|
| `5_llama_priv.parquet` / `5_llama_priv.csv` | 2026-05-20 01:40 | `inference/0_privacy/0_eval.py` 类脚本 | 在 `5_llama.parquet` 上跑的 PII / NE 泄漏率 per-row + summary。|
| `5_ds_priv.parquet` / `5_ds_priv.csv` | 2026-05-20 01:29 | 同上 | 在 `5_ds.parquet` 上的隐私评测产物。|
| `5_llama_eval_result.parquet` / `5_llama_eval_result.csv` | 2026-05-20 02:05 | step4_1_eval.py 类 | llama 版的答案质量评测结果。|
| `5_qwen_eval_result.parquet` / `.csv` | 2026-05-20 02:15 | 同上 | qwen 版的答案质量评测结果（早一次的）。|
| `5_qwen_eval_results.parquet` | 2026-05-25 02:00 | 同上 | qwen 版评测的更新版（注意命名多了一个 `s`）。|

---

## 4. 与其他 `papillon_*` 目录的关系

| 目录 | 时间跨度（按目录内文件 mtime） | 角色 |
|---|---|---|
| `papillon_old/` | 2026-05-16 14:39 ~ 2026-05-18 16:08 | 最初实现，**只支持 privacy 一种 ability**，aggregator/eval 都没有 Med 分支。**已弃用**，仅保留作回溯。|
| `papillon_pupa/` | 2026-05-17 22:54 ~ 2026-05-17 23:16（半小时内一次性建好） | 在 `papillon_old/` 基础上换了一份输入数据（自带 `pii_units` 列），并多写了 `step5_privacy.py` 给 priv_query 算 PII 泄漏率。**和 papillon_old 几乎同构，是中间过渡版**。|
| `papillon_privacy/` | 2026-05-17 20:49（同一天三个文件一次落盘后冻结） | 只有 1 个评测脚本 `0_eval.py`，专门评 **`pp_priv_query`** 列（papillon 后处理过的 priv_query）相对原 question 的 PII / NE 泄漏率 + ea 保留率。和 inference/0_privacy/0_eval.py 是同一份脚本的复制+列名替换版。|
| **`papillon/`**（本目录） | 2026-05-19 21:06 ~ 2026-05-25 02:24 | 现役主版本：Med 能力支持、qwen523/qwen7b/llama 三套 Creator 对比、step5 PII 打标、Med 选项字母强制保留、wild 与 privacy 共用 Q_AL pairwise。**新工作请直接用本目录。** |

> 时间线放一起看：5/16 起 `papillon_old` 第一版；5/17 同一天里先在 `papillon_privacy` 落了一组隐私评测产物（20:49），然后晚上 22:54–23:16 在 `papillon_pupa` 把 papillon_old + step5_privacy 跑了一遍快照；5/19 起整个目录被 fork 成 `papillon/` 继续迭代到 5/25。

