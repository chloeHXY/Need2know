# protect/

本目录实现了论文中"上下文感知隐私改写（Contextual Privacy Reformulation）"流水线的全部脚本与数据。

流水线分 3 个阶段（详见 [`pipeline.md`](./pipeline.md)）：

1. **Context identification** — 判断 query 的 domain 与 task。
2. **Sensitive information classification** — 把敏感信息分为 *essential* / *non-essential* 两类。
3. **Reformulation** — 删除 / 改写 *non-essential* 敏感信息，同时保留用户意图。

> 注：部分文件名（如 `demo.py` / `test2.py` / `1_.py`）与其实际职责并不完全对应，下面表格里给出了真实用途。

---

## 目录速览

| 路径 | 类型 | 最近更新 | 说明 |
| --- | --- | --- | --- |
| [`pipeline.md`](./pipeline.md) | 文档 | 2026-05-24 19:09 | 流水线总览（3 阶段说明）+ 对 `run.py` 的需求约定（输入 parquet、读 `extra_info.question`、写 `priv_query`）。 |
| [`prompt.py`](./prompt.py) | 模块 | 2026-05-24 19:10 | 流水线**正式**使用的 5 个 prompt：`INTENT_DETECTION_PROMPT` / `TASK_DETECTION_PROMPT` / `ESSENTIAL_PROMPT` / `NON_ESSENTIAL_PROMPT` / `REFORMULATION_PROMPT`，由 `run.py` import。 |
| [`run.py`](./run.py) | 脚本 ⭐ | 2026-05-25 12:36 | **主入口**，正式的流水线 runner，支持两种模式：单句测试（`--text "..."`）与 parquet 批处理（`--parquet ...`，默认读 `0_gt_ref.parquet`）。内置 LLM 客户端走内部 OpenAPI（SSE/非 SSE），多线程（`--workers`）+ 断点 checkpoint。 |
| [`test2.py`](./test2.py) | 脚本 | 2026-05-25 12:36 | 内部 OpenAPI（`http://21.119.245.18:81/openapi/chat/completions`）的最小连通性 demo，用于验证 `qwen7b` 在线服务是否可用；`run.py` 的 LLM 客户端就是从它演化而来的。**名字是 "test"，但其实是接口示例。** |
| [`demo.py`](./demo.py) | 脚本 | 2026-05-24 19:05 | **早期/参考实现**：基于 Ollama 本地模型（`llama3.1:8b`）的完整流水线（`contextual_privacy_rewrite`），自带 dynamic / structured 两种敏感信息分类模式，以及一个可选 `evaluate_with_judge`。已被 `run.py` 取代，仅作流程参考。**注意：里面的 `PROMPTS` 是空占位符，不能直接跑。** |
| [`1_.py`](./1_.py) | 文本 | 2026-05-24 19:02 | **草稿文件**：四段 prompt 的早期草稿字符串（`Intent_Detection` / `Task_Detection` / `dynamic_prompt` / `refomulation`），里面还残留 Ollama 的 `{{- if .System }}...{{ end }}` 模板片段。**已被 `prompt.py` 整理替代**，保留作历史参考。 |
| [`0_gt_ref.parquet`](./0_gt_ref.parquet) | 数据 | 2026-05-24 19:08 | 原始 ground-truth / reference parquet（输入），`extra_info.question` 字段存放原始 query。`run.py` parquet 模式默认就是读它。 |
| [`0_gt_ref.priv.parquet`](./0_gt_ref.priv.parquet) | 数据 | 2026-05-25 12:50 | `run.py` 默认输出（`qwen7b` 改写）：在 `0_gt_ref.parquet` 基础上新增 / 覆盖 `priv_query` 列。 |
| [`0_gt_ref.priv_qwen1.5b.parquet`](./0_gt_ref.priv_qwen1.5b.parquet) | 数据 | 2026-05-25 12:14 | 用 Qwen-1.5B 跑同一份输入得到的隐私改写结果。 |
| [`0_gt_ref.priv_llama.parquet`](./0_gt_ref.priv_llama.parquet) | 数据 | 2026-05-24 19:57 | 用 LLaMA 系列模型跑同一份输入得到的隐私改写结果。 |
| [`__pycache__/`](./__pycache__) | 缓存 | 2026-05-24 19:26 | Python 字节码缓存（`prompt.cpython-*.pyc` 等），可随时删除。 |
| [`verl_old/`](./verl_old) | 子项目 | 2026-05-26 02:55 | **GRPO 训练**的 verl 修改版（fork 自 [volcengine/verl](https://github.com/volcengine/verl)）。基于 `Qwen2.5-3B-Instruct` 训练隐私感知查询改写模型，奖励同时考虑 *privacy leakage* 与 *utility preservation*。详见 [`verl_old/README.md`](./verl_old/README.md)。 |
| [`verl_old.zip`](./verl_old.zip) | 归档 | 2026-05-25 22:26 | `verl_old/` 的压缩备份（约 44 MB），方便分发 / 还原。 |
| [`_trash_verl/`](./_trash_verl) | 归档 | 2026-05-26 01:09 | **历史 / 废弃的 verl 工作区**，里面包含 `510eval/`、`math-17k/`、`reward_score_cleanup/`、`my_rollout/`、`recipe/`、`训练说明_priv_rewrite.md`、若干 `rollout_info_priv*.jsonl` 等。仅作归档参考，**不再维护、不参与当前流水线**。 |

---

## 快速开始

```bash
# 1) 单句测试
python run.py --text "My friend Mark, who was just laid off from Google, is looking for a job where he can use ML and Python. Do you have any advice for him?"

# 2) 批处理默认 parquet（输出到 0_gt_ref.priv.parquet）
python run.py --parquet 0_gt_ref.parquet

# 3) 指定模型 / 输出 / 并发
python run.py \
    --parquet 0_gt_ref.parquet \
    --output  0_gt_ref.priv_qwen1.5b.parquet \
    --model   qwen1.5b \
    --workers 20
```

I/O 约定：
- 输入：parquet 中 `extra_info` 列（dict 或 JSON 字符串），从中取 `question` 字段。
- 输出：在原 DataFrame 上新增 / 覆盖 `priv_query` 列，写回 parquet。

## 训练（可选）

参见 [`verl_old/README.md`](./verl_old/README.md)，使用 GRPO 微调 `Qwen2.5-3B-Instruct`，奖励同时计算隐私泄露与效用保留：

```bash
cd verl_old
bash examples/grpo_trainer/run_qwen2_5-3b_gsm8k.sh
```

---

## README 上次更新时间

由于工具无法直接获取本 README 自身的修改时间（这是新建文件），这里给出**本目录主要文件**的最近更新时间（来自文件系统 mtime，时区 +0800）：

| 文件 | 最近更新 |
| --- | --- |
| `run.py` | 2026-05-25 12:36 |
| `test2.py` | 2026-05-25 12:36 |
| `0_gt_ref.priv.parquet` | 2026-05-25 12:50 |
| `0_gt_ref.priv_qwen1.5b.parquet` | 2026-05-25 12:14 |
| `0_gt_ref.priv_llama.parquet` | 2026-05-24 19:57 |
| `0_gt_ref.parquet` | 2026-05-24 19:08 |
| `prompt.py` | 2026-05-24 19:10 |
| `pipeline.md` | 2026-05-24 19:09 |
| `demo.py` | 2026-05-24 19:05 |
| `1_.py` | 2026-05-24 19:02 |
| `verl_old/` | 2026-05-26 02:55 |
| `verl_old.zip` | 2026-05-25 22:26 |
| `_trash_verl/` | 2026-05-26 01:09 |

> 整个 `protect/` 目录最近一次有内容性改动是在 **2026-05-26**（主要是 `verl_old/` 训练子项目的整理与打包），核心流水线脚本（`run.py` / `prompt.py`）最近一次改动是 **2026-05-25**。
