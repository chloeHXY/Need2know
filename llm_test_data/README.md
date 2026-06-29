
# llm_test_data — LLM-as-a-Judge 评测数据与产物

本目录用来存放 **LLM-as-a-Judge（GPT-4o-mini）** 对三套隐私改写系统（**Ours / Papillon / Prediax**）输出的评测数据：包含评测的 **输入**、**输出**、**用量**、**下游分析报告** 与 **论文实验章节文稿**。  
评测脚本位于 `inference/judge/0_judge_gpt4o_mini.py`，评测 Prompt 位于 `judge_prompt.md`。

> 📅 文件最后修改时间均按文件系统 mtime 给出（截至 README 撰写时）。底部附有 [📅 关键时间线](#-关键时间线) 小结，可快速看出整套数据的产出顺序。

> ⚠️ 命名提醒：本目录里有几个文件/目录的名字可能误导，请以下列说明为准。  
> - 根目录下的 `*_judged.parquet.usage.json` 虽然带 `_judged` 后缀，但它**不是 parquet**，而是 sidecar 形式的 JSON 用量统计。  
> - `image/` 这个目录名容易让人以为里面都是图片，但实际上**只放论文实验章节的 `.md` / `.tex` 文稿**，没有图片文件。  
> - `analysis_report/`、`image/intro/` 是**空目录**，只有占位作用，所有真正的分析产物都在 `results/analysis/`。  
> - 真正的图片产物（PNG/PDF）全部位于 `results/analysis/`，不是 `image/`。

---

## 顶层结构总览

```
llm_test_data/                            # (dir, mtime 2026-06-29 12:07)
├── _backup/                              # 原始数据备份（大版本）          (dir, 2026-05-20 03:11)
├── our.parquet                           # Judge 输入：Ours 改写样本(500)  (2026-05-20 03:11)
├── papillon.parquet                      # Judge 输入：Papillon 改写样本    (2026-05-20 03:11)
├── prediax.parquet                       # Judge 输入：Prediax 改写样本     (2026-05-20 03:11)
├── our_judged.parquet.usage.json         # GPT-4o-mini 用量(Ours)          (2026-05-20 13:29)
├── papillon_judged.parquet.usage.json    # 同上(Papillon)                  (2026-05-20 13:29)
├── prediax_judged.parquet.usage.json     # 同上(Prediax)                   (2026-05-20 13:30)
├── results/                              # 评测输出 + 分析脚本 + 可视化     (dir, 2026-05-24 01:53)
├── image/                                # 论文实验章节文稿（不是图片）     (dir, 2026-05-20 23:41)
├── analysis_report/                      # 空目录（占位）                  (dir, 2026-05-20 13:25)
└── README.md                             # 本文件                          (2026-06-29 12:07)
```

---

## 根目录文件

### `our.parquet` / `papillon.parquet` / `prediax.parquet`

这三个是 **LLM-as-a-Judge 的输入**（即 `inference/judge/0_judge_gpt4o_mini.py` 中 `DEFAULT_INPUTS` 列出的文件），每个文件来自不同的隐私改写系统：

| 文件 | 改写系统 | 最后修改 | 说明 |
|---|---|---|---|
| `our.parquet` | **Ours** | 2026-05-20 03:11 | 我们的隐私改写方法的 500 条样本 |
| `papillon.parquet` | **Papillon** | 2026-05-20 03:11 | 用 LLaMA3.1-8B-Instruct 提示词改写得到的 baseline |
| `prediax.parquet` | **Prediax** | 2026-05-20 03:11 | PII 屏蔽 baseline，对识别出的 PII 直接遮盖 |

每行至少包含：
- `extra_info["question"]`：原始问题
- `extra_info["ne"]` / `extra_info["ea"]`：非必要敏感项 / 必要属性
- `priv_query`：该系统给出的隐私改写结果

### `*_judged.parquet.usage.json`

每个文件对应一次 Judge 推理任务的**用量与成本统计**（GPT-4o-mini 通过 Venus LLM 代理调用），格式如下：

```json
{ "calls": 500, "prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ..., "cost_usd": ... }
```

文件命名 `<dataset>_judged.parquet.usage.json` 是为了和真正的输出 `results/<dataset>_judged.parquet` 对齐，**注意它本身不是 parquet**，并且**与对应的 `_judged.parquet` 不在同一个目录**（输出在 `results/`，sidecar JSON 在根目录）。

| 文件 | 最后修改 |
|---|---|
| `our_judged.parquet.usage.json` | 2026-05-20 13:29 |
| `papillon_judged.parquet.usage.json` | 2026-05-20 13:29 |
| `prediax_judged.parquet.usage.json` | 2026-05-20 13:30 |

---

## `_backup/` — 原始数据备份

```
_backup/                       # (2026-05-20 03:11)
├── our.parquet        (3.24 MB,  2026-05-20 03:11)
├── papillon.parquet   (4.03 MB,  2026-05-20 03:11)
└── prediax.parquet    (4.35 MB,  2026-05-20 03:11)
```

这是**完整版本**的三套数据备份。根目录里同名的 `our.parquet / papillon.parquet / prediax.parquet`（约 1 MB 左右）是从这里采样/精简后用作 LLM Judge 输入的版本。如果需要回到全量数据进行重跑或重新采样，使用此目录下的文件。

---

## `results/` — Judge 输出与下游分析

`results/` 同时存放 **Judge 评测输出（parquet）**、**分析脚本（py）**、**典型样例 dump（jsonl）**，并把所有图表/CSV/Markdown 报告统一收敛到子目录 `analysis/` 中。

```
results/                              # (dir, 2026-05-24 01:53)
├── our_judged.parquet                # Ours 的 Judge 输出                 (2026-05-20 13:29)
├── papillon_judged.parquet           # Papillon 的 Judge 输出             (2026-05-20 13:29)
├── prediax_judged.parquet            # Prediax 的 Judge 输出              (2026-05-20 13:30)
├── _inspect_parquet.py               # 速查 parquet schema / 首行小工具    (2026-05-20 15:52)
├── analyze_judged.py                 # 主分析脚本：生成 analysis/01–07     (2026-05-20 13:36)
├── plot_quadrant_distribution.py     # 论文级 quadrant 图：生成 analysis/08 (2026-05-25 18:37)
├── extract_lost_constraint_cases.py  # 挖 lost_constraint 典型 case        (2026-05-20 15:53)
├── added_constraint_cases.jsonl      # added_constraint 样例 dump          (2026-05-24 00:18)
├── new_sensitive_cases.jsonl         # new_sensitive 样例 dump             (2026-05-24 00:20)
└── analysis/                         # 所有报告产物                       (dir, 2026-05-20 14:54)
```

### Parquet 输出文件

`results/our_judged.parquet` / `papillon_judged.parquet` / `prediax_judged.parquet`：在原始输入 parquet 的基础上**追加**以下评测列（由 `inference/judge/0_judge_gpt4o_mini.py` 写入）：

- `judge_raw`：模型原始返回字符串
- `judge_parsed`：解析后 JSON 字符串，含 `privacy_issues / utility_issues / new_sensitive`
- `judge_verdict`：`good` / `acceptable` / `bad`
- `judge_reid_risk`：再识别风险分数 r ∈ [0,1]
- `judge_utility_score`：效用分数 u ∈ [0,1]
- `judge_confidence`：模型自评置信度
- `judge_ok` / `judge_error`：是否解析成功 / 错误原因
- `judge_usage`：本行调用的 token 用量

### 脚本

| 脚本 | 最后修改 | 用途 |
|---|---|---|
| `_inspect_parquet.py` | 2026-05-20 15:52 | 快速检视 `our_judged.parquet` 的列结构与首行内容，调试用 |
| `analyze_judged.py` | 2026-05-20 13:36 | **核心分析脚本**。读取三份 `*_judged.parquet`，输出 `analysis/01_*–07_*` 系列报告（总体统计、隐私 / 效用问题分布、新增敏感属性、tradeoff 散点、case studies、failure pattern、`findings.md`）|
| `extract_lost_constraint_cases.py` | 2026-05-20 15:53 | 从三份 judged parquet 中筛出含 `lost_constraint` 的案例，按"单一效用问题、中等 utility_score、长度合适、source 简短具体"的规则挑选典型样例并打印到控制台（不写文件）|
| `plot_quadrant_distribution.py` | 2026-05-25 18:37 | 基于 `analysis/05_tradeoff_paper_quadrants.csv` 重绘 publication-grade 的四象限分布图，输出 `analysis/08_quadrant_distribution.png/pdf/csv`（**注意**：它依赖 `05_tradeoff_paper_quadrants.csv`，但该 CSV **不是由 `analyze_judged.py` 产出的**，而是手工/外部维护的论文最终汇总；脚本注释里"由 analyze_judged.py 产生"的说法有误）|

### 样例 Dump

| 文件 | 最后修改 | 内容 |
|---|---|---|
| `added_constraint_cases.jsonl` | 2026-05-24 00:18 | 命中 `added_constraint`（改写引入了原本没有的额外约束）的样例，每行 JSON 含 `question / priv_query / added_issues / utility_score / reid_risk / verdict` |
| `new_sensitive_cases.jsonl` | 2026-05-24 00:20 | 命中 `new_sensitive`（改写凭空添加了敏感属性）的样例，每行 JSON 含 `question / priv_query / new_sensitive / utility_score / reid_risk / verdict` |

### `results/analysis/` — 报告产物

由 `analyze_judged.py` 与 `plot_quadrant_distribution.py` 产出。约定：CSV 用于精确数字、PNG/PDF 用于可视化、MD/JSON 用于结论与摘要。

| 文件 | 类型 | 最后修改 | 含义 |
|---|---|---|---|
| `01_overall_stats.csv` | CSV | 2026-05-20 13:36 | 三个数据集 + ALL 的 verdict 分布、reid/utility 均值/中位/方差、Pearson/Spearman 相关 |
| `01_verdict_distribution.png` | 图 | 2026-05-20 13:36 | 三系统 good/acceptable/bad 占比柱状图 |
| `01_score_histograms.png` | 图 | 2026-05-20 13:36 | reid_risk / utility_score 直方图 |
| `02_privacy_issue_counts.csv` | CSV | 2026-05-20 13:36 | 四类隐私问题（direct/semantic/inferential/combination）的样本占比与实例计数 |
| `02_privacy_issue_rates.png` | 图 | 2026-05-20 13:36 | 各系统四类隐私问题的占比对比 |
| `02_privacy_issue_reid_risk.csv` | CSV | 2026-05-20 13:36 | 不同隐私问题类型对应的平均 reid_risk |
| `02_privacy_issue_mean_reid.png` | 图 | 2026-05-20 13:36 | 上表的可视化 |
| `03_utility_issue_counts.csv` | CSV | 2026-05-20 13:36 | 五类效用问题（lost/weakened_constraint, over_generalization, task_drift, added_constraint）的占比 |
| `03_utility_issue_rates.png` | 图 | 2026-05-20 13:36 | 上表的可视化 |
| `03_utility_issue_utility_score.csv` | CSV | 2026-05-20 13:36 | 不同效用问题类型对应的平均 utility_score |
| `03_utility_issue_mean_util.png` | 图 | 2026-05-20 13:36 | 上表的可视化 |
| `04_new_sensitive_items.csv` | CSV | 2026-05-20 13:36 | 所有被判定为"新增敏感属性"的 span（按系统 / 类别拆分） |
| `04_new_sensitive_category_counts.csv` | CSV | 2026-05-20 13:36 | 新增敏感属性按类别计数 |
| `04_new_sensitive_summary.json` | JSON | 2026-05-20 13:36 | 总体新增敏感属性汇总 |
| `04_new_sensitive_categories.png` | 图 | 2026-05-20 13:36 | 类别计数柱状图（ALL）|
| `04_new_sensitive_rate.png` | 图 | 2026-05-20 13:36 | 各系统出现新增敏感属性的样本比例 |
| `05_tradeoff_quadrants.csv` | CSV | 2026-05-20 13:36 | **基于 judged 数据自动算出的**四象限计数与百分比（含 ALL 与三数据集），阈值 utility>0.7、reid≤0.5 |
| `05_tradeoff_scatter.png` | 图 | 2026-05-20 13:36 | 三系统 reid–utility 散点（带抖动 + verdict 上色）|
| `05_tradeoff_paper_quadrants.csv` | CSV | 2026-05-20 14:49 | **论文最终采用的**四象限百分比表（手工/外部维护，列名为 `system, ideal_pct, high_u_high_r_pct, low_u_low_r_pct, worst_pct`），是 `plot_quadrant_distribution.py` 的输入 |
| `05_tradeoff_paper.png` | 图 | 2026-05-20 14:49 | 论文版四象限可视化（早期版本，PNG）|
| `05_tradeoff_paper.pdf` | 图 | 2026-05-20 14:49 | 论文版四象限可视化（早期版本，PDF）|
| `06_case_studies.md` | MD | 2026-05-20 13:36 | 自动挑选的 case study：semantic_leak、inferential_leak、over_generalization、task_drift、严重效用崩溃，每个类型 3 条 |
| `07_failure_patterns.csv` | CSV | 2026-05-20 13:36 | 把抽象失败模式（保留过细描述符 / 仍可识别的改写 / 信息可推断 / 过度抽象 / 引入无关敏感属性 / 任务偏移 / 弱化约束 / 添加约束）映射到具体问题类型并给出占比 |
| `07_failure_patterns.png` | 图 | 2026-05-20 13:36 | 上表 ALL 的横向条形图 |
| `08_quadrant_distribution.csv` | CSV | 2026-05-25 18:36 | `plot_quadrant_distribution.py` 输出的 tidy 长表 |
| `08_quadrant_distribution.png` | 图 | 2026-05-25 18:36 | 论文级四象限分布图（最终版，PNG，带 Ideal/Worst 背景着色）|
| `08_quadrant_distribution.pdf` | 图 | 2026-05-25 18:36 | 论文级四象限分布图（最终版，PDF）|
| `findings.md` | MD | 2026-05-20 13:36 | `analyze_judged.py` 自动总结的关键结论：总体 verdict、隐私/效用问题分布、tradeoff 象限、failure pattern、headline takeaways |

---

## `image/` — 论文实验章节文稿（**不是图片**）

```
image/                     # (dir, 2026-05-20 23:41)
├── Experiments.md         # 实验章节当前版本（精简）         (2026-05-20 23:57)
├── Experiments_old.md     # 实验章节旧版（信息更全）         (2026-05-20 14:53)
├── Experiments.tex        # 实验章节 LaTeX 版本               (2026-05-20 23:41)
├── intro.md               # 任务背景说明                      (2026-05-20 11:44)
├── skills.md              # 论文写作 prompt 模板（与本目录无关）(2026-05-20 11:43)
└── intro/                 # 空目录（占位）                    (dir, 2026-05-20 11:21)
```

- `Experiments.md` / `Experiments_old.md` / `Experiments.tex`：同一节"LLM-as-a-Judge Assessment"的不同版本。**Experiments_old.md** 信息最全，含 verdict 聚合表、隐私失败模式表、效用失败模式分析、幻觉敏感属性分析与 summary；`Experiments.md` 是精简后的当前版本；`Experiments.tex` 是排版到论文里的 LaTeX 版本。
- `intro.md`：项目背景说明，包含 LLM-as-Judge 兜底动机、三套 baseline 介绍、模型/Prompt 与产物路径，可作为本目录的快速索引。
- `skills.md`：一个**通用的论文实验描述生成 prompt**，与本目录数据本身无关，只是放在这里作为写作辅助材料。
- `intro/`：空目录，预留，没有实际内容。

---

## `analysis_report/` — 空目录

`intro.md` 中提到"统计结果目录：`/group/40047/eiraxyhuang/workspace/fc/DataG/llm_test_data/analysis_report`"，但实际所有统计产物均落在 `results/analysis/` 中，本目录目前为空，仅作占位（mtime 2026-05-20 13:25）。后续如需独立沉淀面向汇报的报告，可使用此目录。

---

## 📅 关键时间线

按文件系统 mtime 还原出的工作流时间线：

| 时间 | 事件 |
|---|---|
| **2026-05-20 03:11** | 三套改写系统的原始 parquet 落地（同时存入 `_backup/` 与根目录采样版） |
| 2026-05-20 11:21–11:44 | 起草 `image/intro.md` / `skills.md`，建立 `image/intro/` 占位目录 |
| 2026-05-20 13:25 | 建立 `analysis_report/` 占位目录 |
| **2026-05-20 13:29–13:30** | 跑 LLM-as-Judge：写出 `results/*_judged.parquet` 与根目录三个 `*.usage.json` |
| **2026-05-20 13:36** | 跑 `analyze_judged.py`：生成 `analysis/01_*–07_*` 全套 CSV/PNG + `findings.md` |
| 2026-05-20 14:49 | 手工/外部维护 `analysis/05_tradeoff_paper*` 三件套（论文版四象限） |
| 2026-05-20 14:53–23:57 | 撰写并迭代 `image/Experiments_old.md` → `Experiments.tex` → `Experiments.md` |
| 2026-05-20 15:52–15:53 | 编写辅助小脚本 `_inspect_parquet.py` 与 `extract_lost_constraint_cases.py` |
| **2026-05-24 00:18–00:20** | 补充导出 `added_constraint_cases.jsonl` 与 `new_sensitive_cases.jsonl` |
| **2026-05-25 18:36–18:37** | 最后一次更新：`plot_quadrant_distribution.py` 重绘 `analysis/08_quadrant_distribution.{png,pdf,csv}` |
| 2026-06-29 12:07 | 撰写本 README |

小结：**核心 Judge + 自动分析在 5/20 一天内完成；5/24 补样例 dump；5/25 完成论文级 quadrant 图；之后未再变更数据/脚本。**

---

## 典型使用流程

1. **准备输入**：把三个改写系统的输出写到根目录的 `our.parquet / papillon.parquet / prediax.parquet`（必需列：`priv_query`、`extra_info.question / ne / ea`）。
2. **跑评测**：在仓库根设置好 `ENV_VENUS_OPENAPI_SECRET_ID`，执行
   ```bash
   python inference/judge/0_judge_gpt4o_mini.py
   ```
   产出 `results/<name>_judged.parquet` 与根目录的 `<name>_judged.parquet.usage.json`。
3. **跑分析**：
   ```bash
   python llm_test_data/results/analyze_judged.py
   python llm_test_data/results/plot_quadrant_distribution.py   # 需要先准备好 05_tradeoff_paper_quadrants.csv
   ```
   产出 `results/analysis/` 下全套 CSV / PNG / PDF / Markdown。
4. **挖样例**：
   ```bash
   python llm_test_data/results/extract_lost_constraint_cases.py
   ```
   控制台打印 `lost_constraint` 典型样例，可与 `added_constraint_cases.jsonl` / `new_sensitive_cases.jsonl` 一起作为 case study 素材。
5. **写论文**：直接复用 `image/Experiments.md` 或 `image/Experiments.tex`，并引用 `results/analysis/08_quadrant_distribution.png` 等图表。
