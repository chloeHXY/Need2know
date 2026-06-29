
# `writing/` — Contextual-Privacy Benchmark 数据构建工程

本目录是 contextual-privacy benchmark 的数据构建主工程，由两层数据组成：

- **L1 通用反向合成** —— 见 [`layer1_reverse_synthesis/`](./layer1_reverse_synthesis/)
- **L2 医学领域挑战集** —— 见 [`Med_data_expand/`](./Med_data_expand/)

顶层另有三个写作/总览文档（`intro.md` / `data_construction.md` / `paper.md`）。

> ⚠️ **关于"修改时间"的说明**
>
> 本 README 中所列的"最近修改时间"为**文件系统 `mtime`**（`stat`/`find -printf %T+` 读出）。
> 由于本目录大部分文件是 **2026-05-18** 当天从其他位置整体 `cp` 过来的，
> 因此绝大多数文件的 mtime 都集中在 `2026-05-18 19:38` 附近，并非各文件真正最后一次"语义修改"的时间。
> 后续少数手动重写过的文档（`paper.md` / `data_construction.md` / `intro.md`）有更新的 mtime，可作为相对参考。

> ⚠️ **关于"误导性命名"的说明**
>
> 历史原因下，部分脚本和 parquet 的命名并不准确，下文中会逐项注明"实际行为"。

---

## 顶层文件

| 路径 | 类型 | 最近 mtime | 实际用途 |
|---|---|---|---|
| `intro.md` | 文档 | 2026-05-18 19:52 | 项目动机一页纸：解释为什么做 contextual privacy（区别于传统 PII 检测），并给出 L1/L2 两层的高层定位与项目路径。 |
| `data_construction.md` | 文档 | 2026-05-18 20:01 | **数据构建方法学正文**（论文章节草稿）：从 L1 反向合成的 Sampler→Generator→Judge→Reformulator 闭环，到 L2 医学挑战集的七阶段处理流程，逐节展开。是阅读本目录的第一入口。 |
| `paper.md` | 文档 | 2026-05-18 20:27 | 当前为空文件（占位），预留给整篇论文初稿。 |

---

## `layer1_reverse_synthesis/` — L1 通用反向合成流水线

> 一句话：**采样 spec → 生成 prompt → judge 反向校验 → 改写出 gold reformulation**，产出带先验金标的 `(prompt, E, NE, gold_reformulation)` 四元组。
>
> 子目录详细设计见 [`layer1_reverse_synthesis/README.md`](./layer1_reverse_synthesis/README.md)（这是项目内最完整的工程文档，强烈建议先读）。

### 顶层文件

| 路径 | 最近 mtime | 用途 |
|---|---|---|
| `layer1_reverse_synthesis/README.md` | 2026-05-18 19:38 | L1 项目主文档（约 326 行）：动机、流水线总览、数据 schema、目录结构、快速开始、防 reward hacking 设计、一致性打分、成本估算、与 SFT/RL 对接。 |
| `layer1_reverse_synthesis/requirements.txt` | 2026-05-18 19:38 | Python 依赖（仅 41 字节，少量核心包）。 |
| `layer1_reverse_synthesis/command.txt` | 2026-05-18 19:38 | 历史运行命令记录（filter_pass / run_synth / pii_tag 的实际调用样例）。 |
| `layer1_reverse_synthesis/test.py` | 2026-05-18 19:38 | ⚠️ **不是单元测试**：是一段 Venus LLM 代理的连通性 smoke test（直接 `requests.post` 一次 LLaMA3.1-8B 看是否通）。 |
| `layer1_reverse_synthesis/test.md` | 2026-05-18 19:38 | ⚠️ **不是测试文档**：是给医学题做"essential / helpful_or_uncertain spans"标注用的 prompt 草稿（与正式 pipeline 中的 prompt 同源，留作参考）。 |
| `layer1_reverse_synthesis/todo.md` | 2026-05-18 19:38 | L1 启动期的需求与 attribute 词典初稿（数据挖掘思路 + 30 个敏感属性的关键词模板）。 |
| `layer1_reverse_synthesis/demo_synthesis.ipynb` | 2026-05-18 19:38 | 端到端可运行 demo notebook，由 `scripts/build_demo_notebook.py` 生成。 |
| `layer1_reverse_synthesis/medical_o1_sft.json` | 2026-05-18 19:38 | 原始医学 SFT 数据（≈55 MB），是 L2 输入数据的祖先文件，也用于 `scripts/contextual_priv/mine_attributes.py` 做属性频次挖掘。 |

### `layer1_reverse_synthesis/synth/` — 核心库

所有文件 mtime 均为 `2026-05-18 19:38`。

| 路径 | 用途 |
|---|---|
| `synth/__init__.py` | 包入口。 |
| `synth/taxonomy.py` | 11 个 domain × 20 个 task × 30 个 attribute 的分类体系，以及 domain→essential pool 的映射、task→essential 策略 (`none`/`domain`/`addressed_person`)。 |
| `synth/value_bank.py` | 每个 attribute 的具体取值池（人工策划 ~10–30 项 + Faker-lite 合成函数）。 |
| `synth/sampler.py` | 结构化采样器：根据 spec 随机出 (domain, task, subject, embedding_style, tone, E_attrs, NE_attrs, confusion_type)。 |
| `synth/llm_client.py` | OpenAI 兼容 + 公司 Venus 代理双后端的异步 LLM 客户端，含池化、重试、token / USD 计费。 |
| `synth/prompts.py` | Generator / Reformulator / Judge 的 prompt 模板（按 essential 策略分支）。 |
| `synth/judge.py` | 解析 judge JSON 输出，做 token 重叠 + embedding 余弦两级匹配，产出 PASS / SOFT_FAIL / HARD_FAIL。 |
| `synth/pipeline.py` | Generator + Judge + Reformulator 的端到端编排。 |

### `layer1_reverse_synthesis/scripts/`

| 路径 | 用途 |
|---|---|
| `scripts/run_synth.py` | **主入口**：`--config --n --output` 三参数跑全流程。 |
| `scripts/inspect_samples.py` | 终端 ANSI 高亮地随机抽检 JSONL（支持按 status 过滤）。 |
| `scripts/stats.py` | 数据集分布统计（domain / task / status / attribute 计数 + 直方图）。 |
| `scripts/filter_pass.py` | 按 `consistency.status` / `essential_recall` / `nonessential_recall` 阈值过滤 JSONL。 |
| `scripts/filter_mcq.py` | 从 `medical_o1_sft.json` 中筛选含 A/B/C/D 选项的多选题，输出 `medical_o1_sft_mcq.json`。 |
| `scripts/dryrun_offline.py` | **离线 smoke test**：不调网络，仅验证 taxonomy / sampler / prompts / judge parser 自洽。 |
| `scripts/pii_tag.py` | 对 `judge_out.nonessential_attributes` 中每条 span 二次分类为 PII / NON_PII。 |
| `scripts/build_demo_notebook.py` | 一键生成 `demo_synthesis.ipynb` 的脚本。 |
| `scripts/contextual_priv/mine_attributes.py` | Stage 1 属性挖掘：对 `medical_o1_sft.json` 流式扫描 30 个属性的关键词出现频次，输出 `reports/attr_frequency.csv`。 |

### `layer1_reverse_synthesis/config/`

| 路径 | 用途 |
|---|---|
| `config/default.yaml` | 全部可调参数：generator / reformulator / judge 三个 LLM 端点、并发、采样权重、风格 / tone 分布、confusion_rate 等。 |

### `layer1_reverse_synthesis/data/` — 流水线产物 + 上游数据

整个目录文件 mtime 均落在 `2026-05-18 19:38`。文件数量较多，按用途分组：

| 文件 / 子目录 | 用途 |
|---|---|
| `data/README.md` | 一段文字：约定 `smoke.jsonl` / `layer1_v{N}.jsonl` / `*.bad.jsonl` 三种命名。 |
| `data/small.jsonl` / `data/small.pii.jsonl` / `data/small.pii_old.jsonl` | 极小规模的早期试跑样本。 |
| `data/smoke.jsonl` / `data/smoke.clean.jsonl` | 标准 smoke test 输出 + 经 `filter_pass.py` 过滤后的 PASS 子集。 |
| `data/smoke_v2.jsonl` | smoke test 的 v2 版本（10 条左右，跑通 generator 链路）。 |
| `data/smoke_518.jsonl` | 5/18 那次跑出的 smoke 数据。 |
| `data/smoke_58.jsonl` / `smoke_58_2.jsonl` / `smoke_58_3.jsonl` | 5/8 系列分批跑的合成数据（每批 200–600 条左右），后续会被 merge。 |
| `data/smoke_58.clean.jsonl` | 上面 `smoke_58.jsonl` 经 PASS 过滤后的 clean 子集。 |
| `data/smoke_58.clean_tag.jsonl` | clean 子集再经 `pii_tag.py` 二次打 PII 标签后的输出。 |
| `data/smoke_58.clean_with_tags.jsonl` | 把 `clean.jsonl` 和 `clean_tag.jsonl` 用 `merge_pii_tags.py` 合并后的最终带 PII 标签版本。 |
| `data/smoke_58_merged.jsonl` / `data/smoke_58_merged.clean.jsonl` | 把 `smoke_58_*` 三批 raw / clean 合并后的版本。 |
| `data/smoke_medqa.jsonl` | 在 medqa 数据上跑的 smoke 输出。 |
| `data/contextual_priv/` | 空目录占位，`scripts/contextual_priv/` 的预期输出位置。 |
| `data/medqa/phrases_no_exclude_train.jsonl` / `phrases_no_exclude_test.jsonl` | medqa 风格的短句训练 / 测试集（用于 value bank 取值与 attribute 挖掘）。 |
| `data/medqa/_value_bank_cache.json` | value bank 在 medqa 上的缓存。 |
| `data/med/medqa_dev_convo.jsonl` / `medqa_test_convo.jsonl` | stellalisy/mediQ 数据集的对话格式切片，作为 plan/`med扩展_58.md` 的扩展输入。 |
| `data/o1/` | ⚠️ **这是 `Med_data_expand/` 的早期前身**：当时把 medical_o1 的 label / synthesize_question 流程放在 L1 子目录里，后来被独立抽出来到顶层 `Med_data_expand/`。其中 `label.py`（key-span 标注）、`synthesize_question.py`（PII 注入改写）、`prompt.py` / `prompt2.py` 与 `Med_data_expand/0_label.py` / `1_synthesize_question.py` 一一对应。`labels/`、`syn_questions/`、`medical_o1_sft_mcq.json` 都是同源历史产物。`skill.md` / `command.txt` 是当时的需求 / 运行指令记录。 |

### `layer1_reverse_synthesis/Baseline/` — 全 Presidio baseline

| 路径 | 最近 mtime | 用途 |
|---|---|---|
| `Baseline/anonymize.py` | 2026-05-18 19:38 | Presidio baseline：对一个 jsonl/parquet 的 `extra_info["question"]` 跑 PII 检测 + anonymize，给每条加 `question_anonymized` / `question_pii_entities` 两列。 |
| `Baseline/test.py` | 2026-05-18 19:38 | Presidio API 用法 demo（10 行内的最小可运行示例）。 |
| `Baseline/skill.md` | 2026-05-18 19:38 | 占位文件（仅 2 字节，一个 `# `）。 |
| `Baseline/anony/command.txt` | 2026-05-18 19:38 | 跑 baseline 的具体命令（对 `smoke_58.clean.jsonl` 与 `o1/syn_questions/med.jsonl` 各跑一次）。 |
| `Baseline/anony/med.anonymized.jsonl` | 2026-05-18 19:38 | 对医学 `med.jsonl` 跑 Presidio 后的 anonymized + PII 实体输出。 |
| `Baseline/anony/train_data/smoke_58.clean.anonymized.jsonl` | 2026-05-18 19:38 | 对 `smoke_58.clean.jsonl` 跑 Presidio 后的输出。 |
| `Baseline/anony/train_data/smoke_58.clean.anonymized.with_gpt_answer.jsonl` | 2026-05-18 19:38 | 在上一步基础上又用 GPT 跑出 reference answer 的训练数据。 |

### `layer1_reverse_synthesis/plan/`

| 路径 | 最近 mtime | 用途 |
|---|---|---|
| `plan/med扩展_58.md` | 2026-05-18 19:38 | "5/8 那次"医学扩展计划：以 mediQ 为输入，目标产出与 L1 同 schema 的四元组。 |
| `plan/修改意见_51.md` | 2026-05-18 19:38 | "5/1 那次"代码改造 todo：把 LLM 调用从官方 OpenAI 切到公司 Venus 代理（参考 `examples/formal.py`）。 |

### `layer1_reverse_synthesis/reports/`

| 路径 | 最近 mtime | 用途 |
|---|---|---|
| `reports/attr_frequency.csv` | 2026-05-18 19:38 | `scripts/contextual_priv/mine_attributes.py` 在 `medical_o1_sft.json` 上跑出的 30 个属性的关键词频次表。 |

---

## `Med_data_expand/` — L2 医学领域挑战集

> 一句话：**七阶段串行流水线**，把医学多选题逐字保留、向其中受控注入合成 PII、并为每条样本提供 (medical key-spans, NE PII 列表, 选项金标 + 自由文本金标) 三组标签。
>
> 整体文件数较多，但产物路径有强约定：脚本编号 `N_*.py` 通常读取 `(N-1)_.parquet` 或 `(N-1)_*.parquet`、写入 `N_.parquet`。

整目录 mtime 集中在 `2026-05-18 19:38`。

### 输入 & 中间产物

| 路径 | 类型 / 大小 | 在流水线中的位置 |
|---|---|---|
| `medical_o1_sft_mcq.json` | 11.3 MB JSON | **流水线最初输入**：从 `medical_o1_sft.json` 中 `filter_mcq.py` 筛选出的 ABCD 多选题。 |
| `labels_gpt-4o_start0_n500_20260515_101049.jsonl` | 2.9 MB JSONL | 5/15 第一次跑 `0_label.py` 出的 500 条 key-span 标注（早期版本，已被 `labels/` 子目录中的 1000 条版替代）。 |
| `labels/labels_gpt-4o_start0_n1000_20260518_001557.jsonl` | 5.95 MB JSONL | **当前主版本**：5/18 凌晨跑 `0_label.py` 出的 1000 条 key-span 标注。 |
| `labels/labels_gpt-4o_start0_n1000_20260518_001557.usage.json` | 370 B | 上一步的 LLM 用量 / USD 成本报告。 |
| `syn_questions/med2.jsonl` | 7.46 MB JSONL | `1_synthesize_question.py` 的输出：在 1000 条 labels 上做 PII 注入改写，逐字保留临床字段。 |
| `syn_questions/syn_labels_gpt-4o_start0_n1000_20260518_001557_start0_n1000_20260518_002645.usage.json` | 669 B | 上一步的 LLM 用量报告。 |
| `1_med2.parquet` | 6.35 MB Parquet | ⚠️ **不是 `1_synthesize_question.py` 的直接输出**（脚本只输出 jsonl 到 `syn_questions/`）；这是把 `syn_questions/med2.jsonl` 转成 parquet、并补齐 `extra_info["question"]` 等字段后的版本，作为 `2_anonymize.py` 的输入。 |
| `2_.parquet` | 2.10 MB Parquet | `2_anonymize.py` 输出：对 `extra_info["question"]` 跑 Presidio，写入 `extra_info["question_pii_entities"]`、`extra_info["question_anonymized"]`。 |
| `3_.parquet` | 2.09 MB Parquet | `3_clean_pii_entities.py` 输出：对 PII 实体白/灰/黑名单清洗（仅保留 PERSON / 驾照号 / 银行号 / 年龄式 DATE_TIME / 真实地名 LOCATION 等）。 |
| `4_.parquet` | 2.22 MB Parquet | `4_打标.py` 输出：对每条 prompt 调 GPT-4o 推理，把自然语言医学答案写入 `extra_info.query_gt`（**不是给数据打 PII 标签**）。 |
| `5_.parquet` | 1.84 MB Parquet | `5_答案打标.py` 输出（再被 6_x 系列就地修改）：把 `extra_info.answer` 自然语言映射为 ABCDE 选项字母、写入 `extra_info.answer_label`。随后被 6_1/6_2/6_3 三步**就地覆盖**，所以这份 parquet 实际包含到第 6 步为止的全部修改。 |
| `5_.bak.parquet` | 1.99 MB Parquet | `6_2_remove_age_spans.py` 在覆盖 `5_.parquet` 前自动备份的版本（保留含年龄串的原始 key_spans）。 |
| `med.final.parquet` | 1.70 MB Parquet | `7_最终处理.py` 输出的全集（重命名字段后的最终发布 schema）。 |
| `med.final.train.parquet` | 3.02 KB Parquet | 0/1000 切分中的训练集（当前固定为 0 条，仅占位）。 |
| `med.final.test.parquet` | 1.70 MB Parquet | 0/1000 切分中的测试集（1000 条，**这是对外发布的 L2 测试集**）。 |

### 处理脚本（按编号顺序）

| 路径 | 实际行为（注意命名误导） |
|---|---|
| `0_label.py` | **Key-span 抽取**：以 GPT-4o 看 `(Question, Complex_CoT, Response)`，逐字抽出对答案最关键的连续证据片段，写入 `labels/*.jsonl`。⚠️ "label" 这里指"医学证据片段标注"，不是给整条样本贴 class 标签。 |
| `1_synthesize_question.py` | **PII 注入改写**：读 labels jsonl，按 `prompt2.py` 中的白/灰/黑名单 prompt，把每个 `Question` 改写成 `Syn_Question`（追加合成姓名 / MRN / 邮箱 / 电话 / 中性职业，**严禁**改动任何临床字段）。输出仍为 jsonl。 |
| `2_anonymize.py` | ⚠️ **名为 anonymize，实为 PII *检测/标注***：用 Microsoft Presidio 跑实体识别，把检测到的 `(entity_type, span, score, text)` 写到 `extra_info.question_pii_entities`，并写入一份 `question_anonymized` 文本。原始 `question` 仍然完整保留。 |
| `3_clean_pii_entities.py` | 规则化清洗 Presidio 输出：保留 PERSON / 驾照 / 银行号；DATE_TIME 仅留年龄式（"45-year-old"）；LOCATION 仅留人工策划的真实地名白名单（命中后会回写校正后的 span 起止）；其他丢弃。 |
| `4_打标.py` | ⚠️ **名为"打标"，实为"医学黄金答案推理"**：调 GPT-4o 对 prompt 推理出自然语言答案，写入 `extra_info.query_gt`。是给改写器评测准备的 upper-bound 参考答案。 |
| `5_答案打标.py` | ⚠️ **名为"答案打标"，实为"自然语言答案 → ABCDE 选项字母映射"**：用零温度 + 严格 system prompt 让 GPT-4o 输出 `A/B/C/D/E/UNKNOWN` 之一，写入 `extra_info.answer_label`，便于精确正确率计算。 |
| `6_1_strip_key_spans_reason.py` | 把 `extra_info["key_spans"]` 从 `[{span, reason}, ...]` 精简为纯 `list[str]`，丢弃 reason 字段（reason 仅作消融用）。 |
| `6_2_remove_age_spans.py` | 用正则 `(year\|month\|week\|day\|hour\|minute\|yr\|mo\|wk\|hr\|min)s?[\\s\\-]*old` 从 `key_spans` 中移除年龄串（避免与 NE 中的年龄串口径冲突）。覆盖前自动备份为 `5_.bak.parquet`。 |
| `6_3_fill_ground_truth.py` | 把 `extra_info.query_gt` 同步写到 `reward_model.ground_truth`（保留 `reward_model` 中的其他键如 style）。 |
| `6_simplify_pii_entities.py` | 备选简化路径：把 `question_pii_entities` 中每个实体 dict 退化为它的 `text` 字符串，使该字段变成 `list[str]`。当前主流水线**未使用**此脚本（主路径在第 7 步统一改名）。 |
| `7_最终处理.py` | 最终重命名 + 切分发布：`question_pii_entities → ne`、`key_spans` 保持、`answer ← query_gt`、按种子做 0/1000 train/test 切分（`split` 写入 `extra_info.split`），输出 `med.final{,.train,.test}.parquet`。 |
| `prompt2.py` | `1_synthesize_question.py` 用的 PII 注入改写 prompt 模板（白/灰/黑名单三段式约束）。 |

### 子目录

| 路径 | 用途 |
|---|---|
| `Med_data_expand/labels/` | `0_label.py` 当前主版本输出（1000 条 key-span 标注 + usage report）。 |
| `Med_data_expand/syn_questions/` | `1_synthesize_question.py` 当前主版本输出（1000 条 Syn_Question + usage report）。 |
| `Med_data_expand/__pycache__/` | Python 字节码缓存，可忽略。 |

---

## 推荐阅读顺序

1. 先读 `intro.md` 了解整个 benchmark 的动机；
2. 再读 `data_construction.md` 了解 L1/L2 各自的方法学全貌；
3. 想跑 L1 流水线 → 进 `layer1_reverse_synthesis/README.md`；
4. 想跑 L2 流水线 → 按 `Med_data_expand/` 中 `0_*.py` → `7_*.py` 的编号顺序逐步执行（注意 4/5 步实际是"推理"和"选项映射"，不是字面意义上的"打标"）。

---

## 常见易混点速查

| 你看到的命名 | 真实含义 |
|---|---|
| `Med_data_expand/4_打标.py` | 调 GPT-4o 推出医学黄金答案 `query_gt` |
| `Med_data_expand/5_答案打标.py` | 把自然语言答案规范化为 `A/B/C/D/E` 选项字母 |
| `Med_data_expand/0_label.py` | 抽取医学证据 **key spans**（不是分类打标） |
| `Med_data_expand/2_anonymize.py` | Presidio **PII 检测/标注**（不真正 anonymize 原文） |
| `Med_data_expand/1_med2.parquet` | `syn_questions/med2.jsonl` 转 parquet 后的版本 |
| `Med_data_expand/5_.bak.parquet` | 第 6_2 步覆盖 `5_.parquet` 前的备份 |
| `layer1_reverse_synthesis/test.py` | Venus LLM 代理连通性 smoke test |
| `layer1_reverse_synthesis/test.md` | 医学 essential-span 标注 prompt 草稿 |
| `layer1_reverse_synthesis/data/o1/` | `Med_data_expand/` 的早期前身，已被独立到顶层 |
| `layer1_reverse_synthesis/Baseline/` | 全 Presidio 的基线，不是评测代码 |

