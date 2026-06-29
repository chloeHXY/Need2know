# Med_data_expand

> 📅 文件最后修改时间快照采集于 **2026-06-29**（来自 `ls -la --time-style=long-iso`）。

本目录用于将原始医学多选题数据集（`medical_o1_sft_mcq.json`）逐步加工成最终用于训练 / 评测的隐私改写数据集（`med.final.*.parquet`）。整体流程是一条按文件名前缀编号串起来的 **流水线**：每个脚本读取上一阶段产出的 Parquet/JSONL，加工后写到下一阶段的 Parquet/JSONL。

> ⚠️ 文件名仅作流水线顺序编号，**不要望文生义**。例如：
> - `4_打标.py` 实际是「调用 GPT-4o 对 `prompt` 字段做推理，写入 `extra_info.query_gt`」，跟「打标签」没关系。
> - `5_答案打标.py` 才是真正的「打 ABCDE 选项标签」。
> - `6_simplify_pii_entities.py` 与 `6_1/6_2/6_3_*.py` 编号同为 6，但作用各不相同（见下文）。
> - `1_med2.parquet` / `2_.parquet` / … / `5_.parquet` 这些 Parquet 文件并非由本目录的 Python 脚本直接生成 —— 它们是 **上一编号脚本写出的产物**，被下一个编号的脚本作为输入消费。

---

## 一、流水线总览

```
medical_o1_sft_mcq.json
        │
        │  0_label.py            (标注 key-evidence-spans，调用 GPT-4o)
        ▼
labels/labels_gpt-4o_*.jsonl
        │
        │  1_synthesize_question.py  (用 prompt2.py 改写 Question -> Syn_Question)
        ▼
syn_questions/med2.jsonl   ──►  1_med2.parquet  (外部转换为 Parquet 后作为流水线起点)
        │
        │  2_anonymize.py        (Presidio 检测 PII)
        ▼
2_.parquet
        │
        │  3_clean_pii_entities.py   (按规则过滤 PII 实体)
        ▼
3_.parquet
        │
        │  4_打标.py             (GPT-4o 对 prompt 推理 -> extra_info.query_gt)
        ▼
4_.parquet
        │
        │  5_答案打标.py         (GPT-4o 把自然语言答案归到 A/B/C/D/E)
        ▼
5_.parquet                       (备份: 5_.bak.parquet)
        │
        │  6_simplify_pii_entities.py    (entity dict -> 仅文本字符串)
        │  6_1_strip_key_spans_reason.py (key_spans 去掉 reason)
        │  6_2_remove_age_spans.py       (key_spans 去掉「xx-year-old」)
        │  6_3_fill_ground_truth.py      (query_gt -> reward_model.ground_truth)
        ▼
5_.parquet (就地覆盖)
        │
        │  7_最终处理.py         (字段重命名、划分 train/test)
        ▼
med.final.parquet
med.final.train.parquet
med.final.test.parquet  (med.final.test.600.parquet 为下游手动截取的子集)
        │
        │  (推理改写阶段在别处执行，得到 med_with_priv_query.parquet)
        ▼
med_with_priv_query.parquet
        │
        │  8_eval_ea_ne.py       (评测 priv_query 的 ne 泄漏率 / ea 保留率)
        ▼
tem.parquet
```

---

## 二、Python 脚本

各脚本最后修改时间一览（按文件名排序）：

| 脚本 | 最后修改时间 |
| --- | --- |
| `0_label.py` | 2026-05-18 00:15 |
| `1_synthesize_question.py` | 2026-05-18 00:26 |
| `2_anonymize.py` | 2026-05-18 00:41 |
| `3_clean_pii_entities.py` | 2026-05-18 00:44 |
| `4_打标.py` | 2026-05-18 00:48 |
| `5_答案打标.py` | 2026-05-18 00:53 |
| `6_simplify_pii_entities.py` | 2026-05-18 00:57 |
| `6_1_strip_key_spans_reason.py` | 2026-05-18 00:58 |
| `6_2_remove_age_spans.py` | 2026-05-18 00:59 |
| `6_3_fill_ground_truth.py` | 2026-05-18 01:05 |
| `7_最终处理.py` | 2026-05-18 01:09 |
| `8_eval_ea_ne.py` | 2026-05-19 16:54 |
| `prompt2.py` | 2026-05-18 00:24 |

---

### `0_label.py`
**关键证据片段标注（key-evidence spans labelling）。**

- 输入：`medical_o1_sft_mcq.json`（顶层为列表，每项含 `Question` / `Complex_CoT` / `Response`）。
- 处理：用 `data/o1/prompt.py` 中的模板渲染 prompt，并发调用 GPT-4o（默认走腾讯内部 Venus 代理 `ENV_VENUS_OPENAPI_SECRET_ID`），让模型返回 JSON：`answer_summary` + `key_spans` 等字段。
- 输出：`labels/labels_gpt-4o_start{start}_n{n}_{ts}.jsonl`，并在旁边写一份 `*.usage.json` 记录 token / 美元成本。
- 去重：默认会跳过 `labels_gpt-4o_start0_n500_20260515_101049.jsonl` 中已经标注过的条目（按 `index` 与 `Question` 文本双重去重）。
- 用法示例：
  ```bash
  export ENV_VENUS_OPENAPI_SECRET_ID=<your-key>
  python 0_label.py --n 1000 --start 0 --concurrency 8
  ```

### `1_synthesize_question.py`
**将 `Question` 改写为带合成 PII 的 `Syn_Question`。**

- 输入：`0_label.py` 产出的 labels JSONL（默认是 `labels/labels_gpt-4o_start0_n1000_20260518_001557.jsonl`）。
- 处理：以 `prompt2.py` 为模板，让 GPT-4o 在保留所有医学要素（年龄、症状、化验、答案选项……）的前提下，注入合成的 PII（合成姓名、病历号、诊所 ID、example.com 邮箱、虚假电话号、中性职业等）。
- 输出：`syn_questions/syn_<input-stem>_start{start}_n{n}_{ts}.jsonl`，每条记录在原 label 字段上额外追加 `Syn_Question` / `syn_question_raw` / `syn_endpoint` / `syn_usage` / `syn_ok` / `syn_error`。同时输出 `*.usage.json`。
- 用法示例：
  ```bash
  python 1_synthesize_question.py --n 1000 --concurrency 8
  ```

### `2_anonymize.py`
**用 Microsoft Presidio 检测 `extra_info.question` 中的 PII。**

- 输入：`1_med2.parquet`（包含 `extra_info` 字典列；`question` 即上一步生成的 `Syn_Question`）。
- 处理：`AnalyzerEngine` 检测，`AnonymizerEngine` 生成脱敏文本。
- 输出：`2_.parquet`。在每行的 `extra_info` 字典里追加：
  - `question_anonymized`：脱敏后的问题文本；
  - `question_pii_entities`：实体列表（`entity_type` / `start` / `end` / `score` / `text`）。
- 用法：
  ```bash
  python 2_anonymize.py --input 1_med2.parquet --output 2_.parquet
  ```

### `3_clean_pii_entities.py`
**按白名单/正则规则过滤 PII 实体。**

- 输入：`2_.parquet`。
- 保留规则：
  - `PERSON` / `US_DRIVER_LICENSE` / `US_BANK_NUMBER`：全部保留；
  - `DATE_TIME`：只保留形如 `45-year-old` / `3-month-old` 这种「年龄」表达；
  - `LOCATION`：仅在内置白名单（`india`, `europe`, `usa`, `singapore`, …）命中时保留；如果是 MCQ 选项前缀 `A. Norway`，会去掉 `A. ` 并把 `start/end` 重新对齐到地名本身。
- 丢弃：`NRP` / `US_PASSPORT` / `US_ITIN` / `URL` / `PHONE_NUMBER` 以及不符合上述规则的条目。
- 输出：`3_.parquet`。

### `4_打标.py` ⚠️名称误导
**并非「打标签」，而是「调用 GPT-4o 对 `prompt` 字段做推理，把回答写入 `extra_info.query_gt`」。**

- 输入：`3_.parquet`。
- 处理：把每行的 `prompt`（chat messages）转成纯 list[dict]，并发请求 Venus 代理上的 GPT-4o（最多 16 并发，3 次重试）。注意 token 是脚本里硬编码的 `TOKEN`（建议改为读取环境变量）。
- 输出：`4_.parquet`，每行 `extra_info.query_gt` 即模型生成的开放式回答。
- 参考：`/group/40047/eiraxyhuang/workspace/fc/DataG/inference/inference_gt.py`。

### `5_答案打标.py`
**真正的 ABCDE 选项标签器。**

- 输入：`4_.parquet`。每行的 `extra_info.question` 是单选题，`extra_info.answer` 是自然语言解释。
- 处理：用 `PROMPT_TEMPLATE` 让 GPT-4o 严格输出 `A/B/C/D/E/UNKNOWN` 一个字母（`temperature=0`，`output_seq_len=16`），再用正则 `normalize_label` 兜底。
- 输出：`5_.parquet`，在 `extra_info` 中追加：
  - `answer_label`：A/B/C/D/E 或 UNKNOWN；
  - `answer_label_raw`：模型原始输出（用于调试）。
- 流水线产物中存在 `5_.bak.parquet`，是 `6_2_remove_age_spans.py` 在原地覆盖前自动备份的版本。

### `6_simplify_pii_entities.py`
**把 `extra_info.question_pii_entities` 从「实体 dict 列表」简化为「纯文本字符串列表」。**

- 默认输入/输出都是 `5_.parquet`（**就地覆盖**）。
- 仅保留每个实体的 `text` 字段，丢弃 `entity_type` / `start` / `end` / `score`。

### `6_1_strip_key_spans_reason.py`
**剥离 `extra_info.key_spans` 里的 `reason` 字段。**

- 原本 `key_spans` 是 `[{"reason": "...", "span": "..."}, ...]`，处理后只保留 `span` 字符串组成的列表。
- 默认输入/输出都是 `5_.parquet`（**就地覆盖**）。

### `6_2_remove_age_spans.py`
**从 `extra_info.key_spans` 中删除年龄类字符串。**

- 用正则 `(year|month|week|day|hour|minute|yr|mo|wk|hr|min)s?[\s\-]*old` 命中诸如 `"45-year-old"`、`"3 month old"`、`"2 yrs old"` 等表述。
- 第一次运行时会自动把原 `5_.parquet` 备份为 `5_.bak.parquet`，再原地覆盖 `5_.parquet`。

### `6_3_fill_ground_truth.py`
**用 `extra_info.query_gt` 填充 `reward_model.ground_truth`。**

- `reward_model` 的其他键（如 `style`）保持不变。
- 若 `query_gt` 缺失/为空则跳过并打印告警。
- 默认就地覆盖 `5_.parquet`，可通过 `--output` 改写到别处。

### `7_最终处理.py`
**最后一步字段重排 + 数据集划分。**

- 输入：`5_.parquet`。
- 操作：
  1. `extra_info.question_pii_entities` 重命名为 **`ne`**（non-essential，不应泄漏到改写后的 query 中）；
  2. `extra_info.key_spans` 保持为 `key_spans`（在评测中作为 **`ea`** 即 essential 的来源使用）；
  3. 用 `extra_info.query_gt` 覆盖 `extra_info.answer`；
  4. 给每行加 `extra_info.origin_ea = []`（占位）；
  5. 按 `RANDOM_SEED=42` 划分 train / test，比例为 `TRAIN_SIZE=0` / `TEST_SIZE=1000`，写入 `extra_info.split`，并同步暴露为顶层列 `split`。
- 输出：
  - `med.final.parquet`：完整数据；
  - `med.final.train.parquet`：split=train（默认 0 行，仅占位）；
  - `med.final.test.parquet`：split=test（1000 行）。

### `8_eval_ea_ne.py`
**评测改写后的 `priv_query` 的隐私泄漏率与效用保留率。**

- 输入：`med_with_priv_query.parquet`（由其他推理脚本生成，包含 `priv_query` 列与含 `ne` / `key_spans` 的 `extra_info`）。
- 评判标准与训练时奖励完全对齐（复用 `z_eval/eval_privacy/com_privacy_score.py` 中的 `coverage` / `_bert_p_rescaled`）：
  - **ne 泄漏**：`coverage(priv_query, ne) >= 1.0` 或 `BERTScore P_rs > 0.3` 即视为泄漏；
  - **ea 保留**：`coverage(priv_query, ea) >= 0.5` 或 `BERTScore P_rs > 0.3` 即视为保留。
- 报告：样本级泄漏率（按全量 / 仅含 ne 的子集）、ne item 泄漏率、ea item 保留率。
- 输出：
  - `--output`（默认 `tem.parquet`）：每行打分明细；
  - `--noleak_output`（默认也是 `tem.parquet`，**会被覆盖**，可在调用时改名）：`n_ne_leak == 0` 的无泄漏子集。
- 可选：`--no_bert` 关闭 BERTScore，仅用 Jaccard；`--limit N` 只评测前 N 行。

### `prompt2.py`
被 `1_synthesize_question.py` 引用的 prompt 模板，定义了模块级字符串 `input`，里面有一个 `{{Question}}` 占位符。它详细规定了：

- **必须保留**：年龄、性别、症状、体征、化验、影像、诊断、用药剂量、病史、答题选项、正确答案……
- **可以新增**：合成姓名、病历号、就诊号、`example.com` 邮箱、明显假的电话、中性职业……
- **禁止新增**：种族、真实地理位置、家族史、旅行史、性史、物质使用、饮食、运动、妊娠、疫苗、社会经济、环境暴露、新症状/新疾病……

---

## 三、数据文件

| 文件 | 大小 | 最后修改时间 | 说明 |
| --- | --- | --- | --- |
| `medical_o1_sft_mcq.json` | 11.3 MB | 2026-05-18 00:08 | **原始数据集**，FreedomIntelligence/medical-o1-reasoning-SFT 的 MCQ 子集，列表，每项含 `Question` / `Complex_CoT` / `Response`。 |
| `labels_gpt-4o_start0_n500_20260515_101049.jsonl` | 2.9 MB | 2026-05-18 00:09 | 早期一次 500 条的标注结果，主要作用是作为 `0_label.py` 的去重排除集。 |
| `labels/labels_gpt-4o_start0_n1000_20260518_001557.jsonl` | 5.95 MB | 2026-05-18 00:23 | `0_label.py` 主标注结果（1000 条，含 key_spans / answer_summary）。 |
| `labels/labels_gpt-4o_start0_n1000_20260518_001557.usage.json` | 370 B | 2026-05-18 00:23 | 上述标注的 token / cost 报告。 |
| `syn_questions/med2.jsonl` | 7.46 MB | 2026-05-18 00:30 | `1_synthesize_question.py` 输出的合成 PII 改写结果。**`1_med2.parquet` 即是它转 Parquet 后的版本**，作为后续流水线的实际起点。 |
| `syn_questions/syn_labels_gpt-4o_..._20260518_002645.usage.json` | 669 B | 2026-05-18 00:30 | 上一步的 LLM 用量 / 成本报告。 |
| `1_med2.parquet` | 6.35 MB | 2026-05-18 00:39 | 流水线起点（包含 `prompt` / `extra_info` / `reward_model` 等列，`extra_info.question` 即合成 PII 改写后的题目）。 |
| `2_.parquet` | 2.10 MB | 2026-05-18 00:42 | `2_anonymize.py` 输出，新增 `extra_info.question_anonymized` / `question_pii_entities`。 |
| `3_.parquet` | 2.09 MB | 2026-05-18 00:44 | `3_clean_pii_entities.py` 输出，按规则过滤后的 PII 实体。 |
| `4_.parquet` | 2.22 MB | 2026-05-18 00:50 | `4_打标.py` 输出，新增 `extra_info.query_gt`（GPT-4o 开放式作答）。 |
| `5_.parquet` | 1.84 MB | 2026-05-18 01:05 | 经过 `5_答案打标.py` + `6_*` 系列脚本就地修改后的最终单文件成果（含 `answer_label`、简化版 PII / key_spans，且 `reward_model.ground_truth` 已被 `query_gt` 填充）。 |
| `5_.bak.parquet` | 1.99 MB | 2026-05-18 00:58 | `6_2_remove_age_spans.py` 第一次运行时自动制作的备份。 |
| `med.final.parquet` | 1.70 MB | 2026-05-18 01:09 | `7_最终处理.py` 输出的完整最终数据集。 |
| `med.final.train.parquet` | 3.02 KB | 2026-05-18 01:09 | 训练集（默认 0 条，仅占位）。 |
| `med.final.test.parquet` | 1.70 MB | 2026-05-18 01:09 | 测试集（1000 条）。 |
| `med.final.test.600.parquet` | 1.01 MB | 2026-05-19 19:14 | 下游手动截取的 600 条测试子集。 |
| `med_with_priv_query.parquet` | 1.79 MB | 2026-05-19 16:37 | 在外部推理脚本里跑出 `priv_query`（隐私改写后的查询）后得到的评测输入。 |
| `tem.parquet` | 511 KB | 2026-05-19 16:55 | `8_eval_ea_ne.py` 的临时输出（每行打分明细 / 无泄漏子集，会被覆盖）。 |

---

## 四、目录

| 目录 | 最后修改时间 | 说明 |
| --- | --- | --- |
| `labels/` | 2026-05-18 00:23 | 存放 `0_label.py` 的输出（key-evidence span 标注 JSONL + usage 报告）。 |
| `syn_questions/` | 2026-05-18 00:37 | 存放 `1_synthesize_question.py` 的输出（合成 PII 改写后的 JSONL + usage 报告）。 |
| `__pycache__/` | 2026-05-18 00:26 | Python 编译缓存，可安全删除。 |

---

## 五、跑通完整流水线的最小命令序列

```bash
export ENV_VENUS_OPENAPI_SECRET_ID=<your-key>

# 0. 关键证据片段标注
python 0_label.py --n 1000 --start 0 --concurrency 8

# 1. 合成 PII 改写
python 1_synthesize_question.py --n 1000 --concurrency 8
# (此处需要把 syn_questions/*.jsonl 转为 1_med2.parquet，
#  这一步在外部完成，参考 verl_old/protect 等仓库的预处理脚本)

# 2. PII 检测
python 2_anonymize.py

# 3. PII 过滤
python 3_clean_pii_entities.py

# 4. GPT-4o 推理写 query_gt
python 4_打标.py

# 5. 选项标签
python 5_答案打标.py

# 6. 系列清理
python 6_simplify_pii_entities.py
python 6_1_strip_key_spans_reason.py
python 6_2_remove_age_spans.py
python 6_3_fill_ground_truth.py

# 7. 字段重排 + train/test 划分
python 7_最终处理.py

# (在外部跑推理生成 med_with_priv_query.parquet 后)

# 8. 评测
python 8_eval_ea_ne.py \
    --input  med_with_priv_query.parquet \
    --output tem.parquet \
    --noleak_output tem.noleak.parquet
```
