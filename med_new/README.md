# `med_new` 目录说明

本目录用于围绕一个**医学单选题（MCQ）数据集**搭建「隐私重写（privacy-rewrite）」任务的全流程数据加工链：

> 原始医学题 → PII（个人身份信息）标注 → PII 实体清洗 → query_gt 推理 → 选项标签打标 → key_spans 抽取与瘦身 → key_spans 二次校验（LLM 消融 + 命中率） → system prompt 替换 → 最终字段重命名与 train/test 划分。

下游 RL 训练所需的 reward 函数（`命中.py`）也存放在本目录，便于与数据字段一起维护。

> ⚠️ 部分文件名带有"误导性"，请以本说明为准（详见下文每个文件的 **注意** 段落）。
> 📅 每个文件的最后修改时间见文末「文件最后修改时间」一节，可帮助快速分辨"哪一版才是当前在用的产物"。

---

## 1. 数据流水线（按生成顺序）

下图展示了 parquet 文件的生成依赖。每一步对应一个或多个脚本：

```
med.parquet
   │  (anonymize.py)
   ▼
med.anonymized.parquet
   │  (clean_pii_entities.py)
   ▼
med.anonymized.cleaned.parquet
   │  (打标.py：用 GPT-4o 推理 query_gt，写入 extra_info.query_gt)
   ▼
med.anonymized.cleaned.with_query_gt.parquet
   │  (答案打标.py：用 GPT-4o 把自然语言 answer 转为 A/B/C/D/E 字母)
   ▼
med.anonymized.cleaned.with_answer_label.parquet     ←★ 主工作文件
   │
   ├─ (fix_unknown_to_e.py)        UNKNOWN → E（就地覆盖）
   ├─ (simplify_pii_entities.py)   question_pii_entities: list[dict] → list[str]（就地覆盖）
   ├─ (strip_key_spans_reason.py)  key_spans: list[{reason,span}] → list[str]（就地覆盖）
   ├─ (remove_age_spans.py)        从 key_spans 中删除 "xx-year-old" 类年龄串（就地覆盖，附 .bak）
   ├─ (system_prompt_change.py)    替换 prompt 中 system 消息为 NEW_SYSTEM_PROMPT（就地覆盖）
   ├─ (fill_ground_truth.py)       extra_info.query_gt → reward_model.ground_truth
   │
   ├─ (key_spans_hit_rate.py)      → med.anonymized.cleaned.with_hit_rate.parquet
   ├─ (key_spans_check.py)         → med.anonymized.cleaned.with_span_check.parquet            (GPT-4o LOO 消融)
   └─ (key_spans_check_llama.py)   → with_span_check_llama1b.parquet / with_span_check_llama3b.parquet
                                     (本地 Llama-3.2-1B/3B-Instruct LOO 消融，文件名 `_llama` 不区分尺寸)
   │
   │  (最终处理.py：rename / replace / 350-150 split)
   ▼
med.final.parquet  →  med.final.train.parquet  +  med.final.test.parquet
```

---

## 2. Parquet 数据文件

| 文件 | 说明 |
| --- | --- |
| `med.parquet` | 输入起点：医学 MCQ，含 `prompt`、`extra_info.question`、`extra_info.answer`（自然语言）等字段。 |
| `med.anonymized.parquet` | 经 Presidio 在 `extra_info.question` 上做 PII 检测后的结果，新增 `extra_info.question_anonymized`、`extra_info.question_pii_entities`（list[dict]，含 `entity_type/start/end/score/text`）。 |
| `med.anonymized.cleaned.parquet` | 对 `question_pii_entities` 按规则清洗（保留 PERSON / 驱照 / 银行号；DATE_TIME 仅保留年龄；LOCATION 仅保留白名单地名）。 |
| `med.anonymized.cleaned.with_query_gt.parquet` | 在上一步基础上用 GPT-4o 跑 prompt，得到的回答写入 `extra_info.query_gt`。 |
| `med.anonymized.cleaned.with_answer_label.parquet` | **主工作文件**。在 `with_query_gt` 基础上用 GPT-4o 把 `extra_info.answer`（自然语言）打标为 A/B/C/D/E 字母，存入 `extra_info.answer_label`（原始输出在 `answer_label_raw`）。后续多个就地覆盖脚本（`fix_unknown_to_e.py`、`simplify_pii_entities.py`、`strip_key_spans_reason.py`、`remove_age_spans.py`、`system_prompt_change.py`、`fill_ground_truth.py` 等）均直接修改此文件。 |
| `med.anonymized.cleaned.with_answer_label.bak.parquet` | `remove_age_spans.py` 第一次运行时自动生成的备份。 |
| `med.anonymized.cleaned.with_hit_rate.parquet` | `key_spans_hit_rate.py` 的输出：每个 `key_spans` 项相对 `query_gt` 的 Jaccard coverage 与 BERTScore P_rescaled，以及行级命中率。 |
| `med.anonymized.cleaned.with_span_check.parquet` | `key_spans_check.py` 的输出：用 **GPT-4o** 做 Leave-One-Out 消融校验 `key_spans` 必要性。 |
| `med.anonymized.cleaned.with_span_check_llama.parquet` | 旧版/通用名，实际由 `key_spans_check_llama.py` 历史版本产出。 |
| `med.anonymized.cleaned.with_span_check_llama1b.parquet` | 本地 **Llama-3.2-1B-Instruct** 跑 LOO 消融的结果。 |
| `med.anonymized.cleaned.with_span_check_llama3b.parquet` | 本地 **Llama-3.2-3B-Instruct** 跑 LOO 消融的结果（当前 `key_spans_check_llama.py` 默认输出此路径）。 |
| `med.final.parquet` | `最终处理.py` 的全量输出：`question_pii_entities` 重命名为 `ne`，`extra_info.answer` 替换为 `query_gt`，并加入空的 `origin_ea` 与 `split` 字段。 |
| `med.final.train.parquet` | 训练集（350 条），`split == "train"`。 |
| `med.final.test.parquet` | 测试集（150 条），`split == "test"`。 |

---

## 3. Python 脚本

### 3.1 PII 标注与清洗

- **`anonymize.py`**
  使用 Microsoft Presidio 的 `AnalyzerEngine + AnonymizerEngine` 对 `extra_info["question"]` 做 PII 检测与脱敏。把脱敏文本写入 `extra_info.question_anonymized`，把检测到的实体列表写入 `extra_info.question_pii_entities`。
  默认 `med.parquet → med.anonymized.parquet`。

- **`clean_pii_entities.py`**
  按实体类型清洗 `question_pii_entities`：
  - 保留：`PERSON`、`US_DRIVER_LICENSE`、`US_BANK_NUMBER`
  - `DATE_TIME` 仅保留 "xx-year-old / xx-month-old / xx-week-old / xx-day-old" 这类年龄串
  - `LOCATION` 仅保留白名单地名（含国家、洲、地区码 WY/MI 等；并能去掉 "A. " / "B. " 之类 MCQ 前缀，把 span 截到地名上）
  - 其它（NRP、URL、PHONE_NUMBER 等）全部丢弃
  默认 `med.anonymized.parquet → med.anonymized.cleaned.parquet`。

- **`simplify_pii_entities.py`**
  将 `extra_info.question_pii_entities` 从 `list[{entity_type,start,end,score,text}]` 简化为 `list[str]`，只保留每个实体的 `text` 字段。**默认就地覆盖** `med.anonymized.cleaned.with_answer_label.parquet`。

- **`stats_entity_types.py`**
  统计 `question_pii_entities` 中各 `entity_type` 的频次（默认读 `med.anonymized.parquet`）。仅打印，不写文件。

- **`_inspect_entities.py`**
  调试用：打印 `DATE_TIME` 与 `LOCATION` 实体的 `text` 取值频次 Top-N，用来设计 `clean_pii_entities.py` 的过滤规则。

### 3.2 query_gt / 答案标签

- **`打标.py`** （文件名直译"打标"，但**实际功能是用 GPT-4o 跑 prompt 生成 query_gt**，并不是给答案打标签）
  并发请求 venus llmproxy 的 GPT-4o，把回答写入 `extra_info.query_gt`。
  默认 `med.anonymized.cleaned.with_answer_label.parquet → med.anonymized.cleaned.with_answer_label2.parquet`（脚本头注释提到的 cleaned.parquet 并非真实输入路径，请以脚本中 `INPUT_PATH/OUTPUT_PATH` 为准）。

- **`答案打标.py`**
  这个才是真正的"答案字母标注"脚本：用 GPT-4o 读 `extra_info.question`（含选项）和 `extra_info.answer`（自然语言解释），输出 A/B/C/D/E/UNKNOWN 写入 `extra_info.answer_label`，原始模型输出写入 `extra_info.answer_label_raw`。
  默认 `med.anonymized.cleaned.with_query_gt.parquet → med.anonymized.cleaned.with_answer_label.parquet`。

- **`fix_unknown_to_e.py`**
  把 `extra_info.answer_label == "UNKNOWN"` 全部改成 `"E"`，**就地覆盖** `med.anonymized.cleaned.with_answer_label.parquet`。

- **`fill_ground_truth.py`**
  把 `extra_info.query_gt` 写入 `reward_model.ground_truth`（仅替换该子键，其它 reward_model 字段保持不变）；缺失 `query_gt` 时保留原值并打告警。默认就地覆盖输入文件。

### 3.3 key_spans 处理

- **`strip_key_spans_reason.py`**
  把 `extra_info.key_spans` 从 `list[{reason, span}]` 压平为 `list[str]`（只保留 `span` 字段）。**就地覆盖** `med.anonymized.cleaned.with_answer_label.parquet`。

- **`remove_age_spans.py`**
  在 key_spans 已经被简化为字符串列表的前提下，删除其中所有匹配年龄正则
  `(year|month|week|day|hour|minute|yr|mo|wk|hr|min)s?[\s\-]*old` 的项。
  首次运行会把原文件备份到 `*.bak.parquet`，然后**就地覆盖**主文件。

- **`stats_key_spans.py`**
  统计 `extra_info.key_spans` 的字符长度 / 词长度分布、每行 span 数量分布，并打印最长 / 最短 5 个示例 span（默认读 `med.anonymized.cleaned.parquet`）。
  **注意**：脚本里取 `it.get("span", "")`，是按 dict 形式读取的。当 key_spans 还未经 `strip_key_spans_reason.py` 简化时（也就是仍是 `list[{reason,span}]` 时）才能读到内容；对已简化的 list[str] 文件需要先调整再使用。

- **`_probe_key_spans.py`**
  调试用：探测 `key_spans` 在 parquet 中的位置（顶级列还是 `extra_info` 内）以及类型，打印第一行样例。

### 3.4 key_spans 必要性 / 命中率校验

- **`key_spans_check.py`**
  **GPT-4o 版** Leave-One-Out 消融。对每行的每个 key_span：在 `question` 中把它替换为 `[REDACTED]`，让 GPT-4o 只输出 A/B/C/D/E，与 `extra_info.answer_label`（gold）比较：
  - 不同 → `is_necessary = True`（去掉就答错 → 必要）
  - 相同 → `is_necessary = False`（疑似冗余）

  写回字段：
  - `extra_info.key_spans[i]` 增加 `is_necessary / masked_pred / masked_pred_raw / skipped_reason`
  - `extra_info.key_spans_check_summary`：行级汇总

  默认 `with_answer_label.parquet → with_span_check.parquet`。

- **`key_spans_check_llama.py`**
  与上面同思路的本地小模型版本，使用 `transformers` + 批量 `generate`。
  **⚠️ 文件名误导**：脚本名虽然叫 `_llama`（看起来像 1B），但**当前默认 `MODEL_PATH` 指向 `Llama-3.2-3B-Instruct`，输出 `with_span_check_llama3b.parquet`**；脚本 docstring 里仍提到 1B-Instruct。可以通过 `--model-path / --output` 覆盖以跑 1B 版本。

- **`key_spans_hit_rate.py`**
  对每个 key_span 与 `extra_info.query_gt` 计算：
  - Jaccard 风格的 `coverage`（`|tokens(query_gt) ∩ tokens(span)| / |tokens(span)|`）
  - BERTScore P_rescaled（`roberta-large`，本地路径，开启 rescale baseline）
  阈值默认 `coverage>=0.5 or p_rescaled>=0.3` 视为命中，输出每行命中率 / 缺失数量等统计；同时把详细结果写入 `extra_info.key_spans_hit_check`，并新增顶级列 `key_spans_hit_rate / key_spans_miss_count`。
  默认 `with_answer_label.parquet → with_hit_rate.parquet`。

### 3.5 训练所需的最终化处理

- **`system_prompt_change.py`**
  替换 `prompt` 中所有 `role == system` 的消息为脚本内置的 `NEW_SYSTEM_PROMPT`（用于"隐私改写为信息检索式 query"的指令），其它消息保持不变。**就地覆盖** `med.anonymized.cleaned.with_answer_label.parquet`。

- **`最终处理.py`**
  做最后一步重整：
  1. `extra_info.question_pii_entities` 重命名为 `ne`
  2. `extra_info.key_spans` 保留为 `key_spans`
  3. 用 `extra_info.query_gt` 覆盖 `extra_info.answer`
  4. 给每行加空的 `extra_info.origin_ea = []`
  5. 用固定 seed=42 把 500 条数据划分为 350 train / 150 test，并写入 `extra_info.split` 与顶级 `split` 列
  6. 输出 `med.final.parquet / med.final.train.parquet / med.final.test.parquet`

### 3.6 通用工具与 reward

- **`change_split.py`**
  把 `split` 字段从 `test` 批量改成 `train`（或自定义任意 `--from-value` / `--to-value`）。同时支持顶级 `split` 列与 `extra_info.split` 嵌套场景。可多次 `--input` 一并处理。

- **`parquet_to_jsonl.py`**
  通用 parquet → jsonl 转换器（流式 + 可选列裁剪），基于 `pyarrow.parquet.ParquetFile.iter_batches`。处理 NaN/Inf、numpy 标量、bytes、datetime 等的安全 JSON 序列化。

- **`命中.py`**
  PRIV 任务的 reward 函数 `compute_score(solution_str, ground_truth, extra_info)`。
  逻辑见文件头注释：
  1. 隐私泄露：`coverage(A, c) >= 1.0` 或 BERTScore P_rescaled max > 0.3 → return -1
  2. utility：对 `extra_info.origin_ea` 每一项做 Jaccard + BERTScore 命中检查，每个 miss 扣 0.2，clamp 到 -1
  3. 通过前两步后给一个长度爬坡奖励作为连续信号
  与 `key_spans_hit_rate.py` 的命中判断逻辑保持一致。

---

## 4. Markdown 备忘文件

- **`skills.md`** —— 最早写给自己看的 PII 标注脚本说明（思路 = `anonymize.py` 的雏形）。
- **`check.md`** —— 关于"key_spans 必要性二次校验该怎么做"的思考草稿，最终落地为 `key_spans_check.py` / `key_spans_check_llama.py` / `key_spans_hit_rate.py` 三个脚本。
- **`todo.md`** —— 临时 TODO：检查 `with_span_check_llama.parquet` 与 `with_answer_label2.parquet` 是否行对齐。

---

## 5. extra_info 关键字段速查（最终态）

经过整条流水线后，`med.final.parquet` 中每行 `extra_info` 大致包含：

| 字段 | 含义 |
| --- | --- |
| `question` | 原始医学单选题（含选项） |
| `question_anonymized` | Presidio 脱敏后的 question |
| `ne` | 简化后的 PII 实体文本列表（list[str]）—— 命名来自 `最终处理.py` |
| `key_spans` | 解题关键片段（list[str]，已去除年龄串，已去掉 reason） |
| `answer` | = `query_gt`（覆盖后） |
| `answer_label` | A/B/C/D/E 字母标签 |
| `answer_label_raw` | 标注模型的原始输出 |
| `query_gt` | GPT-4o 对 prompt 给出的回答（用作 RL ground truth） |
| `origin_ea` | 占位空列表，留给后续填充"必须保留的实体"用 |
| `split` | "train" / "test" |

---

## 6. 常用命令示例

```bash
# 1) 跑一次完整的 PII 流水线（前两步）
python anonymize.py
python clean_pii_entities.py

# 2) 用 GPT-4o 生成 query_gt（注意脚本名是"打标.py"，但其实是生成 query_gt）
python 打标.py

# 3) 把自然语言 answer 标注为 A/B/C/D/E
python 答案打标.py
python fix_unknown_to_e.py

# 4) 简化 PII 实体 / key_spans，并去掉年龄串
python simplify_pii_entities.py
python strip_key_spans_reason.py
python remove_age_spans.py

# 5) 替换 system prompt，并把 query_gt 灌进 reward_model.ground_truth
python system_prompt_change.py
python fill_ground_truth.py

# 6) key_spans 校验
python key_spans_hit_rate.py
python key_spans_check.py                         # GPT-4o 版
python key_spans_check_llama.py                   # 本地 Llama 3B（默认）
python key_spans_check_llama.py \
    --model-path /group/40047/eiraxyhuang/workspace/fc/DataG/model_hf/Llama-3.2-1B-Instruct \
    --output    /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_span_check_llama1b.parquet

# 7) 最终重命名 + 划分
python 最终处理.py

# 8) 看一眼数据
python parquet_to_jsonl.py med.final.train.parquet -o /tmp/train.jsonl
```

---

## 7. 文件最后修改时间

> 来自 `ls -la --time-style=long-iso` 在 2026-06-29 抓取的快照，按修改时间倒序排列。
> 同名前缀的两份产物可以通过这个时间快速判断"哪一版是更新的"。

### 7.1 Python 脚本

| 脚本 | 最后修改时间 |
| --- | --- |
| `parquet_to_jsonl.py` | 2026-05-17 15:13 |
| `最终处理.py` | 2026-05-17 02:19 |
| `fill_ground_truth.py` | 2026-05-17 01:13 |
| `system_prompt_change.py` | 2026-05-17 01:04 |
| `remove_age_spans.py` | 2026-05-17 00:59 |
| `simplify_pii_entities.py` | 2026-05-16 23:08 |
| `key_spans_hit_rate.py` | 2026-05-16 22:56 |
| `命中.py` | 2026-05-16 22:55 |
| `strip_key_spans_reason.py` | 2026-05-16 22:45 |
| `打标.py` | 2026-05-16 22:32 |
| `key_spans_check_llama.py` | 2026-05-16 21:39 |
| `key_spans_check.py` | 2026-05-16 20:48 |
| `答案打标.py` | 2026-05-16 20:38 |
| `fix_unknown_to_e.py` | 2026-05-16 20:39 |
| `stats_key_spans.py` | 2026-05-16 18:39 |
| `_probe_key_spans.py` | 2026-05-16 18:39 |
| `clean_pii_entities.py` | 2026-05-16 17:22 |
| `_inspect_entities.py` | 2026-05-16 17:21 |
| `stats_entity_types.py` | 2026-05-16 17:21 |
| `change_split.py` | 2026-05-16 16:56 |
| `anonymize.py` | 2026-05-16 16:49 |

### 7.2 Parquet 数据文件

| Parquet | 最后修改时间 |
| --- | --- |
| `med.final.parquet` | 2026-05-17 02:19 |
| `med.final.test.parquet` | 2026-05-17 02:19 |
| `med.final.train.parquet` | 2026-05-17 02:19 |
| `med.anonymized.cleaned.with_answer_label.parquet` | 2026-05-17 01:13 |
| `med.anonymized.cleaned.with_answer_label.bak.parquet` | 2026-05-16 23:08 |
| `med.anonymized.cleaned.with_hit_rate.parquet` | 2026-05-16 23:02 |
| `med.anonymized.cleaned.with_span_check_llama3b.parquet` | 2026-05-16 21:46 |
| `med.anonymized.cleaned.with_span_check_llama.parquet` | 2026-05-16 21:11 |
| `med.anonymized.cleaned.with_span_check_llama1b.parquet` | 2026-05-16 21:33 |
| `med.anonymized.cleaned.with_span_check.parquet` | 2026-05-16 20:57 |
| `med.anonymized.cleaned.with_query_gt.parquet` | 2026-05-16 19:54 |
| `med.anonymized.cleaned.parquet` | 2026-05-16 19:52 |
| `med.anonymized.parquet` | 2026-05-16 16:59 |
| `med.parquet` | 2026-05-16 16:59 |

### 7.3 Markdown 文件

| 文件 | 最后修改时间 |
| --- | --- |
| `check.md` | 2026-05-16 20:40 |
| `skills.md` | 2026-05-16 16:50 |
| `todo.md` | 2026-05-16 22:38 |

> 备注：
> - 三份 `with_span_check_llama*.parquet` 中，**`llama3b` 是最新的**（21:46），与 `key_spans_check_llama.py` 当前默认 `MODEL_PATH=Llama-3.2-3B-Instruct` 对应；早一点产出的 `_llama.parquet`（21:11）和 `_llama1b.parquet`（21:33）属于历史/小模型对照版本。
> - `med.anonymized.cleaned.with_answer_label.parquet`（01:13）的修改时间晚于 `with_answer_label.bak.parquet`（23:08），是因为多个就地覆盖脚本（`remove_age_spans.py / simplify_pii_entities.py / system_prompt_change.py / fill_ground_truth.py` 等）会持续更新它，备份只在 `remove_age_spans.py` 首次运行时落盘一次。
