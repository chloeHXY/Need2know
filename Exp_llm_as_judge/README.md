# `Exp_llm_as_judge` 目录说明

本目录是 LLM-as-Judge（大语言模型作为裁判）实验的完整实现，用于对隐私重写查询进行自动化质量评估。

## 目录结构

```
Exp_llm_as_judge/
├── 0_judge_gpt4o_mini.py          # ★主脚本★ GPT-4o-mini 评测流水线
├── judge_prompt.md                 # 评测系统提示词（JSON格式输出规范）
├── our.parquet                     # our 模型的重写查询数据
├── papillon.parquet                # Papillon baseline 数据
├── prediax.parquet                 # Prediax baseline 数据
├── PUFT.parquet                    # PUFT 模型数据
├── Agents/                         # 智能体分析文档
│   ├── analysis.md                 # 智能体行为分析
│   └── top_tier_nlp_paper_revision.md  # 顶级NLP论文修订指南
├── results/                        # ★评测结果与分析★
│   ├── our_judged.parquet          # our 模型评测结果
│   ├── papillon_judged.parquet     # Papillon 评测结果
│   ├── prediax_judged.parquet      # Prediax 评测结果
│   ├── PUFT_judged.parquet         # PUFT 评测结果
│   ├── analyze_judged.py           # 结果分析脚本（多维度统计+可视化）
│   ├── attribute_PUFT.py           # PUFT 模型归因分析
│   ├── plot_privacy_leak_table.py   # 隐私泄漏表格可视化
│   ├── plot_quadrant_distribution.py # 四象限分布图绘制
│   └── analysis/                   # 详细分析结果
│       ├── 01_overall_stats.csv    # 整体统计
│       ├── 01_score_histograms.png # 分数分布直方图
│       ├── 01_verdict_distribution.png # 裁决分布图
│       ├── 02_privacy_issue_counts.csv # 隐私问题统计
│       ├── 02_privacy_issue_rates.png # 隐私问题率
│       ├── 03_utility_issue_counts.csv # 效用问题统计
│       ├── 03_utility_issue_rates.png # 效用问题率
│       ├── 04_new_sensitive_items.csv # 新增敏感项
│       ├── 04_new_sensitive_categories.png # 敏感项分类
│       ├── 05_tradeoff_scatter.png  # 隐私-效用权衡散点图
│       ├── 06_case_studies.md      # 案例研究
│       ├── 07_failure_patterns.csv # 失败模式分析
│       └── findings.md             # 主要发现总结
├── _backup/                         # 数据备份
│   ├── our.parquet                 # our 原始数据备份
│   ├── papillon.parquet            # Papillon 备份
│   └── prediax.parquet             # Prediax 备份
├── image/                           # 图像资源
│   ├── Experiments.md              # 实验文档
│   ├── intro/                       # 介绍图片
│   └── skills.md                    # 技能文档
├── filter_by_question.py           # 按问题过滤脚本
└── __pycache__/                     # Python缓存
```

## 核心组件

### [0_judge_gpt4o_mini.py](/group/40047/eiraxyhuang/workspace/fc/DataG/Exp_llm_as_judge/0_judge_gpt4o_mini.py)
**主评测脚本**：
- **模型**：GPT-4o（通过 Venus LLM 代理调用）
- **输入**：`our.parquet`、`papillon.parquet`、`prediax.parquet`、`PUFT.parquet`
- **输出**：`*_judged.parquet`（追加评测列）

**评测流程**：
1. **字段提取**：从 `extra_info` 提取 `question`、`priv_query`、`ne_items`、`ea_items`
2. **提示构建**：使用 `judge_prompt.md` 作为系统提示，构建 JSON 格式用户消息
3. **LLM调用**：通过 Venus API 调用 GPT-4o，要求返回结构化 JSON
4. **结果解析**：提取裁决、隐私风险、效用分数、置信度等字段
5. **断点续跑**：支持 `--resume` 模式，跳过已成功评测的行

**输出列**：
- `judge_raw`：原始 LLM 输出
- `judge_parsed`：解析后的 JSON
- `judge_verdict`：裁决（good/acceptable/bad）
- `judge_reid_risk`：重识别风险分数（0-1）
- `judge_utility_score`：效用分数（0-1）
- `judge_confidence`：置信度（0-1）
- `judge_ok`：评测是否成功
- `judge_error`：错误信息
- `judge_usage`：API 使用统计

### [judge_prompt.md](/group/40047/eiraxyhuang/workspace/fc/DataG/Exp_llm_as_judge/judge_prompt.md)
**评测规范文档**：
- **目标**：评估隐私重写查询的质量
- **隐私问题类型**：direct_leak、semantic_leak、inferential_leak、combination_leak
- **效用问题类型**：lost_constraint、weakened_constraint、task_drift、over_generalization、added_constraint
- **评分标准**：reid_risk（0-1）、utility_score（0-1）、confidence（0-1）
- **裁决标准**：good（低风险高效用）、acceptable（轻微问题）、bad（明显问题）

## 数据文件

### 输入数据格式
每个 parquet 文件包含：
- `priv_query`：重写后的隐私保护查询
- `extra_info`：原始信息（包含 question、ne_items、ea_items 等）
- `ability`：能力类型（Common/Med/wild）

### 评测数据集
- **our**：我们的方法产生的重写查询
- **papillon**：Papillon baseline 方法
- **prediax**：Prediax baseline 方法
- **PUFT**：PUFT 模型输出

## 结果分析

### [analyze_judged.py](/group/40047/eiraxyhuang/workspace/fc/DataG/Exp_llm_as_judge/results/analyze_judged.py)
**综合分析脚本**，生成 8 个维度的分析：

1. **整体统计**（`01_*`）：
   - 裁决分布（good/acceptable/bad 比例）
   - reid_risk、utility_score、confidence 的均值/中位数/标准差
   - 隐私风险与效用分数的相关性分析

2. **隐私问题分析**（`02_*`）：
   - 各类隐私问题的出现频率
   - 隐私问题与 reid_risk 的关系
   - 多隐私问题样本统计

3. **效用问题分析**（`03_*`）：
   - 各类效用问题的出现频率
   - 效用问题与 utility_score 的关系
   - 效用问题组合分析

4. **新增敏感项分析**（`04_*`）：
   - 新引入敏感信息的分类统计
   - 敏感项类别分布（位置/医疗/金融/职业等）
   - 各数据集新增敏感项率

5. **权衡分析**（`05_*`）：
   - 隐私-效用权衡散点图（四象限分析）
   - 高效用低风险（理想）、低效用高风险（最差）等象限统计

6. **案例研究**（`06_*`）：
   - 语义隐私泄漏案例
   - 推断性隐私泄漏案例
   - 过度泛化案例
   - 任务漂移案例
   - 严重效用崩溃案例

7. **失败模式分析**（`07_*`）：
   - 抽象失败模式到具体问题类型的映射
   - 模式流行度分析

8. **主要发现**（`findings.md`）：
   - 整体裁决和分数总结
   - 隐私/效用问题分析
   - 新增敏感项统计
   - 权衡分析结果
   - 失败模式总结
   - 关键发现提炼

## 使用指南

### 运行评测
```bash
# 评测所有数据集（默认32个worker）
python 0_judge_gpt4o_mini.py

# 评测单个数据集，限制10行测试
python 0_judge_gpt4o_mini.py --inputs our.parquet --limit 10

# 强制重新评测（覆盖已有结果）
python 0_judge_gpt4o_mini.py --overwrite

# 更多worker加速评测
python 0_judge_gpt4o_mini.py --workers 64
```

### 分析结果
```bash
# 运行完整分析
python results/analyze_judged.py

# 查看主要发现
cat results/analysis/findings.md

# 查看案例研究
cat results/analysis/06_case_studies.md
```

### 环境要求
- **环境变量**：`ENV_VENUS_OPENAPI_SECRET_ID`（Venus API 密钥）
- **Python包**：pandas, requests, tqdm, matplotlib, numpy
- **API成本**：GPT-4o 输入 $5/百万token，输出 $15/百万token

## 技术特点

1. **高可靠性**：支持断点续跑、错误重试、用量统计
2. **结构化输出**：强制 JSON 格式，确保结果可解析
3. **多维分析**：覆盖隐私、效用、新增敏感项等多个维度
4. **可视化支持**：自动生成统计图表和散点图
5. **案例研究**：提供具体失败案例便于问题诊断

## 注意事项

1. **API成本**：大规模评测前建议先用小样本测试
2. **数据备份**：原始数据在 `_backup/` 目录有备份
3. **结果验证**：LLM-as-Judge 结果应与人工评估交叉验证
4. **错误处理**：脚本会自动跳过格式错误的行并记录错误信息

## 实验价值

本实验提供了：
- **自动化评估**：替代人工评估，提高评测效率
- **细粒度分析**：深入理解隐私重写失败模式
- **baseline对比**：客观比较不同方法的优劣
- **改进指导**：识别具体问题类型，指导模型优化

> **提示**：评测结果应结合人工验证，LLM-as-Judge 作为辅助工具而非绝对标准。

---

## 文件最后修改时间

> 通过 `ls -la --time-style=long-iso` 获取，时间戳为文件系统的 mtime。

### 顶层文件 / 目录

| 路径 | 最后修改时间 |
|---|---|
| `0_judge_gpt4o_mini.py` | 2026-05-25 14:55 |
| `0_gt_ref.priv_llama.parquet` | 2026-05-25 14:05 |
| `judge_prompt.md` | 2026-05-25 14:23 |
| `filter_by_question.py` | 2026-05-25 14:09 |
| `our.parquet` | 2026-05-20 17:49 |
| `papillon.parquet` | 2026-05-20 17:49 |
| `prediax.parquet` | 2026-05-20 17:49 |
| `PUFT.parquet` | 2026-05-25 14:09 |
| `our_judged.parquet.usage.json` | 2026-05-25 14:57 |
| `papillon_judged.parquet.usage.json` | 2026-05-25 14:58 |
| `prediax_judged.parquet.usage.json` | 2026-05-25 14:58 |
| `PUFT_judged.parquet.usage.json` | 2026-05-25 14:59 |
| `Agents/` (目录) | 2026-05-21 21:15 |
| `_backup/` (目录) | 2026-05-20 17:49 |
| `image/` (目录) | 2026-05-20 20:41 |
| `results/` (目录) | 2026-05-25 15:15 |
| `README.md` | 2026-06-29 11:59 |

### `Agents/`

| 文件 | 最后修改时间 |
|---|---|
| `analysis.md` | 2026-05-20 18:10 |
| `top_tier_nlp_paper_revision.md` | 2026-05-21 21:16 |

### `_backup/`（首次入库后未再变动）

| 文件 | 最后修改时间 |
|---|---|
| `our.parquet` | 2026-05-20 17:49 |
| `papillon.parquet` | 2026-05-20 17:49 |
| `prediax.parquet` | 2026-05-20 17:49 |

### `results/`

| 文件 | 最后修改时间 |
|---|---|
| `analyze_judged.py` | 2026-05-25 14:34 |
| `attribute_PUFT.py` | 2026-05-25 15:09 |
| `plot_privacy_leak_table.py` | 2026-05-25 15:15 |
| `plot_quadrant_distribution.py` | 2026-05-25 18:38 |
| `our_judged.parquet` | 2026-05-25 14:57 |
| `papillon_judged.parquet` | 2026-05-25 14:58 |
| `prediax_judged.parquet` | 2026-05-25 14:58 |
| `PUFT_judged.parquet` | 2026-05-25 14:59 |

### `results/analysis/`

| 文件 | 最后修改时间 |
|---|---|
| `01_overall_stats.csv` | 2026-05-25 15:03 |
| `01_score_histograms.png` | 2026-05-25 15:03 |
| `01_verdict_distribution.png` | 2026-05-25 15:03 |
| `02_privacy_issue_counts.csv` | 2026-05-25 15:03 |
| `02_privacy_issue_mean_reid.png` | 2026-05-25 15:03 |
| `02_privacy_issue_rates.png` | 2026-05-25 15:03 |
| `02_privacy_issue_reid_risk.csv` | 2026-05-25 15:03 |
| `03_utility_issue_counts.csv` | 2026-05-25 15:03 |
| `03_utility_issue_mean_util.png` | 2026-05-25 15:03 |
| `03_utility_issue_rates.png` | 2026-05-25 15:03 |
| `03_utility_issue_utility_score.csv` | 2026-05-25 15:03 |
| `04_new_sensitive_categories.png` | 2026-05-25 15:03 |
| `04_new_sensitive_category_counts.csv` | 2026-05-25 15:03 |
| `04_new_sensitive_items.csv` | 2026-05-25 15:03 |
| `04_new_sensitive_rate.png` | 2026-05-25 15:03 |
| `04_new_sensitive_summary.json` | 2026-05-25 15:03 |
| `05_tradeoff_quadrants.csv` | 2026-05-25 15:03 |
| `05_tradeoff_scatter.png` | 2026-05-25 15:03 |
| `06_case_studies.md` | 2026-05-25 15:03 |
| `07_failure_patterns.csv` | 2026-05-25 15:03 |
| `07_failure_patterns.png` | 2026-05-25 15:03 |
| `08_quadrant_distribution.csv` | 2026-05-25 18:39 |
| `08_quadrant_distribution.pdf` | 2026-05-25 18:39 |
| `08_quadrant_distribution.png` | 2026-05-25 18:39 |
| `09_privacy_leak_table.csv` | 2026-05-25 15:15 |
| `09_privacy_leak_table.md` | 2026-05-25 15:15 |
| `09_privacy_leak_table.pdf` | 2026-05-25 15:15 |
| `09_privacy_leak_table.png` | 2026-05-25 15:15 |
| `09_privacy_leak_table.tex` | 2026-05-25 15:15 |
| `findings.md` | 2026-05-25 15:03 |
| `PUFT/` (目录) | 2026-05-25 15:11 |

### `results/analysis/PUFT/`

| 文件 | 最后修改时间 |
|---|---|
| `length_buckets_our.csv` | 2026-05-25 15:09 |
| `length_buckets_papillon.csv` | 2026-05-25 15:09 |
| `length_buckets_prediax.csv` | 2026-05-25 15:09 |
| `length_buckets_PUFT.csv` | 2026-05-25 15:09 |
| `length_corr.csv` | 2026-05-25 15:09 |
| `len_stats.csv` | 2026-05-25 15:09 |
| `lost_constraint_counts.csv` | 2026-05-25 15:09 |
| `lost_constraint_per_sample.png` | 2026-05-25 15:09 |
| `lost_reason_clusters_PUFT.csv` | 2026-05-25 15:09 |
| `lost_span_tokens_others.csv` | 2026-05-25 15:09 |
| `lost_span_tokens_PUFT.csv` | 2026-05-25 15:09 |
| `PUFT_attribution.md` | 2026-05-25 15:11 |
| `PUFT_by_verdict.csv` | 2026-05-25 15:09 |
| `PUFT_collapse_cases.md` | 2026-05-25 15:09 |
| `PUFT_good_cases.md` | 2026-05-25 15:09 |
| `PUFT_len_vs_util.png` | 2026-05-25 15:09 |

**时间分布观察**：
- **2026-05-20 17:49**：`_backup/` 与 `our/papillon/prediax.parquet` 一同入库（初始基线数据）；
- **2026-05-21**：完成 `Agents/top_tier_nlp_paper_revision.md` 论文修订指南；
- **2026-05-25 14:00–15:15**：评测主流程集中跑完——先 `judge_prompt.md` / `0_judge_gpt4o_mini.py` / `PUFT.parquet` 准备就绪，再在 14:57–14:59 依次产出 4 份 `*_judged.parquet`，随后 15:03 跑 `analyze_judged.py` 出 01–07 系列分析，15:09–15:11 跑 `attribute_PUFT.py` 出 `PUFT/` 子目录归因分析，15:15 跑 `plot_privacy_leak_table.py` 出 09 系列；
- **2026-05-25 18:38–18:39**：`plot_quadrant_distribution.py` 单独跑出 08 系列象限分布图；
- 整体来看，本目录是 **2026-05-25 一天内完成的"裁判打分 + 多维分析"完整产出**，之后未再变动（当前 README 由本次会话写入）。