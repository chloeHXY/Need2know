# Layer 2 — Natural-Dialogue Anchor (WildChat)
## 我的补充
A 与 B 不是"两套并行的方法"或"两位 judge"，而是同一份数据按"上下文隐私适用性 (contextual privacy suitability)"做的二级类别。

A/B 来自 find.py 中那段 system prompt 定义的 A/B/C/D/E 五分类，由 gpt-4o-mini 在阶段 2 给每条 WildChat 单轮 query 打的标签：
A: 请求型 query；含敏感信息；至少有一些敏感信息看起来与任务无关 / 过度披露 —— 这是 benchmark 最想要的"金样本"b:
B: 请求型 query；含敏感信息；但大多数甚至全部敏感信息可能都是任务必需的 —— 作为 hard / borderline 例子保留


Layer-2 子项目，用于从公开的 **WildChat** 真实用户—LLM 对话中，
按照与 Layer-1 reverse-synthesis 完全一致的 `(E, N)` 上下文隐私
（contextual privacy）协议，挖掘并标注一组 **自然对话锚点集
(natural-dialogue anchor set)**。

它的作用是给 reverse-synthesized 训练集补一个 **out-of-distribution
真实分布探针** —— 检验在合成数据上训练的 rewriter 是否能在真实
用户措辞下仍然正确识别 **必要 (essential)** 与 **非必要
(non-essential) 敏感披露**。

> 方法论摘要：每条样本都标注两组互不相交的属性集合：
> `E = {essential spans}`（任务必需，必须保留）和
> `N = {non-essential sensitive spans}`（应被删除或泛化）。
> 详细动机见 `Data.tex` 第 §4 节，操作建议见 `advice.md`。

---

## 1. 流水线总览

源数据 → 6 个 WildChat parquet 分片（≈352k 条原始对话）。

```
S0  load            parquet → 00_loaded.jsonl          (单轮 user 消息抽取)
S1  struct_filter   deterministic, no-LLM             → 01_struct.jsonl
                                                       01_struct_anchor.jsonl  (redacted 旁路)
S2+S3 screen        gpt-4o-mini   内容类型 + CI flag    → 02_screen.jsonl
                                                       03_screen_passed.jsonl
S4  judge_a         gpt-4o        full CI 标注          → 04_judge_a.jsonl
S5  judge_b         deepseek-chat 跨家族第二意见         → 05_judge_b.jsonl
                    + concord soft-IoU 一致性判定       → 06_concord.jsonl
S6  unify           合并两位 judge                      → 07_unified.jsonl
S7  reformulate     gpt-4o-mini 生成 gold rewrite       → 08_reformulated.jsonl
S9  ethical         姓名/邮箱/电话等 PII 泛化           → final/*.public.jsonl
S10 stats           漏斗 + 分布报告                     → final/report.md
```

S1 的关键约束：**single-turn / English / non-toxic /
non-redacted / 25–250 words**（见 `config/layer2_full.yaml`）。
`redacted=True` 的行会被旁路到 `*_anchor.jsonl`，作为天然 PII 锚池。

最终目标产物：
- `data/final_full/wildchat_anchor.eval.jsonl`   —— 评测用，全部 PASS
- `data/final_full/wildchat_anchor.public.jsonl` —— ethical sanitizer 后

---

## 2. 目录结构

```
layer2_nature_dialogue/
├── README.md                        # 本文件
├── Data.tex                         # 论文 §Data 章节（含 reverse-synth + 本锚集）
├── advice.md                        # 真实交互数据 benchmark 化的 8 条要点
├── intro.md                         # （占位，空）
├── Protecting Users From Themselves.pdf   # 参考论文：Ngong et al. contextual privacy
├── requirements.txt
├── __init__.py
│
├── config/
│   ├── default.yaml                 # 烟测配置（3000 行子集）
│   └── layer2_full.yaml             # 全量分片配置（train-00000/00001 两片）
│
├── wcanchor/                        # 主流水线包（S0–S10）
│   ├── pipeline.py                  # End-to-end orchestrator
│   ├── load.py                      # S0  parquet → jsonl
│   ├── filter_struct.py             # S1  deterministic 结构过滤
│   ├── screen.py                    # S2+S3 内容类型 + CI 标记
│   ├── annotate_ci.py               # S4/S5 双 judge CI 标注
│   ├── concord.py                   # S5 soft-IoU 一致性
│   ├── unify.py                     # S6 合并 judge
│   ├── reformulate.py               # S7 gold rewrite
│   ├── ethical.py                   # S9 PII 泛化
│   ├── stats.py                     # S10 漏斗/分布
│   ├── prompts.py                   # 所有 LLM prompt 模板
│   └── _jsonio.py                   # jsonl 读写工具
│
├── process/                         # 早期独立脚本（不依赖 wcanchor 包）
│   ├── s0_s1_load_struct.py         # S0+S1 离线版本
│   ├── 2_filter_suitable.py         # 基于 find.py 的 A/B/C/D/E 五分类筛选
│   ├── 3_tag_ea_na_A.py             # 对 A 类样本抽取 (primary_context, E, N)
│   ├── find.py                      # 适用性筛选 prompt
│   ├── new_prompt.py                # E/N 抽取 prompt
│   ├── length_stats.py              # 字数分布统计
│   ├── stages_full/                 # 当前在跑的全量阶段输出
│   │   ├── 00_loaded.jsonl          # ~525 MB
│   │   ├── 01_struct.jsonl          # ~40 MB
│   │   ├── 01_struct_anchor.jsonl   # redacted 锚池
│   │   ├── 02_suitable.jsonl        # 全量 A/B/C/D/E 标注
│   │   ├── 02_suitable.A.jsonl      # 仅 A 类
│   │   ├── 02_suitable_B.jsonl
│   │   ├── 03_ea_na_A.jsonl         # A 类 E/N 抽取（最终候选锚集）
│   │   ├── 03_ea_na_B.jsonl
│   │   └── *.usage.json             # token 用量统计
│   └── stages_full_old/             # 旧版（word_max=2500）阶段产物，仅留档
│
├── scripts/
│   ├── run_full.py                  # wcanchor.pipeline 的 CLI 入口
│   ├── inspect_anchor.py            # 抽样人工检查
│   ├── export_for_human.py          # 导出人工复核 csv
│   └── merge_with_layer1.py         # 与 Layer-1 reverse-synth 合并
│
├── data/
│   ├── final/                       # （空，烟测预留）
│   ├── final_full/                  # （空，最终产物预留）
│   └── stages_full_old/             # 旧版结构过滤输出
│
└── train-0000{0..5}-of-00006.parquet   # WildChat 6 个原始分片，共 ~1.5 TB raw
```

---

## 3. 如何运行

```bash
# 全量 S0+S1（结构过滤，纯本地，无 LLM 调用）
python scripts/run_full.py --config config/layer2_full.yaml --stop-after struct
# 【chloe】这里不对，实际上主要的处理逻辑都在/group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/process/s0_s1_load_struct.py
python s0_s1_load_struct.py 

# 在 S1 输出上跑 2_filter_suitable + 3_tag_ea_na_A（独立路线）
cd process
python 2_filter_suitable.py --workers 32
python 3_tag_ea_na_A.py     --workers 32

# 端到端 wcanchor 流水线（需要 OPENAI_API_KEY / DEEPSEEK_API_KEY）
python scripts/run_full.py --config config/default.yaml
```
【chloe】我们真的完整下载了整个wild-chat的6个parquet,开始处理了0&1，放到了stages_full_old中，后来一次性处理完了2345然后放到了stages_full中，虽然paper中我们说是352k,实际上这只是2345的量，但是鉴于我们筛选太苛刻，所以这里就写352k也没关系。
核心的流水线漏斗处理代码基本上都在process里面

---

## 4. 文件最近更新时间

> 以下时间戳来自文件系统 `mtime`，时区为运行环境本地时区
> （列表生成时间 **2026-06-29 17:39**，单位 `YYYY-MM-DD HH:MM`）。
> 大文件（parquet / jsonl checkpoint）大小同时给出，便于核对。

### 4.1 顶层文件

| 文件 | 大小 | 最近更新 |
|---|---:|---|
| `Data.tex` | 7.3 KB | 2026-05-21 04:06 |
| `advice.md` | 8.5 KB | 2026-05-18 04:22 |
| `intro.md` | 0 B | 2026-05-21 02:59 |
| `Protecting Users From Themselves.pdf` | 1008 KB | 2026-05-18 04:22 |
| `requirements.txt` | 244 B | 2026-05-18 04:22 |
| `__init__.py` | 68 B | 2026-05-18 04:22 |

### 4.2 配置

| 文件 | 大小 | 最近更新 |
|---|---:|---|
| `config/default.yaml` | 5.3 KB | 2026-05-18 04:22 |
| `config/layer2_full.yaml` | 2.9 KB | 2026-05-18 15:12 |

### 4.3 `wcanchor/`（主流水线包）

| 文件 | 大小 | 最近更新 |
|---|---:|---|
| `wcanchor/__init__.py` | 2.0 KB | 2026-05-18 04:41 |
| `wcanchor/_jsonio.py` | 1.9 KB | 2026-05-18 04:22 |
| `wcanchor/load.py` | 4.2 KB | 2026-05-18 04:39 |
| `wcanchor/filter_struct.py` | 2.0 KB | 2026-05-18 04:22 |
| `wcanchor/screen.py` | 3.9 KB | 2026-05-18 15:17 |
| `wcanchor/annotate_ci.py` | 4.9 KB | 2026-05-18 04:22 |
| `wcanchor/concord.py` | 8.8 KB | 2026-05-18 04:22 |
| `wcanchor/unify.py` | 8.0 KB | 2026-05-18 04:22 |
| `wcanchor/reformulate.py` | 2.3 KB | 2026-05-18 04:22 |
| `wcanchor/ethical.py` | 6.3 KB | 2026-05-18 04:22 |
| `wcanchor/stats.py` | 5.0 KB | 2026-05-18 04:22 |
| `wcanchor/prompts.py` | 14.0 KB | 2026-05-18 04:22 |
| `wcanchor/pipeline.py` | 14.6 KB | 2026-05-18 04:39 |

### 4.4 `process/`（独立处理脚本）

| 文件 | 大小 | 最近更新 |
|---|---:|---|
| `process/s0_s1_load_struct.py` | 12.7 KB | 2026-05-19 13:47 |
| `process/find.py` | 5.1 KB | 2026-05-18 19:14 |
| `process/new_prompt.py` | 2.0 KB | 2026-05-18 16:13 |
| `process/2_filter_suitable.py` | 17.9 KB | 2026-05-19 13:51 |
| `process/3_tag_ea_na_A.py` | 15.5 KB | 2026-05-19 16:22 |
| `process/length_stats.py` | 3.7 KB | 2026-05-21 03:33 |

### 4.5 `process/stages_full/`（当前全量阶段产物）

| 文件 | 大小 | 最近更新 |
|---|---:|---|
| `00_loaded.jsonl` | 525.5 MB | 2026-05-19 13:48 |
| `01_struct.jsonl` | 39.7 MB | 2026-05-19 13:49 |
| `01_struct_anchor.jsonl` | 325.7 KB | 2026-05-19 13:49 |
| `02_suitable.jsonl` | 71.2 MB | 2026-05-19 14:53 |
| `02_suitable.A.jsonl` | 967.1 KB | 2026-05-19 14:53 |
| `02_suitable_B.jsonl` | 110.7 KB | 2026-05-19 16:22 |
| `02_suitable.jsonl.usage.json` | 134 B | 2026-05-19 14:53 |
| `03_ea_na_A.jsonl` | 579.0 KB | 2026-05-19 15:47 |
| `03_ea_na_A.jsonl.usage.json` | 146 B | 2026-05-19 15:41 |
| `03_ea_na_B.jsonl` | 141.1 KB | 2026-05-19 16:23 |
| `03_ea_na_B.jsonl.usage.json` | 142 B | 2026-05-19 16:23 |

### 4.6 `process/stages_full_old/`（旧版留档，`word_max=2500`）

| 文件 | 大小 | 最近更新 |
|---|---:|---|
| `00_loaded.jsonl` | 203.4 MB | 2026-05-18 04:41 |
| `01_struct.jsonl` | 27.2 MB | 2026-05-18 04:54 |
| `01_struct_anchor.jsonl` | 239.7 KB | 2026-05-18 04:54 |
| `01_struct_lt150.jsonl` | 12.5 MB | 2026-05-18 16:18 |
| `01_struct_lt250.jsonl` | 18.7 MB | 2026-05-18 16:16 |
| `02_ea_na.jsonl` | 25.4 MB | 2026-05-18 17:29 |
| `02_ea_na.jsonl.usage.json` | 132 B | 2026-05-18 17:29 |
| `02_ea_na.smoketest.jsonl` | 11.7 KB | 2026-05-18 16:25 |
| `02_ea_na.smoketest.jsonl.usage.json` | 118 B | 2026-05-18 16:25 |
| `02_screen.jsonl` | 33.3 MB | 2026-05-18 16:00 |
| `03_ea_na_with_na.jsonl` | 9.7 MB | 2026-05-18 17:34 |
| `03_screen_passed.jsonl` | 1.2 MB | 2026-05-18 16:00 |
| `04_consensus.jsonl` | 20.0 MB | 2026-05-18 17:55 |
| `04_consensus.jsonl.usage.json` | 240 B | 2026-05-18 17:55 |
| `04_consensus.pass.jsonl` | 3.5 MB | 2026-05-18 17:55 |
| `04_consensus.smoketest.jsonl` | 35.8 KB | 2026-05-18 17:41 |
| `04_consensus.smoketest.jsonl.usage.json` | 218 B | 2026-05-18 17:41 |
| `04_consensus.smoketest.pass.jsonl` | 10.4 KB | 2026-05-18 17:41 |
| `05_suitable.jsonl` | 32.8 MB | 2026-05-18 19:46 |
| `05_suitable.jsonl.usage.json` | 133 B | 2026-05-18 19:46 |
| `05_suitable.A.jsonl` | 474.6 KB | 2026-05-18 19:46 |
| `05_suitable_B.jsonl` | 40.7 KB | 2026-05-19 16:21 |
| `06_ea_na_A.jsonl` | 408.2 KB | 2026-05-18 20:03 |
| `06_ea_na_A.jsonl.usage.json` | 145 B | 2026-05-18 20:02 |

### 4.7 `scripts/`

| 文件 | 大小 | 最近更新 |
|---|---:|---|
| `scripts/run_full.py` | 2.3 KB | 2026-05-18 04:39 |
| `scripts/inspect_anchor.py` | 3.4 KB | 2026-05-18 04:22 |
| `scripts/export_for_human.py` | 4.1 KB | 2026-05-18 04:22 |
| `scripts/merge_with_layer1.py` | 5.1 KB | 2026-05-18 04:22 |

### 4.8 `data/`

| 文件 | 大小 | 最近更新 |
|---|---:|---|
| `data/final/` | （空） | 2026-05-18 04:22 |
| `data/final_full/` | （空） | 2026-05-18 04:39 |
| `data/stages_full_old/01_struct.w2500.jsonl` | 62.2 MB | 2026-05-18 04:41 |
| `data/stages_full_old/01_struct_anchor.w2500.jsonl` | 924.0 KB | 2026-05-18 04:41 |

### 4.9 WildChat 原始分片

| 文件 | 大小 | 最近更新 |
|---|---:|---|
| `train-00000-of-00006.parquet` | 277.3 MB | 2026-05-18 01:44 |
| `train-00001-of-00006.parquet` | 257.7 MB | 2026-05-18 04:29 |
| `train-00002-of-00006.parquet` | 266.7 MB | 2026-05-19 13:41 |
| `train-00003-of-00006.parquet` | 256.3 MB | 2026-05-19 13:46 |
| `train-00004-of-00006.parquet` | 234.7 MB | 2026-05-19 13:46 |
| `train-00005-of-00006.parquet` | 220.4 MB | 2026-05-19 13:46 |

---

## 5. 重要约定与提醒

1. **不要把真实数据等同于真实隐私风险** —— 真实 prompt 中存在
   玩笑、引文、虚构角色、翻译/润色任务等噪声，必须先做任务适配筛选。
2. **必须标注必要性 (necessity)，否则会退化为 PII benchmark**。
   每条 sensitive span 至少标注 `subject / sensitivity_type /
   necessity / recommended_action / rationale`。
3. **判分使用异质模型** —— generator 与 judge 必须跨家族
   （e.g. Claude 生成 / GPT-4o judge；judge_a=GPT-4o，
   judge_b=DeepSeek-Chat），避免 co-adaptation。
4. **发布前必须 ethical sanitize**：替换姓名、邮箱、电话、地址、SSN、
   驾照号；高再识别风险样本直接丢弃而非匿名化。
5. **核心测试集需要人工复核** —— LLM judge 容易把虚构当真实、
   把第三方信息漏报；务必走 `scripts/export_for_human.py`。

更详细的方法论与做法请阅读同目录下的 `Data.tex`（论文章节）和
`advice.md`（落地建议）。
