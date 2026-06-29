# Layer 1 — 反向合成流水线 (Reverse Synthesis Pipeline)
## chloe add
git 忽略的文件包括：medical_o1_sft.json
data/o1/medical_o1_sft_mcq.json


面向 **LLM 用户交互隐私保护** benchmark 的第一阶段：**反向合成 (reverse synthesis)** 数据流水线。

> 本目录下的代码与数据为整个 benchmark 项目（DataG）中 “Layer 1” 子模块。
> 与传统 PII 检测不同，本项目关注 **contextual privacy（上下文隐私）**：
> 即用户在 prompt 中披露的敏感信息，是否对当前任务的完成是 *必要* 的。

---

## 1. 项目背景与目标

我们正在构建一个评估 LLM 是否能理解 *上下文隐私* 的挑战集。
同一个敏感属性，在不同任务语境下可能具有完全不同的必要性，例如：

- 在 *糖尿病治疗建议* 任务中，`type 1 diabetes` 是 **essential**；
- 在 *基于解剖定位判断颅神经受累* 的医学题中，`type 1 diabetes` 只是无关背景病史，是 **non-essential**。

Layer 1 流水线通过 *反向合成* 构造 RL 训练 / 评测所需的四元组：

```
(prompt, essential_info, nonessential_sensitive_info, gold_reformulation)
```

合成链路（参见 `synth/pipeline.py`）：

```
Sampler  →  Generator (LLM)  →  Judge (LLM)  →  Consistency Check  →  Reformulator (LLM)  →  JSONL
   spec       raw_prompt         attr extraction     PASS / SOFT / HARD       gold reformulation
```

所有 LLM 调用统一走 **公司内部 Venus LLM 代理**
(`http://v2.open.venus.oa.com/llmproxy/chat/completions`)，
通过环境变量 `ENV_VENUS_OPENAPI_SECRET_ID` 注入 token。

---

## 2. 目录结构 & 最近更新时间

> 时间戳来自文件系统 mtime（北京时间），统计于 `2026-06-29`。

### 2.1 顶层文件

| Path | mtime | 说明 |
| --- | --- | --- |
| `README.md` | 2026-06-29 | 本文件。 |
| `requirements.txt` | 2026-04-30 11:15 | Python 依赖（仅 `httpx`、`pyyaml`）。 |
| `command.txt` | 2026-05-14 03:43 | 常用 run 命令速查（`run_synth` / `filter_pass` / `pii_tag` …）。 |
| `demo_synthesis.ipynb` | 2026-05-11 11:28 | 端到端可运行的 Demo notebook（由 `scripts/build_demo_notebook.py` 生成）。 |
| `medical_o1_sft.json` | 2026-05-14 20:48 | 输入医学推理数据集（FreedomIntelligence/medical-o1-reasoning，用于挖掘自然对照样本）。 |
| `test.md` | 2026-05-14 21:39 | 临时测试笔记。 |
| `test.py` | 2026-05-11 19:44 | 临时测试脚本。 |
| `todo.md` | 2026-05-14 21:26 | 项目背景说明 + 未完成任务清单（contextual privacy 数据挖掘流程）。 |

### 2.2 `synth/` — 合成流水线核心库

| Path | mtime | 说明 |
| --- | --- | --- |
| `synth/__init__.py` | 2026-05-13 21:18 | 包初始化。 |
| `synth/pipeline.py` | 2026-05-13 21:28 | 端到端编排：spec → generator → judge → reformulator → JSONL；带并发、断点续写、状态计数。 |
| `synth/sampler.py` | 2026-05-13 21:59 | `Spec` 采样器（domain / task / essential / nonessential / confusion case）。 |
| `synth/taxonomy.py` | 2026-05-13 21:28 | DOMAINS / TASKS / ATTRIBUTES / 每任务 essential 池 / SUBJECTS / TONES / EMBEDDING_STYLES。 |
| `synth/value_bank.py` | 2026-05-13 21:59 | 各属性的具体取值池（curated lists + 生成器，如 SSN/phone/email）。 |
| `synth/prompts.py` | 2026-05-13 21:28 | Generator / Judge / Reformulator prompt 模板（Judge 参考 Ngong et al. 2025 Appx. E）。 |
| `synth/prompt.tex` | 2026-05-25 17:19 | 论文版 prompt（LaTeX 源）。 |
| `synth/judge.py` | 2026-05-13 21:18 | 解析 judge 输出 + token-overlap & embedding cosine 两阶段匹配，输出 PASS / SOFT_FAIL / HARD_FAIL。 |
| `synth/llm_client.py` | 2026-04-30 17:38 | 异步 OpenAI/Venus 兼容客户端：多端点路由、重试、token & 美元用量统计。 |

### 2.3 `scripts/` — 入口脚本

| Path | mtime | 说明 |
| --- | --- | --- |
| `scripts/run_synth.py` | 2026-05-13 21:59 | **主入口**：`python scripts/run_synth.py --config config/default.yaml --n 1000 --output data/v1.jsonl`。 |
| `scripts/dryrun_offline.py` | 2026-04-30 11:02 | 离线 smoke test（不调用 LLM），仅打印若干 spec 与渲染后的 prompt。 |
| `scripts/filter_pass.py` | 2026-04-30 17:53 | 按 `consistency.status` 过滤 JSONL（默认仅保留 `PASS`）。 |
| `scripts/inspect_samples.py` | 2026-04-30 11:02 | 随机抽样 + ANSI 彩色打印 JSONL 数据，便于人工检查。 |
| `scripts/stats.py` | 2026-04-30 11:02 | 数据集分布统计（domain / task / status / 属性频次等）。 |
| `scripts/pii_tag.py` | 2026-05-13 23:57 | 对 `judge_out.nonessential_attributes` 中各 span 调用 LLM 二分类为 `PII` / `NON_PII`。 |
| `scripts/filter_mcq.py` | 2026-05-14 21:24 | 从 `medical_o1_sft.json` 中筛选含 A/B/C/D 选项的多选题。 |
| `scripts/build_demo_notebook.py` | 2026-05-08 21:29 | 构建 `demo_synthesis.ipynb`。 |
| `scripts/contextual_priv/mine_attributes.py` | 2026-05-14 21:20 | 从 `medical_o1_sft.json` 流式统计敏感属性关键词频次（`reports/attr_frequency.csv`）。 |

### 2.4 `config/` — 运行配置

| Path | mtime | 说明 |
| --- | --- | --- |
| `config/default.yaml` | 2026-05-13 21:59 | 默认配置：generator / reformulator / judge 各自的模型、温度、max_tokens、采样 weights、pipeline 阈值、可选 embedding fallback。 |

### 2.5 `data/` — 合成 / 输入数据

> 详见 `data/README.md`（mtime: 2026-04-30 11:46）。

主要约定：

- `smoke*.jsonl` —— 小规模冒烟测试输出（≤ 100 行）。
- `smoke_58*.jsonl` —— 5/8 阶段产生的批次（含 `clean` 过滤、`tag`/`with_tags` PII 标签合并版本）。
- `smoke_518.jsonl` —— 5/18 批次。
- `smoke_v2.jsonl` —— v2 schema 合成。
- `small.jsonl` / `small.pii.jsonl` —— 用于调试 PII 标注的小样本。
- `layer1_v{N}.jsonl` —— 版本化的正式数据集（建议命名）。

子目录：

| Path | mtime | 说明 |
| --- | --- | --- |
| `data/contextual_priv/` | 2026-05-14 21:20 | 上下文隐私挖掘中间产物。 |
| `data/med/medqa_dev_convo.jsonl` | 2026-05-08 21:46 | stellalisy/mediQ 会话格式数据（dev）。 |
| `data/med/medqa_test_convo.jsonl` | 2026-05-08 21:46 | mediQ test 集。 |
| `data/medqa/phrases_no_exclude_train.jsonl` | 2026-05-13 21:52 | medqa 训练集短语提取。 |
| `data/medqa/phrases_no_exclude_test.jsonl` | 2026-05-13 21:52 | medqa 测试集短语提取。 |
| `data/medqa/_value_bank_cache.json` | 2026-05-13 21:52 | value bank 缓存。 |
| `data/o1/` | 2026-05-15 10:36 | medical-o1 数据打标 / 反向合成子流水线。 |
| `data/o1/medical_o1_sft_mcq.json` | 2026-05-15 10:36 | 多选题筛选输出。 |
| `data/o1/label.py` | 2026-05-15 10:36 | 用 GPT-4o 给 mcq 数据打 key-evidence-span 标签。 |
| `data/o1/prompt.py` / `prompt2.py` | 2026-05-15 10:36 | 打标 / 改写 prompt 模板。 |
| `data/o1/synthesize_question.py` | 2026-05-15 10:36 | 基于 label 输出，用 prompt2 改写为 `Syn_Question`。 |
| `data/o1/labels/labels_gpt-4o_start0_n500_*.jsonl` | 2026-05-15 10:36 | 实际打标输出（500 条，gpt-4o）。 |
| `data/o1/syn_questions/med.jsonl` | 2026-05-15 10:36 | 改写后的 Syn_Question 输出。 |
| `data/o1/skill.md` | 2026-05-15 10:36 | 子任务说明。 |
| `data/o1/command.txt` | 2026-05-15 10:36 | 子任务运行命令。 |

### 2.6 `Baseline/` — Presidio 匿名化基线

| Path | mtime | 说明 |
| --- | --- | --- |
| `Baseline/anonymize.py` | 2026-05-19 22:13 | 用 Microsoft Presidio 匿名化 parquet/jsonl 中的问题字段（基线对比方法）。 |
| `Baseline/test.py` | 2026-05-15 11:08 | Baseline 调试脚本。 |
| `Baseline/skill.md` | 2026-05-15 10:46 | Baseline 任务说明。 |
| `Baseline/anony/command.txt` | 2026-05-15 17:01 | 匿名化运行命令。 |
| `Baseline/anony/med.anonymized.jsonl` | 2026-05-15 17:01 | 对 `data/o1/syn_questions/med.jsonl` 的 Presidio 匿名化结果。 |
| `Baseline/anony/train_data/smoke_58.clean.anonymized.jsonl` | 2026-05-15 17:01 | 训练数据匿名化版本。 |
| `Baseline/anony/train_data/smoke_58.clean.anonymized.with_gpt_answer.jsonl` | 2026-05-15 17:01 | 训练数据匿名化 + GPT 答案版本。 |

### 2.7 `plan/` & `reports/`

| Path | mtime | 说明 |
| --- | --- | --- |
| `plan/修改意见_51.md` | 2026-04-30 11:15 | 5/1 改造计划：从 OpenAI 调用切换到公司 Venus 代理。 |
| `plan/med扩展_58.md` | 2026-05-11 11:28 | 5/8 扩展计划：基于 mediQ 构造 RL 四元组。 |
| `reports/attr_frequency.csv` | 2026-05-14 21:20 | 敏感属性关键词在医学数据中的频次报告（`mine_attributes.py` 输出）。 |

---

## 3. 快速开始

### 3.1 安装依赖

```bash
pip install -r requirements.txt
# 仅需要：httpx[http2]>=0.27 ，pyyaml>=6.0
# 若需要 Baseline/anonymize.py：另需 presidio-analyzer / presidio-anonymizer / pandas / tqdm
```

### 3.2 配置 LLM token

```bash
export ENV_VENUS_OPENAPI_SECRET_ID=<your venus openapi secret id>
```

### 3.3 离线 smoke test（不调 LLM）

```bash
python scripts/dryrun_offline.py --n 3
```

### 3.4 端到端合成

```bash
# 5 条小样本
python scripts/run_synth.py --config config/default.yaml --n 5  --output data/smoke.jsonl

# 600 条
python scripts/run_synth.py --config config/default.yaml --n 600 --output data/smoke_58_3.jsonl
```

运行结束后会打印各端点的 token / USD 用量表（来自 `synth/llm_client.format_usage_table`）。

### 3.5 数据后处理

```bash
# 仅保留 PASS
python scripts/filter_pass.py data/smoke_58_merged.jsonl -o data/smoke_58_merged.clean.jsonl

# 对 nonessential spans 二次打 PII 标签
python scripts/pii_tag.py \
  --config config/default.yaml \
  --input  data/smoke_58.clean.jsonl \
  --output data/smoke_58.clean_tag.jsonl \
  --n 1022

# 数据分布统计
python scripts/stats.py data/smoke_58.clean.jsonl

# 随机抽样彩色打印
python scripts/inspect_samples.py data/smoke_58.clean.jsonl --n 5 --status PASS
```

更多命令见 `command.txt`。

---

## 4. 数据 Schema（合成输出）

每行一个 JSON 对象（参见 `synth/pipeline.py::synthesize_one`）：

```jsonc
{
  "id": "l1-00000123",
  "spec": {
    "domain": "Health_And_Wellness",
    "task": "diet_recommendation",
    "subject": "self",
    "embedding_style": "narrative",
    "tone": "casual",
    "essential_policy": "domain",
    "task_brief": null,
    "essential_info":           [{"attribute": "...", "value": "...", "subject_modifier": null}],
    "nonessential_sensitive_info":[{"attribute": "...", "value": "...", "subject_modifier": null}],
    "confusion_kind": null,
    "notes": [],
    "generator_endpoint": "claude-sonnet-4-6@venus"
  },
  "raw_prompt": "...",
  "judge_out": {
    "primary_context": "...",
    "essential_attributes":    ["..."],
    "nonessential_attributes": ["..."],
    "judge_endpoint": "gpt-4o@venus"
  },
  "consistency": {
    "status": "PASS",            // PASS | SOFT_FAIL | HARD_FAIL
    "essential_recall": 1.0,
    "nonessential_recall": 1.0,
    "score": 1.0,
    "matches": { ... }
  },
  "gold_reformulation": "...",
  "meta": {
    "created_at": "2026-05-13T13:59:00+00:00",
    "schema_version": "1.0",
    "reformulator_endpoint": "gpt-4o@venus",
    "embeddings_used": false
  }
}
```

错误样本：除 `id` / `spec` / `meta` 外，仅含 `error` 字段。

---

## 5. Pipeline 关键参数（`config/default.yaml`）

| 段 | 字段 | 默认 | 说明 |
| --- | --- | --- | --- |
| `generator.models[]` | `claude-sonnet-4-6` | T=0.95 | 多模型路由，按 `weight` 加权抽样以增加表达多样性。 |
| `reformulator.models[]` | `gpt-4o` | T=0.2 | 训练数据上限取决于此处质量，温度调低。 |
| `judge.models[]` | `gpt-4o` | T=0.0 | 与 generator 不同家族，避免同源宽容偏置。 |
| `sampling` | `num_essential_min/max` | 1/2 | 每条 spec 的 essential 属性数。 |
| `sampling` | `num_nonessential_min/max` | 1/3 | 每条 spec 的 NE 属性数。 |
| `sampling` | `confusion_rate` | 0.15 | 制造 `shared_attr` / `over_removal_trap` 的比例。 |
| `pipeline` | `concurrency` | 16 | 异步并发度。 |
| `pipeline` | `pass_threshold` | 0.8 | judge 一致性 PASS 阈值。 |
| `pipeline` | `soft_fail_threshold` | 0.5 | SOFT_FAIL 与 HARD_FAIL 的分界。 |
| `pipeline` | `matcher_token_threshold` | 0.5 | token-overlap 匹配阈值。 |
| `pipeline` | `matcher_cosine_threshold` | 0.65 | embedding cosine 匹配阈值（仅当 embeddings 启用时）。 |
| `embeddings.enabled` | `false` | — | 启用后用 OpenAI text-embedding-3-small 做语义 fallback。 |

---

## 6. 设计要点

1. **三模型解耦**：generator / reformulator / judge 用不同家族模型，避免 *自评偏置*。
2. **两阶段一致性匹配**：先 token-overlap，再 embedding cosine 兜底，覆盖 “同义改写” 场景。
3. **断点续写**：`pipeline.run` 用行缓冲 append 写 JSONL，崩溃后可直接从 `--start-idx` 续跑。
4. **错误容忍**：单样本异常被捕获并写入 `{"id":..., "error":...}`，不中断整批。
5. **用量计费**：`llm_client.UsageTracker` 维护每端点的 prompt/completion tokens & USD（由 `DEFAULT_PRICES` 表换算），跑完打印汇总。

---

## 7. 相关文档

- `todo.md` —— contextual privacy 数据挖掘流程的设计稿。
- `plan/修改意见_51.md` —— Venus 代理改造说明。
- `plan/med扩展_58.md` —— 基于 mediQ 的扩展方案。
- `data/README.md` —— `data/` 命名约定。
- `data/o1/skill.md` —— medical-o1 子任务说明。
- `Baseline/skill.md` —— Presidio 基线说明。

---

## 8. License / Notes

仅供内部研究使用。所有外部数据集（medical-o1-reasoning, mediQ）请遵循其各自原始 license。
