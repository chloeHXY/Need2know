# `Experiments` 目录说明

本目录是隐私保护查询重写（Privacy-Preserving Query Rewriting）实验的主要文档和分析结果汇总。

## 目录结构

```
Experiments/
├── Data.md                          # 数据构建方法文档（反向合成 + 医疗挑战集）
├── Method.md                        # 方法文档（RL框架 + 奖励设计 + GRPO训练）
├── Experiments.md                   # 实验设置大纲（待完善）
├── skills.md                        # 论文实验结果分析与表述生成指南
├── intro.md                         # 项目介绍
├── image/                           # 实验图表目录
│   └── intro/                       # 介绍相关图片
├── Main_results/                    # ★主实验结果★
│   ├── main.csv                     # 核心实验结果表格（Common/Med/wild 三能力）
│   ├── main.png                     # 主结果可视化图表
│   ├── main.tex                     # LaTeX 表格源码
│   ├── exp.tex                      # 实验设置LaTeX源码
│   ├── tables.tex                   # 补充表格LaTeX源码
│   ├── ne&ea.png                    # NE/EA 保留率对比图
│   ├── ea&ne.csv                    # NE/EA 统计数据
│   ├── eval_privacy.py              # 隐私泄漏评测脚本（按 ability 分组）
│   ├── eval_utiility.py             # 效用评测脚本
│   └── res.txt                      # 评测结果摘要
└── __pycache__/                     # Python缓存
```

## 核心文档

### [Data.md](/group/40047/eiraxyhuang/workspace/fc/DataG/Experiments/Data.md)
**数据构建方法论**：
- **反向合成管道**：从结构化语义骨架生成流畅用户提示，确保标签生成而非推断
- **医疗挑战集**：针对"过度删除"失败模式的对抗性测试
- 统一的 $(\mathcal{E},\mathcal{N})$ 抽象：essential spans 必须保留，non-essential spans 应删除

### [Method.md](/group/40047/eiraxyhuang/workspace/fc/DataG/Experiments/Method.md)  
**方法框架**：
- **RL问题形式化**：策略模型 $\pi_\theta$ 生成重写查询 $y \sim \pi_\theta(\cdot \mid x)$
- **复合奖励设计**：
  - $R_{\text{priv}}$：隐私奖励（PII泄漏惩罚）
  - $R_{\text{ess}}$：必要信息保留奖励
  - $L_{\text{brev}}$：长度惩罚
- **GRPO训练**：组相对策略优化，利用组内奖励方差

### [skills.md](/group/40047/eiraxyhuang/workspace/fc/DataG/Experiments/skills.md)
**论文写作指南**：
- 实验结果分析与表述生成规范
- 避免夸张表达，使用稳健学术语言
- 诚实但有策略的结果呈现

## 主实验结果

### [main.csv](/group/40047/eiraxyhuang/workspace/fc/DataG/Experiments/Main_results/main.csv)
**核心结果表格**（按 Common/Med/wild 三能力分组）：

| 模型 | Common-utility | Common-privacy_l | Med-utility | Med-privacy_l | wild-utility | wild-privacy_l |
|------|---------------|------------------|-------------|---------------|--------------|----------------|
| 直接使用llm | / | 100 | 0.795 | 100 | / | 100 |
| prediax(纯pii) | 0.904 | 0.98 | 0.6417 | 0.0183 | 0.855 | 0.6493 |
| llama-3.1-8b-Instruct | 0.874 | 0 | 0.6067 | 0 | 0.87 | 0 |
| Papillon | 0.911 | 0.026 | 0.4917 | 0.4667 | 0.9375 | 0.0435 |
| our | 0.953 | 0.043 | 0.6667 | 0.0417 | 0.9325 | 0.2222 |
| Qwen-2.5-7b-Instruct | 0.911 | 0 | 0.4733 | 0 | 0.8875 | 0 |
| Papillon | 0.943 | 0.057 | 0.59 | 0.55 | 0.9275 | 0.1014 |
| our | 0.977 | 0.043 | 0.62 | 0.0417 | 0.93 | 0.2222 |

**关键发现**：
- **our方法**在 Common 能力上 utility 最高（0.977），privacy leakage 适中（0.043）
- **Med能力**：our方法 utility 显著优于 Papillon（0.620 vs 0.590），privacy leakage 远低于 Papillon（0.0417 vs 0.550）
- **wild能力**：our方法 utility 与 Papillon 相当（0.93 vs 0.9275），但 privacy leakage 较高（0.2222 vs 0.1014）

### [eval_privacy.py](/group/40047/eiraxyhuang/workspace/fc/DataG/Experiments/Main_results/eval_privacy.py)
**隐私泄漏评测脚本**：
- 按 `ability` 字段分组统计 priv_query 隐私泄漏率与 ea 保留率
- 复用 `0_eval.py` 的 Jaccard coverage + BERTScore 阈值逻辑
- 支持大小写不敏感的 haystack 过滤 + 同一行内 PII/NE 项去重
- 输出：stdout 分组指标 + parquet（每行样本）+ csv（汇总表）

### [eval_utiility.py](/group/40047/eiraxyhuang/workspace/fc/DataG/Experiments/Main_results/eval_utiility.py)
**效用评测脚本**：评估重写查询的任务完成能力。

## 实验图表

### [main.png](/group/40047/eiraxyhuang/workspace/fc/DataG/Experiments/Main_results/main.png)
主结果可视化图表，展示各模型在三能力上的表现对比。

### [ne&ea.png](/group/40047/eiraxyhuang/workspace/fc/DataG/Experiments/Main_results/ne&ea.png)
NE（非必要信息）和 EA（必要信息）保留率对比图。

## LaTeX 源码

### [main.tex](/group/40047/eiraxyhuang/workspace/fc/DataG/Experiments/Main_results/main.tex)
主结果表格的 LaTeX 源码，可直接用于论文排版。

### [exp.tex](/group/40047/eiraxyhuang/workspace/fc/DataG/Experiments/Main_results/exp.tex)
实验设置部分的 LaTeX 源码。

## 实验结论

1. **有效性验证**：our方法在隐私保护与任务效用之间取得了良好平衡
2. **领域适应性**：在医疗领域（Med）表现尤为突出，显著降低隐私泄漏的同时保持高效用
3. **trade-off分析**：wild能力上存在隐私-效用权衡，需要进一步优化
4. **baseline对比**：相比纯PII方法和现有baseline，our方法在多指标上表现优越

## 使用说明

1. **查看结果**：直接阅读 `main.csv` 和 `main.png` 了解核心发现
2. **复现评测**：运行 `eval_privacy.py` 和 `eval_utiility.py` 进行自定义评测
3. **论文撰写**：参考 `skills.md` 的表述规范，使用 LaTeX 源码排版表格
4. **深入分析**：结合 `Data.md` 和 `Method.md` 理解实验设计与理论基础

> **注意**：文件名 `eval_utiility.py` 中的 "utiility" 是拼写错误，应为 "utility"，但功能正常。

---

## 文件最后修改时间

> 通过 `ls -la --time-style=long-iso` 获取，时间戳为文件系统的 mtime。

### 顶层文件 / 目录

| 路径 | 最后修改时间 |
|---|---|
| `Data.md` | 2026-05-20 20:54 |
| `Method.md` | 2026-05-20 20:54 |
| `Experiments.md` | 2026-05-21 00:07 |
| `intro.md` | 2026-05-21 01:16 |
| `skills.md` | 2026-05-20 23:58 |
| `image/` (目录) | 2026-05-20 20:51 |
| `Main_results/` (目录) | 2026-05-21 02:50 |
| `README.md` | 2026-06-29 11:57 |

### `Main_results/` 子文件

| 文件 | 最后修改时间 |
|---|---|
| `ea&ne.csv` | 2026-05-20 20:45 |
| `eval_privacy.py` | 2026-05-20 20:47 |
| `eval_utiility.py` | 2026-05-20 20:32 |
| `exp.tex` | 2026-05-21 02:04 |
| `main.csv` | 2026-05-20 20:45 |
| `main.png` | 2026-05-20 20:45 |
| `main.tex` | 2026-05-24 01:53 |
| `ne&ea.png` | 2026-05-20 20:46 |
| `res.txt` | 2026-05-20 20:40 |
| `tables.tex` | 2026-05-20 23:16 |

**时间分布观察**：
- 大部分内容集中在 **2026-05-20 ~ 2026-05-24** 完成（主实验交付期）；
- 唯一近期更新是 `main.tex`（2026-05-24，做了 LaTeX 表格的最终排版）和 `exp.tex`（2026-05-21）；
- `image/` 目录未在主实验后再变动；
- 整体来看，本目录是**已冻结的论文实验交付物**，新工作请走 `inference/` 或 `Exp_llm_as_judge/`。