
# `pupa/` 目录说明

本目录用于在 **PUPA (PAPILLON benchmark)** 数据集上复现 / 评测“本地模型重写 query → 远程强模型回答 → 本地模型整合”这条隐私委托 pipeline，并同时评估两个核心指标：

- **QUAL（质量保持）**：最终回答 `merge_inference_answer` 是否至少和 GPT-4o 直接回答原始问题（`gpt_answer`）一样好。
- **LEAK（隐私泄漏）**：本地重写出的 `priv_query` 中是否仍然残留原始 `question` 里的 PII。

> ⚠️ **关于文件命名的提醒**：本目录下的文件名前缀（`0_`、`1_`、`2_`、`3_`、`5_`、`step5_`）**并不严格等于执行先后顺序**，有几个名字会误导。请以下文“真实执行顺序”为准。

---

## 真实执行顺序（pipeline）

```
                                    PUPA_TNB.csv
                                          │ (本目录已经预生成好)
                                          ▼
                       PUPA_TNB_with_priv_query.parquet
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
   step ①  1_inference.py                              step ⑤(评测B) step5_privacy.py
   读 PUPA_TNB_with_priv_query.parquet                 读 1_.parquet
   用 GPT-4o 对 priv_query 给出参考答案                 计算 priv_query 对原始 PII 的 LEAK
   写 1_.parquet（新增 privq_gpt_answer 列）            写 5_eval_.parquet
                  │
                  ▼
   step ②  2_merge_inference.py
   读 1_.parquet
   用本地部署模型（llama_inference）合并 question + priv_query + privq_gpt_answer
   写 2_.parquet（新增 merge_inference_answer 列）
                  │
                  ▼
   step ③  0_inference_gt.py   ← 名字带 0_，但它在 pipeline 里跑在 ② 之后
   读 2_.parquet
   用 GPT-4o 直接回答原始 question，作为评测时的“目标答案”C_T
   写 2_.parquet（新增 gpt_answer 列，**就地原地覆盖**）
                  │
                  ▼
   step ④(评测A) 3_eval.py
   读 2_.parquet
   按 ability 分流：
     - privacy → 成对裁判（merge_inference_answer vs gpt_answer，含 swap）→ Q_AL
     - Med     → 单选一致性（merge_inference_answer 与 extra_info.answer_label 比对）→ accuracy
   写 3_eval.parquet（每行打分明细）
```

---

## 文件清单

### 一、数据文件

| 文件 | 大小 | 角色 | 关键列 |
| --- | --- | --- | --- |
| `PUPA_TNB.csv` | 875 KB | **原始数据集**。来自 PAPILLON 论文里 PUPA-TNB 子集，每行一条真实带 PII 的用户 query。 | `conversation_hash`, `user_query`, `target_response`, `pii_units`（用 `\|\|` 分隔的 PII spans）, `redacted_query` |
| `PUPA_TNB_with_priv_query.parquet` | 886 KB | 在 `PUPA_TNB.csv` 基础上，**已经预生成好 `priv_query` 列**（即 PAPILLON Prompt-Creator 重写后的隐私化提问）。这是整条 pipeline 的真正起点。 | 上面所有列 + `priv_query`, `extra_info`(含 `question`/`answer_label`/`index`), `ability`(`privacy` / `Med`) |
| `1_.parquet` | 1.11 MB | step ① 输出。在 `PUPA_TNB_with_priv_query.parquet` 上新增 `privq_gpt_answer` 列（GPT-4o 对 `priv_query` 的参考答案）。 | + `privq_gpt_answer` |
| `2_.parquet` | 1.37 MB | step ② / step ③ 的产物。**先**被 `2_merge_inference.py` 写入 `merge_inference_answer`，**再**被 `0_inference_gt.py` 就地补上 `gpt_answer`。是 step ④ 评测的核心输入。 | + `merge_inference_answer`, + `gpt_answer` |
| `3_eval.parquet` | 437 KB | `3_eval.py` 输出的逐行打分明细：`ability`/`user_query`/`answer_label`/`response_A`/`response_B`/`s1`/`s2`/`score`。 | 评测结果 |
| `5_eval_.parquet` | 235 KB | `step5_privacy.py` 输出的逐行 PII 泄漏明细：`pii_items`/`pii_leak_flags`/`pii_coverage`/`pii_bert_p`/`n_pii_leak`/`sample_leak`。 | 隐私评测结果 |
| `0_.parquet` | 1.22 MB | **历史遗留 / 未被当前任何脚本读写**。从大小和命名看是早期版本的中间产物，保留只是为了对照。当前 pipeline 不要依赖它。 | — |
| `0_.parquet.bak` | 1.22 MB | `0_.parquet` 的备份。同样不参与 pipeline。 | — |

### 二、脚本文件

#### `1_inference.py` —— step ①：用 GPT-4o 给 `priv_query` 生成参考答案

- 输入：`PUPA_TNB_with_priv_query.parquet`
- 输出：`1_.parquet`，新增列 `privq_gpt_answer`
- 调的是腾讯 Venus 代理的 `gpt-4o`（HTTP，非流式），16 路并发，自带重试。
- system prompt 要求把 `priv_query`（隐私化后、可能信息缺失）当作真实问题尽量回答，不要追问、不要谈隐私 —— 产出的是供下一步合并用的“参考资料”，对应论文里强模型那一路的输出。
- 命名对应论文里的 `M_REMOTE`（远程强模型）这一调用环节。

#### `2_merge_inference.py` —— step ②：本地模型 Information Aggregator

- 输入：`1_.parquet`（必须含 `priv_query`/`privq_gpt_answer`/`extra_info`/`ability`）
- 输出：`2_.parquet`，新增列 `merge_inference_answer`
- 调的是内部 SSE 服务 `llama_inference`（`http://21.119.245.18:81/...`），手写 SSE 解析（避免 `sseclient` 丢包）。
- 按 `ability` 选模板：
  - `ability == "privacy"` → `PROMPT_TEMPLATE_privacy`（自由问答，融合 `helpfulInformation` 写最终答案）。
  - `ability == "Med"` → `PROMPT_TEMPLATE_Med`（单选题模式，强制只输出 `<option letter>. <option text>`）。
  - 未知值 fallback 到 privacy 模板。
- 支持 `--input/--output/--workers/--limit/--resume`，`--resume` 会从上次输出里挑出非 `[ERROR]` 的行复用。
- 这一步对应论文里 `M_LOCAL` 的 Information Aggregator。

#### `0_inference_gt.py` —— step ③：给评测准备 GPT-4o 的“目标答案”

- ⚠️ **名字带 `0_` 极易误导**。它看起来像 step 0，但实际是在 step ② 跑完之后才执行。
- 输入：`2_.parquet`（在 `INPUT_PATH` 写死）
- 输出：**就地写回** `2_.parquet`（`OUTPUT_PATH` 与 `INPUT_PATH` 相同），新增列 `gpt_answer`
- 直接用 GPT-4o 回答 `extra_info["question"]`（即 **未经隐私化** 的原始问题），作为 `3_eval.py` 里 pairwise 评测的 reference answer `C_T`。
- system prompt 是简单的 “直接给答案，不解释”。
- 不要在没跑完 step ② 的情况下执行；同时注意它会原地覆写 parquet。

#### `3_eval.py` —— step ④（评测 A）：QUAL 指标

- 输入：`2_.parquet`（必须已经同时具有 `merge_inference_answer` 和 `gpt_answer`）
- 输出：`3_eval.parquet`
- 按 `ability` 分两路：
  - **privacy** → 成对裁判 `Q_AL`：让 GPT-4o 判断 `merge_inference_answer (A)` vs `gpt_answer (B)` 哪个更好，再 swap 角色再判一次；两次结果相同时 `score=1`，否则取 `s1`。这就是 PAPILLON 论文里 QUAL 指标的实现。
  - **Med** → 让 GPT-4o 判断 `merge_inference_answer` 选的选项是否等于 `extra_info["answer_label"]`，输出 1/0 → 报告 accuracy。
- 边界处理：A/B 同时为空算 1，A 空 B 非空算 0，A 非空 B 空算 1（不调 LLM）。
- 终端打印各 ability 的 count 和均值，并随机打 2 条样例方便人工抽检。

#### `step5_privacy.py` —— step ⑤（评测 B）：LEAK 指标，**独立分支**

- ⚠️ 输出文件叫 `5_eval_.parquet`，但它跟 step ②/③/④ **不在同一条链路上**：它直接读 `1_.parquet`，**不依赖** `merge_inference_answer` 或 `gpt_answer`。可以在 step ① 完成后立即跑。
- 输入：`1_.parquet`（必须含 `priv_query` 和 `pii_units`）
- 输出：`5_eval_.parquet`
- 复用了 `z_eval/eval_privacy/com_privacy_score.py` 里训练时奖励函数的 leak 判定原语（`coverage`、`_bert_p_rescaled`、`_get_bert_scorer`），保证跟训练时奖励完全对齐：
  - **lexical**：`coverage(priv_query, pii_item) >= 1.0` → 算泄漏。
  - **semantic**：`BERTScore P_rescaled(pii_item, priv_query) > 0.3` → 算泄漏。
  - 任一条件命中即视为该 PII 单元已泄漏。
- 会自动过滤掉看起来像选择题选项串（如 `A. xx B. yy ...`）这种伪 PII。
- 报告两个粒度：
  - 样本级：至少有一个 PII 泄漏的样本数 / 总样本数。
  - PII 项级：泄漏的 PII 项数 / 总 PII 项数。
- 支持 `--no_bert`（仅 Jaccard）和 `--limit N`。

### 三、文档文件

#### `paper_key.md`
PAPILLON 论文（*PrivAcy Preservation from Internet-based and Local Language MOdel ENsembles*）的中文要点摘录：任务定义（Privacy-Conscious Delegation）、PUPA benchmark 来源与规模、PAPILLON baseline 双模块（Prompt Creator + Information Aggregator）、QUAL/LEAK 评测设计、主要实验数字、以及局限性。这里所有脚本的设计都对照这份要点来理解最直观。

---

## 各文件最近更新时间

下表按 **pipeline 真实执行顺序** 排列（时间为本地时区，来自文件系统 mtime）：

| 文件 | 上次更新时间 | 备注 |
| --- | --- | --- |
| `paper_key.md` | 2026-05-17 22:19:23 | 论文要点笔记，最早建立 |
| `PUPA_TNB.csv` | 2026-05-17 22:06:06 | 原始数据，最早建立 |
| `PUPA_TNB_with_priv_query.parquet` | 2026-05-17 22:35:43 | 含 `priv_query` 的 pipeline 起点数据 |
| `1_inference.py` | 2026-05-17 22:39:03 | step ① 脚本 |
| `1_.parquet` | 2026-05-17 22:40:14 | step ① 输出 |
| `2_merge_inference.py` | 2026-05-17 22:48:54 | step ② 脚本 |
| `3_eval.py` | 2026-05-17 22:51:16 | step ④ 脚本 |
| `0_inference_gt.py` | 2026-05-17 22:52:07 | step ③ 脚本（mtime 晚于 step ②/④ 脚本，印证它实际跑在 step ② 之后） |
| `2_.parquet` | 2026-05-17 22:52:53 | step ②→③ 共同写出的最终 parquet |
| `3_eval.parquet` | 2026-05-17 22:54:39 | step ④ QUAL 评测结果 |
| `0_.parquet.bak` | 2026-05-17 22:57:06 | 历史遗留备份，不在主链路上 |
| `0_.parquet` | 2026-05-17 22:57:07 | 历史遗留产物，不在主链路上 |
| `step5_privacy.py` | 2026-05-17 23:18:13 | step ⑤ 脚本（最后改的脚本） |
| `5_eval_.parquet` | 2026-05-17 23:18:41 | step ⑤ LEAK 评测结果（最后产出的数据） |

从时间戳能直接读出来的几个事实：

1. 整套代码与数据基本是在 **2026-05-17 22:06 ～ 23:19** 这一个多小时内一次性产出的，之后再没改过。
2. `0_inference_gt.py`（22:52:07）的 mtime **晚于** `2_merge_inference.py`（22:48:54）和 `3_eval.py`（22:51:16），从时间上佐证了它在 pipeline 里**确实是 step ③**，与 `0_` 的命名前缀不一致。
3. `2_.parquet`（22:52:53）紧跟 `0_inference_gt.py` 写出，正是后者把 `gpt_answer` 列就地补回去后的产物，**晚于** `2_merge_inference.py` 写出的中间版本。
4. `0_.parquet` / `0_.parquet.bak`（22:57）的 mtime 晚于主链路的 `3_eval.parquet`（22:54），进一步说明它们是事后留下的副产物，不属于当前 pipeline。
5. `step5_privacy.py` 与 `5_eval_.parquet` 是 23:18 才补做的，比主线晚约 24 分钟 —— 这与它"独立分支、只依赖 step ① 输出"的角色是一致的。

---

## 快速复跑

```bash
cd /group/40047/eiraxyhuang/workspace/fc/DataG/pupa

# step ①  生成 privq_gpt_answer
python 1_inference.py

# step ②  本地模型合并出 merge_inference_answer
python 2_merge_inference.py            # 可加 --resume / --limit N / --workers K

# step ③  给原始 question 打上 GPT-4o 目标答案 gpt_answer（就地写回 2_.parquet）
python 0_inference_gt.py

# step ④  QUAL 评测
python 3_eval.py

# step ⑤  LEAK 评测（与 ②③④ 并行，只依赖 step ① 的输出）
python step5_privacy.py
```

## 已知坑位

1. `0_inference_gt.py` 的命名容易让人以为是 pipeline 第一步，实际是 step ③；它会**就地覆写** `2_.parquet`，跑前最好备份。
2. `step5_privacy.py` 输出名叫 `5_eval_.parquet`，但它读的是 `1_.parquet`，**和 `3_eval.py` 完全是独立分支**，不要误以为它需要先跑完 `3_eval.py`。
3. `0_.parquet` / `0_.parquet.bak` 是历史产物，**当前 pipeline 完全不读不写**，请勿据此推断流程。
4. `1_inference.py` 和 `0_inference_gt.py` 都会调 GPT-4o，但作用完全不同：前者回答的是隐私化后的 `priv_query`（生成 `privq_gpt_answer`，作为 step ② 的"参考资料"），后者回答的是原始 `question`（生成 `gpt_answer`，作为 step ④ 的"评测目标"），不要把两列搞混。
5. `2_.parquet` 在 step ② 和 step ③ 都会被写入（先加 `merge_inference_answer`，再加 `gpt_answer`），中途如果中断，列可能不全，重跑相应步骤即可恢复。
6. 几个脚本里的 `TOKEN` 是写死的明文，不要外传。
