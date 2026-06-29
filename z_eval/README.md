# z_eval — 隐私改写流水线的评测套件

本目录提供两类评测能力，用于度量「先把用户 query 经本地模型改写为 `priv_query`，再交由远端 LLM（GPT-4o）回答」这一隐私改写流水线的端到端表现：

1. **质量评测（Quality Judge, `Q_AL`）**：使用 GPT-4o 作为裁判，双向比较（防位置偏差）流水线回答 `C_L` 与基线回答 `C_T` 的相对质量。
2. **隐私评测（Privacy-leak）**：基于 `priv_query`（唯一暴露给远端 LLM 的载荷），同时计算两种泄露率——与训练 reward 对齐的 **NE-leak**，以及更直观的 **PII-leak（正则）**。

> ⚠️ 文件命名提示：`eval.py` 中的 `OUTPUT_PATH` 当前默认指向 `eval_result_PII.parquet`，且 `FILE_A` 已改为 `inference/test.anonymized_gpt_answer.parquet`（即匿名化路径产出的回答），**与 `skill.md` 中最初描述的 `merge_inference` 输入并不一致**。换言之，目录中带 `PII` 字样的结果文件指代的是「匿名化（anonymize）路径」而非 PII 抽取本身，请勿望文生义。

---

## 目录结构与最近更新时间

| 路径 | 类型 | 大小 | 最近修改时间 |
| --- | --- | --- | --- |
| `eval.py`                              | 文件 | 12.60 KB  | 2026-05-15 17:22 |
| `eval_jsonl.py`                        | 文件 | 12.13 KB  | 2026-05-15 16:58 |
| `skill.md`                             | 文件 |  4.77 KB  | 2026-05-15 17:39 |
| `eval_result.parquet`                  | 文件 | 299.76 KB | 2026-05-12 03:21 |
| `eval_result_PII.parquet`              | 文件 | 150.12 KB | 2026-05-15 17:23 |
| `eval_privacy/`                        | 目录 |  —        | 2026-05-12 03:36 |
| `eval_privacy/com_privacy_score.py`    | 文件 | 14.03 KB  | 2026-05-17 21:05 |
| `eval_privacy/eval_privacy.py`         | 文件 | 12.84 KB  | 2026-05-12 03:36 |
| `eval_privacy/skill.md`                | 文件 |  0.96 KB  | 2026-05-12 03:34 |

> 时间通过 `find -printf '%T...'` 直接读取自文件系统 `mtime`，并非 git 历史。`__pycache__/` 已忽略。

---

## 一、质量评测脚本

### `eval.py`
**作用**：对两份 **parquet** 输入做 pairwise 质量评测（`Q_AL`，带顺序交换）。

- **输入**
  - `FILE_A`（默认 `inference/test.anonymized_gpt_answer.parquet`）— 流水线输出 `C_L`，使用列 `question_anonymized_gpt_answer`。
  - `FILE_B`（默认 `inference/test_with_gpt_answer2.parquet`）— 基线输出 `C_T`，使用列 `gpt_answer`。
- **对齐策略**（按优先级降级）：
  1. 双方都有 `extra_info.question` → 按 user_query 内连接；
  2. 双方都有 `priv_query` → 按 `priv_query` 内连接；
  3. 行数相等时位置对齐，否则报错。
- **裁判逻辑（`Q_AL`，与 `skill.md` 一致）**：
  1. 调用 1 次：`A=C_L, B=C_T` → `s1`；
  2. 调用 2 次（交换顺序）：`A=C_T, B=C_L` → `s2`；
  3. `s1 == s2` 视为不一致/并列，保守通过 `score = 1`；否则 `score = s1`。
- **空响应短路**：避免空字符串浪费 LLM 调用，`A` 空记 0、`B` 空记 1、双空记 1。
- **裁判服务**：GPT-4o（venus llmproxy），`temperature=0`，16 路并发，3 次重试 + 指数退避，单请求超时 120 s。
- **输出**：`OUTPUT_PATH`（**默认 `z_eval/eval_result_PII.parquet`**），列：`user_query, response_A, response_B, s1, s2, score`；终端打印总均分及 2 条随机样例。

**典型用法**：
```bash
cd /group/40047/eiraxyhuang/workspace/fc/DataG/z_eval
python eval.py                      # 全量评估
python eval.py --limit 50           # 小批量验证
python eval.py --workers 8          # 调整并发
python eval.py --file_a <A.parquet> --file_b <B.parquet> --output <out.parquet>
```

### `eval_jsonl.py`
**作用**：与 `eval.py` 同一套 `Q_AL` 逻辑，但 **File A 改为 JSONL** 输入。用于评测 `layer1_reverse_synthesis` 流水线产出的中间文件。

- **输入**
  - `FILE_A`（JSONL，默认 `layer1_reverse_synthesis/Baseline/anony/smoke_58.clean.anonymized.with_gpt_answer.jsonl`），列 `anonymized_gpt_answer` 作为 `C_L`，键 `raw_prompt` 作为 user query。
  - `FILE_B`（parquet，同上），列 `gpt_answer` 作为 `C_T`，user query 取自 `extra_info.question`。
- **对齐策略**：优先按 `raw_prompt`（A）↔ `extra_info.question`（B）内连接，否则按行数位置对齐。
- **输出**：默认 `z_eval/eval_result_jsonl.parquet`（与 `eval.py` 输出格式一致）。

**典型用法**：
```bash
python eval_jsonl.py --file_a <A.jsonl> --file_b <B.parquet> --output <out.parquet>
```

### `skill.md`
质量评测模块的设计文档：算法目标、`f_QJ` 提示词、`Q_AL` 推导、对齐策略、健壮性要求、运行方式，以及 5/12 跑出的历史结果（`merge_inference` 路径平均 0.90，PII/anonymize 路径平均 0.8867）。是上面两个脚本的「需求规格」。

---

## 二、质量评测结果文件

### `eval_result.parquet`（2026-05-12）
`eval.py` 早期版本（`FILE_A = merge_inference/test_with_merge_inference.parquet`，列 `merge_inference_answer`）输出的结果。对应 `skill.md` 末尾「total pairs : 150, average : 0.90」。
列：`user_query, response_A, response_B, s1, s2, score`。

### `eval_result_PII.parquet`（2026-05-15）
`eval.py` 当前默认 `OUTPUT_PATH`，对应「匿名化（anonymize）路径」的评测结果（`question_anonymized_gpt_answer` vs `gpt_answer`）。
**注意**：文件名中的 `PII` 是历史命名，并不是说该文件存的是 PII 抽取结果，而是「PII/匿名化」分支的质量评测结果。对应 `skill.md` 末尾「pii Result … average : 0.8867」。
列同上：`user_query, response_A, response_B, s1, s2, score`。

---

## 三、隐私评测子目录 `eval_privacy/`

度量 `priv_query`（暴露给远端 LLM 的唯一载荷）的隐私泄露率，输入是 `inference/test_with_priv_query.parquet`。

### `eval_privacy/eval_privacy.py`
**作用**：计算两类互补的泄露指标。

- **NE-leak**（与训练 reward 对齐，复用 `com_privacy_score.py` 中的 `coverage` 与 `_bert_p_rescaled`）
  - 对每个 `extra_info["ne"]` 中的 `C`：
    - 字面：`coverage(priv_query, C) >= 1.0`；
    - 语义：`BERTScore`（roberta-large, `rescale_with_baseline=True`）的 `P_rescaled > 0.3`；
  - **样本级**：任一 NE 命中即记泄露；**元素级**：泄露 NE 个数 / 总 NE 个数。
- **PII-leak**（正则）
  - 从原始 `question` 中抽取 PII（email / url / ssn / phone / credit_card / driver_license / 长数字串），更具体的模式优先 claim 区间，避免重叠重复计数；
  - 对每个 PII，做大小写不敏感、空白归一化的子串匹配；电话/SSN/卡号等额外做「仅数字」匹配，容忍格式重排；
  - 同样输出样本级与元素级泄露率。
- **输入**：`--input` 默认 `inference/test_with_priv_query.parquet`，必须含 `priv_query` 与 `extra_info`（其中 `question/ne/origin_ea/index`）。
- **输出**：`--output` 默认 `z_eval/eval_privacy/eval_privacy_result.parquet`（**当前目录中尚未生成**），含每条样本的 NE/PII 详细指标；终端打印聚合结果。
- **开关**：`--no_bert` 关闭语义级判定（BERTScorer 加载失败时自动降级为 Jaccard-only）；`--limit N` 只跑前 N 条。

**典型用法**：
```bash
cd /group/40047/eiraxyhuang/workspace/fc/DataG/z_eval/eval_privacy
python eval_privacy.py                          # 全量
python eval_privacy.py --no_bert --limit 50     # 快速验证
```

### `eval_privacy/com_privacy_score.py`
**作用**：训练 reward 函数 `compute_score(solution_str, ground_truth, extra_info)`，同时被 `eval_privacy.py` 复用作为 NE-leak 的底层算子。

- **核心工具**：`_tokenize`（去停用词的字母数字 token 化）、`jaccard`、`coverage`（B 中被 A 覆盖的比例）、`_get_bert_scorer`（懒加载 `bert_score.BERTScorer`，`rescale_with_baseline=True`，模型路径取自 `PRIV_BERTSCORE_MODEL_PATH` 环境变量）、`_bert_p_rescaled`、`_to_str_list`。
- **`compute_score` 三段式打分**：
  1. **隐私**：任一 `coverage(A, ne_i) >= 1.0` 或 `max P_rescaled > 0.3` → 直接 `return -1`；
  2. **效用**（仅 `origin_ea` 非空时）：每个 `ea_i` 若同时 `coverage < 0.5` 且 `P_rescaled < 0.3` 计一次 miss；`score = max(-1, -0.2 * miss_count)`；
  3. **长度爬坡**：通过前两关后给 `len(A)/len(gold)` 比值作为连续小奖励，避免合格样本之间梯度为零。
- 文件末尾保留了一段 smoke test，可直接 `python com_privacy_score.py` 跑一个示例。

### `eval_privacy/skill.md`
隐私评测模块的设计文档：阐明为什么只评 `priv_query`，以及衡量方式（NE 复用 reward 逻辑 + 加上 PII 正则更直观）。

### `eval_privacy/__pycache__/`
Python 解释器自动生成的字节码缓存，可忽略 / 安全删除。

---

## 四、整体数据流

```
                     question                       (raw user input)
                        │
                        ▼
            ┌───────────────────────┐
            │  本地隐私改写模型      │  → priv_query  (暴露给远端的唯一载荷)
            └───────────────────────┘
                        │                                 │
                        │                                 ▼
                        │                  eval_privacy.py  → NE-leak / PII-leak
                        ▼
            ┌───────────────────────┐
            │   远端 GPT-4o 回答    │  → C_L (anonymized_gpt_answer / merge_inference_answer)
            └───────────────────────┘
                        │
                        ▼
                    eval.py / eval_jsonl.py
                        │  ↑ 与基线 C_T (gpt_answer) 双向 GPT-4o 裁判
                        ▼
                eval_result*.parquet  + 终端平均分
```

---

## 五、跑通最小依赖

- Python 包：`pandas`, `pyarrow`, `requests`, `tqdm`（质量评测）、`bert_score` + `roberta-large`（隐私评测，可关）。
- 网络：`eval.py` / `eval_jsonl.py` 需要能访问 `http://v2.open.venus.oa.com/llmproxy`（脚本内置 token，仅供内网调试）。
- 环境变量：`PRIV_BERTSCORE_MODEL_PATH` 指向本地 roberta-large 权重；未设置时 BERTScorer 会加载失败并自动降级为 Jaccard-only。
