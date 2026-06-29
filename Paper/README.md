## Paper —— Privacy-Conscious Delegation under Contextual Integrity

> 本目录是论文项目的工作区，承载从 **数据构造 → 方法 → 实验 → 评测 → 写作** 的全部产物。
> 论文核心命题：以 **Contextual Integrity (CI)** 替代 PII 中心化的隐私观，对每条请求做
> **task-essential ($\mathcal{E}$) / task-non-essential sensitive ($\mathcal{N}$)** 两分标注，
> 联合度量 *over-disclosure* 与 *over-removal*，并将该标注同时用作 RL 训练信号。
>
> ⚠️ **关于"上次更新时间"**：本目录大量子文件是从其他工作区一次性拷贝过来的（mtime 集中在
> 2026-05-21 22:58 ~ 23:01），因此**子目录内部文件的 mtime 并不代表真实最后修改时间**，
> 仅顶层文件 / 顶层 README 的 mtime 比较可靠。下方时间均为文件系统记录的最后修改时间，
> 对于一次性拷贝进来的内容，可视为"最迟在该时间点已存在"。

---

### 📌 顶层文件 / 目录概览（mtime = 文件系统最后修改时间）

| 路径 | mtime | 用途 |
|---|---|---|
| `main.tex` | 2026-05-21 23:00 | 论文主源文件（≈33 KB）。**注意**：开头注释自称 "LLM-as-a-Judge Assessment subsection"，但实际是整篇论文的主入口，不要被注释误导。 |
| `Introduction.md` | 2026-05-22 23:25 | 英文 Introduction 草稿（LaTeX 片段），围绕 CI 重新形式化 privacy-conscious delegation，提出 ($\mathcal{E},\mathcal{N}$) 标注与三源 benchmark 的贡献。 |
| `Introduction中文设计.md` | 2026-05-22 23:17 | Introduction 的中文设计稿 / 思路推演，比英文版更口语化、含取舍说明。 |
| `todo.md` | 2026-05-22 14:45 | 当前写作 TODO：在纠结是否要把"benchmark"作为主贡献突出；已经做了 benchmark 调研但还在权衡是否要继续细看更多。 |
| `figures_preview.tex` | 2026-05-21 23:30 | 三张主图的 **standalone 预览编译入口**，用 `pdflatex figures_preview.tex` 单独编译 figures。 |
| `figures/` | 2026-05-21 23:29 | 论文 LaTeX 图源（见下文）。 |
| `Data/` | 2026-05-21 23:01 | **数据构造流水线**（论文核心贡献之一）：三条数据来源各一个子目录。 |
| `Experiments/` | 2026-05-21 23:07 | 论文实验/方法相关的 markdown 草稿与 baseline 说明。 |
| `LLMasJudge/` | 2026-05-21 22:59 | LLM-as-a-Judge 评测产物：被评测的 parquet、judged 后的 parquet、分析脚本与图表。 |
| `benchmark_survey/` | 2026-05-22 14:41 | 隐私 benchmark 文献调研（5 项交付物），用于回答 "我们是否构成新 benchmark 贡献" 的问题。 |
| `skills/` | 2026-05-22 14:19 | 写作/绘图风格指南（论文写作 Prompt / 主图设计经验）。 |

---

### 📁 `figures/` — 论文主图 LaTeX 源

| 文件 | mtime | 用途 |
|---|---|---|
| `fig1_teaser.tex` | 2026-05-21 23:28 | Fig.1 Teaser：三栏 before/after 对比（PII 红action vs CI-aware delegation）。 |
| `fig2_data.tex` | 2026-05-21 23:29 | Fig.2 数据构造：反向合成主回路 + 两条辅助轨（WildChat anchor / Medical challenge）。 |
| `fig3_method.tex` | 2026-05-21 23:29 | Fig.3 方法主图：左 training / 右 inference 两面板。 |

> 三张图的预览编译走根目录的 `figures_preview.tex`。

---

### 📁 `Data/` — 数据构造流水线（三源）在git中删去

> 对应论文 §Data Construction，三条来源各一个独立子目录。

#### 📂 `Data/layer1_reverse_synthesis/` — Layer 1：反向合成（合成数据，gold 标签）
拷贝时间 2026-05-21 22:58。生成 `(prompt, essential, nonessential, gold_reformulation)` 四元组，标签先验给定再被独立 judge 反向校验，**通过率约 85%+**，用于 RL 训练时的低延迟 reward 计算。

| 路径 | 用途 |
|---|---|
| `README.md` | 流水线整体说明 / 数据 schema / 设计权衡（≈16 KB，最权威入口）。 |
| `requirements.txt` | 依赖清单。 |
| `command.txt` | 常用 CLI 速查（如 `python scripts/filter_pass.py ...`）。 |
| `demo_synthesis.ipynb` | 合成流水线的 demo notebook。 |
| `test.py` / `test.md` | 临时调试脚本/标注 prompt 草稿（非测试集）。 |
| `todo.md` | Layer 1 自身的 TODO。 |
| `medical_o1_sft.json` | 医学 O1 SFT 原始数据（≈55 MB）。 |
| `config/default.yaml` | 流水线默认配置。 |
| `synth/` | **核心 Python 包**：`taxonomy.py`/`value_bank.py`(域-任务-属性受控词表), `sampler.py`(抽样), `prompts.py`(LLM Prompt), `pipeline.py`(编排), `judge.py`(独立 judge), `llm_client.py`(LLM 调用客户端,≈21 KB,被 Layer 2 复用)。 |
| `scripts/` | CLI 入口：`run_synth.py` 主流程；`pii_tag.py` PII 打标；`filter_pass.py` 过滤未通过；`filter_mcq.py` MCQ 过滤；`stats.py` 统计；`build_demo_notebook.py` 生成 demo；`dryrun_offline.py` 离线 dry-run；`inspect_samples.py` 抽样查看；`contextual_priv/mine_attributes.py` 属性挖掘。 |
| `data/` | 合成产物 JSONL：`smoke*.jsonl` / `small*.jsonl` / `smoke_medqa.jsonl` 等多次迭代版本；子目录 `med/`、`medqa/`、`o1/`、`contextual_priv/` 是按域/数据源分桶。 |
| `Baseline/` | 基线方法：`anonymize.py` 用 Microsoft Presidio 做 PII 红action 作为对照；`anony/` 存放 baseline 输出。 |
| `plan/` | 阶段性计划文档（`med扩展_58.md`、`修改意见_51.md`）。 |
| `reports/attr_frequency.csv` | 属性频次统计。 |

#### 📂 `Data/layer2_nature_dialogue/` — Layer 2：WildChat 自然对话锚点
拷贝时间 2026-05-21 23:00。从 WildChat parquet 切片做单轮过滤、双评委 CI 标注、Faker 假名化，产出 **schema 兼容 Layer 1** 的"真实分布锚点"评测集。

| 路径 | 用途 |
|---|---|
| `README.md` | 流水线说明（≈22 KB），含 S0–S10 全阶段。 |
| `Data.tex` | 写到论文里的 Data Construction 段落 LaTeX。 |
| `intro.md` / `advice.md` | 设计思路与三档必要性等级（essential / helpful / non_essential）说明。 |
| `Protecting Users From Themselves.pdf` | 主要参考论文原文。 |
| `requirements.txt` | 在 Layer 1 之上的额外依赖。 |
| `train-00000~00005-of-00006.parquet` | **WildChat 原始输入分片 6×~250 MB**。 |
| `config/default.yaml` | 3000 行冒烟测试配置。 |
| `config/layer2_full.yaml` | 真实大数据 S0/S1 配置。 |
| `wcanchor/` | **核心 Python 包（"WildChat anchor"）**：`load.py`(S0 parquet→JSONL), `filter_struct.py`(S1 单轮/英文/字数过滤), `screen.py`(S2+S3 内容类型 + CI 担忧二判), `annotate_ci.py`(S4/S5a CI 标注), `concord.py`(S5b 双评委 soft-IoU), `unify.py`(S6 schema 转换), `reformulate.py`(S7 改写), `ethical.py`(S9 假名化), `stats.py`(S10 报告), `prompts.py`(全部 Prompt + 受控词表), `pipeline.py`(全流程编排), `_jsonio.py`(JSONL 工具)。 |
| `process/` | 历史/一次性过程脚本：`s0_s1_load_struct.py`（S0+S1 自包含版本）、`2_filter_suitable.py`/`3_tag_ea_na_A.py`（按 category-A 分类后再打标）、`find.py`(system_prompt 达标筛选)、`length_stats.py`(长度分布)、`new_prompt.py`(检测 contextual privacy violations 的 prompt)。子目录 `stages_full/` / `stages_full_old/` 存阶段 checkpoint。 |
| `scripts/` | CLI：`run_full.py`(端到端)、`inspect_anchor.py`(抽样查看)、`export_for_human.py`(人评模板)、`merge_with_layer1.py`(L1+L2 按比例合并)。 |
| `data/final/`、`data/final_full/`、`data/stages_full_old/` | 不同配置的最终/历史输出（当前为空目录占位）。 |

#### 📂 `Data/Med_data_expand/` — 医疗挑战切片（**注意：名字有误导**）
拷贝时间 2026-05-21 23:01。**虽然目录名是 "Med_data_expand"，但实际是一条完整的医疗 benchmark 构造流水线**：从 `medical_o1_sft_mcq.json` 出发，依次做关键 span 打标 → 问题改写注入 PII → Presidio 标注 → PII 清洗 → 答案选项打标 → 简化字段 → 最终处理（重命名为 `ne` / `key_spans`），不是简单的"数据扩展"。

| 文件 | 用途 |
|---|---|
| `medical_o1_sft_mcq.json` | **原始医学 MCQ 数据**（11 MB）。 |
| `prompt2.py` | 医学 MCQ 改写 prompt（注入 task-irrelevant 个性化 + 合成 PII，保留医学推理）。 |
| `0_label.py` | **Step 0**：用 GPT-4o 给每条 MCQ 打 key-evidence-span 标签（`answer_summary`+`key_spans`），输出 `labels/*.jsonl`。 |
| `1_synthesize_question.py` | **Step 1**：用 `prompt2.py` 把 `Question` 改写为 `Syn_Question`，输出 `syn_questions/`、`1_med2.parquet`。 |
| `2_anonymize.py` | **Step 2**：用 Microsoft Presidio 给 `extra_info["question"]` 做 PII 标注，写回 `extra_info`，输出 `2_.parquet`。 |
| `3_clean_pii_entities.py` | **Step 3**：清洗 `question_pii_entities`，仅保留 PERSON 等关键类别，输出 `3_.parquet`。 |
| `4_打标.py` | **Step 4**：对 prompt 做推理生成 `query_gt`（金标 query），写入 `extra_info.query_gt`，输出 `4_.parquet`。 |
| `5_答案打标.py` | **Step 5**：对自然语言 answer 用 LLM 打标出选项字母（A–E），输出 `5_.parquet`（带 `5_.bak.parquet` 备份）。 |
| `6_simplify_pii_entities.py` | **Step 6.0**：把 PII entity dict 简化为 text 字符串列表。 |
| `6_1_strip_key_spans_reason.py` | **Step 6.1**：剥离 `key_spans` 中的 `reason` 字段，仅保留 span 文本。 |
| `6_2_remove_age_spans.py` | **Step 6.2**：从 `key_spans` 移除年龄表达式（避免与 PII 重叠）。 |
| `6_3_fill_ground_truth.py` | **Step 6.3**：把 `extra_info.query_gt` 回填到 `reward_model.ground_truth`。 |
| `7_最终处理.py` | **Step 7**：字段重命名（`question_pii_entities → ne`，保留 `key_spans`）等收尾工作。 |
| `8_eval_ea_ne.py` | **Step 8**：评估 `priv_query` 相对训练信号 `ea`/`ne` 的表现。 |
| `med.final.parquet` / `med.final.test.parquet` / `med.final.test.600.parquet` / `med.final.train.parquet` | **最终产物**：完整 / 测试 / 600 条测试 / 训练切片。 |
| `med_with_priv_query.parquet` | 中间产物：带改写后 priv_query。 |
| `tem.parquet` | 临时缓存（≈511 KB）。 |
| `1_med2.parquet` ~ `5_.parquet` | 各 step 落地的中间 parquet。 |
| `labels/` | `0_label.py` 的 GPT-4o 打标输出 JSONL + usage 统计。 |
| `labels_gpt-4o_start0_n500_20260515_101049.jsonl` | 早期 500 条打标产物（旧版，2026-05-15）。 |
| `syn_questions/` | `1_synthesize_question.py` 输出（`med2.jsonl` 等）。 |

---

### 📁 `Experiments/` — 实验/方法的 Markdown 草稿
拷贝时间 2026-05-21 23:07。这里**全是 markdown 草稿**，最终会被并入 `main.tex`。

| 文件 | 用途 |
|---|---|
| `intro.md` | baseline 列表（papillon: 用 llama3.1-8b-instruct 本地改写 prompt 等）。 |
| `Data.md` | 数据构造章节草稿（≈6 KB）。 |
| `Method.md` | 方法章节草稿：把 privacy-preserving query rewriting 形式化为 RL 任务（≈5 KB）。 |
| `Experiments.md` | 实验章节骨架（仅 228 B，刚起头）。 |
| `skills.md` | "论文实验结果分析与表述生成"角色 prompt（≈2.6 KB）。 |

---

### 📁 `LLMasJudge/` — LLM-as-a-Judge 评测与分析 就是llm_test_data目录的拷贝 在git中删去
拷贝时间 2026-05-21 22:59。在 cov + BERTScore 双判据之上叠加 LLM 仲裁，做隐私-效用 trade-off 的细粒度判定。

| 路径 | 用途 |
|---|---|
| `our.parquet` / `papillon.parquet` / `prediax.parquet` | **三套被评测的改写结果**（ours / Papillon baseline / Prediax baseline）。 |
| `*_judged.parquet.usage.json` | 对应 judged 跑完后的 LLM 用量统计（不是 judged 数据本身——judged 数据在 `results/`）。 |
| `_backup/our.parquet` 等 | 三套数据的早期备份版本（更大，约 3–4 MB）。 |
| `results/our_judged.parquet` 等 | **真正的 judged 输出**（被打分后的 parquet）。 |
| `results/_inspect_parquet.py` | 简单的 schema/抽样查看脚本。 |
| `results/analyze_judged.py` | **核心分析脚本**（≈37 KB）：从 judged parquet 计算分数分布、隐私问题率、re-id 风险、效用得分、quadrant 分布、failure pattern 等全套指标。 |
| `results/extract_lost_constraint_cases.py` | 抽取代表性的 "lost_constraint"（关键证据被误删）案例。 |
| `results/plot_quadrant_distribution.py` | 画 privacy–utility 四象限分布图（与 analyze_judged 共享象限定义）。 |
| `results/analysis/` | **所有可直接进论文的图表/CSV**：`01_*` 总体统计 + verdict 分布 + 分数直方图；`02_*` 隐私问题计数/率/re-id 风险；`03_*` 效用问题；`04_*` 新发现的敏感类别；`05_*` privacy-utility trade-off 散点 + 四象限（含 .pdf/.png/.csv）；`06_case_studies.md` 案例研究；`07_failure_patterns.*` 失败模式；`08_quadrant_distribution.*` 主表四象限分布；`findings.md` 文字结论。 |
| `image/Experiments.tex` / `image/Experiments.md` / `image/Experiments_old.md` | LLM-as-Judge 实验段落的 LaTeX/Markdown 写作版本（含历史旧稿）。 |
| `image/intro.md` | LLM-as-Judge 的背景说明（说明它是如何叠加在 cov + BERTScore 上的）。 |
| `image/skills.md` | 论文写作角色 prompt（与 `Experiments/skills.md` 内容相近）。 |
| `image/intro/` | 空目录占位（图素材待补）。 |
| `analysis_report/` | 空目录占位。 |

---

### 📁 `benchmark_survey/` — 隐私 benchmark 文献调研
拷贝时间 2026-05-22 14:41。对应论文写作中"我们是否构成 benchmark 贡献"这一问题的调研产物，按交付物结构组织。

| 文件 | mtime | 用途 |
|---|---|---|
| `README.md` | 2026-05-22 14:41 | 调研索引（5 项交付物清单 + self-checklist + 已知局限）。 |
| `benchmarks_main.md` | 2026-05-22 14:41 | **主表**（≈28 KB）：核心候选 benchmark 按统一字段填写（含 Pilan2022, Lukas2023, Mireshghallah2024, Ngong2025 等）。 |
| `benchmarks_secondary.md` | 2026-05-22 14:41 | 副表（≈15 KB）：attack/extraction、域特定、PII detector 工具等。 |
| `dimensions_matrix.md` | 2026-05-22 14:41 | 5 维度矩阵（最有可能直接进 paper 的形式）。 |
| `summary.md` | 2026-05-22 14:41 | 中英双语 ≤200 字总结，仅事实计数、不做"我们更好"的评价。 |
| `open_questions.md` | 2026-05-22 14:41 | 调研中所有 `[TO VERIFY]` 边界决策（如 Prediax baseline 找不到、Ngong2025 是否 release gold E/N 等）。 |

---

### 📁 `skills/` — 写作 / 绘图风格指南
拷贝时间 2026-05-22 14:19。是 **Agent / 自己使用的 prompt 与方法论**，不进论文正文。

| 文件 | mtime | 用途 |
|---|---|---|
| `write_chef.md` | 2026-05-22 14:21 | "顶会论文写作助理"角色 prompt（不能编造事实/引用，所有不确定都标注待确认）。 |
| `draw.md` | 2026-05-22 14:42 | 顶会主图设计方法论（图是"压缩版论证"，先想清楚要让读者完成什么理解动作再选工具）。 |

---

### 🧭 推荐阅读顺序

1. **先读 `Introduction.md`**：理解论文核心命题（CI-grounded delegation, $\mathcal{E}/\mathcal{N}$ 双标）。
2. **再读 `Data/layer1_reverse_synthesis/README.md`**：这是数据构造的最权威入口，理解整个 benchmark 的"先验金标"思路。
3. **然后看 `Data/layer2_nature_dialogue/README.md`**：理解真实分布锚点的 9 阶段流水线。
4. **最后看 `LLMasJudge/results/analyze_judged.py` + `analysis/findings.md`**：理解评测口径与现有结论。
5. 写作前查 `benchmark_survey/dimensions_matrix.md` 和 `skills/write_chef.md`。

---

### ⚠️ 命名陷阱备忘（避免被误导）

| 名称 | 容易误解为 | 实际含义 |
|---|---|---|
| `Med_data_expand` | "医疗数据扩展" | 完整的医疗 benchmark **构造流水线**（打标→改写→PII→答案打标→收尾），不是简单扩展。 |
| `main.tex` 开头注释 | "只是 LLM-as-a-Judge 子节" | 实际是论文整体主入口。 |
| `figures_preview.tex` | 一张主图 | 三张图的 standalone 编译 wrapper。 |
| `LLMasJudge/our.parquet` | "judged 后的输出" | **未 judged 的输入**；judged 输出在 `LLMasJudge/results/*_judged.parquet`。 |
| `LLMasJudge/image/` | 图片素材目录 | 实际是 LaTeX/Markdown **写作稿**目录（`image/intro/` 子目录才是空的图位）。 |
| `LLMasJudge/_backup/*.parquet` | 当前数据的备份 | 早期更大版本的备份，与顶层 parquet **不一一对应**。 |
| `Data/layer1_reverse_synthesis/test.py` / `test.md` | 单元测试 | 临时调试脚本与标注 prompt 草稿。 |
| `Data/layer2_nature_dialogue/process/` vs `wcanchor/` | 看起来重复 | `wcanchor/` 是**正式核心包**；`process/` 是历史/一次性过程脚本（含旧版 stages_full_old）。 |

---

### 📅 mtime 可信度提示

- ✅ **可信（独立编辑过的文件）**：`Introduction.md` (2026-05-22 23:25)、`todo.md` (2026-05-22 14:45)、`benchmark_survey/*` (2026-05-22 14:41)、`skills/*` (2026-05-22 14:19~14:42)、`Introduction中文设计.md` (2026-05-22 23:17)。
- ⚠️ **批量拷贝时间**：`Data/`、`LLMasJudge/`、`Experiments/`、`figures/`、`main.tex`、`figures_preview.tex` 内的所有文件 mtime 都集中在 `2026-05-21 22:58 ~ 23:30` 这一小段时间窗口，是从其它工作区拷贝过来的瞬间，**不代表真实最后修改时间**。如需追溯真实修改史，请回到原始工作区或查看 git log。
