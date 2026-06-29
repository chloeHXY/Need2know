
# DataG 目录 Timeline 总览

> 统计依据：每个一级子目录中**最新被修改的文件**（已忽略 `README.md` / `readme.md`）。
> 空目录则使用其目录自身的 mtime；时间格式 `YYYY-MM-DD HH:MM`。
> 用于辅助按时间倒推工作脉络。

---

## 一、按时间倒序的总表

| 排序 | 目录 | 最新修改时间 | 触发文件（最新） |
| --- | --- | --- | --- |
| 1  | `tem/`                     | 2026-06-29 15:09 | （空目录，mtime） |
| 2  | `prediax/`                 | 2026-06-29 14:50 | `4_priv_eval.py` |
| 3  | `inference/`               | 2026-06-29 14:35 | `mix_data/4_sum_111.csv`、`mix_data/4_eval_ability_111.parquet`、`0_privacy/0_eval_by_ability.py` |
| 4  | `protect/`                 | 2026-05-26 02:55 | `verl_old/Need2Know.zip` |
| 5  | `update_data/`             | 2026-05-26 02:50 | `data.jsonl` 这个应该是最后上传数据集的时候|
| 6  | `Exp_llm_as_judge/`        | 2026-05-25 18:39 | `results/analysis/08_quadrant_distribution.{pdf,png,csv}` |
| 7  | `llm_test_data/`           | 2026-05-25 18:37 | `results/plot_quadrant_distribution.py` |
| 8  | `layer1_reverse_synthesis/`| 2026-05-25 17:19 | `synth/prompt.tex` |
| 9  | `papillon/`                | 2026-05-25 02:24 | `step4_eval_result.parquet` |
| 10 | `Experiments/`             | 2026-05-24 01:53 | `Main_results/main.tex` |
| 11 | `Paper/`                   | 2026-05-22 23:25 | `Introduction.md` |
| 12 | `info/`                    | 2026-05-21 21:08 | `data.md` |
| 13 | `layer2_nature_dialogue/`  | 2026-05-21 04:06 | `Data.tex` |
| 14 | `wild/`                    | 2026-05-19 16:15 | `tem.parquet`、`1_eval_ea_ne.py` |
| 15 | `Med_data_expand/`         | 2026-05-19 19:14 | `med.final.test.600.parquet` |
| 16 | `writing/`                 | 2026-05-18 20:27 | `paper.md` |
| 17 | `papillon_old/`            | 2026-05-18 16:08 | `abstract_examples.jsonl` |
| 18 | `need2know/`               | 2026-05-18 16:03 | （空目录，mtime） |
| 19 | `other/`                   | 2026-05-18 02:16 | `train_subset_3000.parquet` |
| 20 | `pupa/`                    | 2026-05-17 23:18 | `step5_privacy.py`、`5_eval_.parquet` |
| 21 | `papillon_pupa/`           | 2026-05-17 23:16 | `step5_privacy_result.parquet` |
| 22 | `prediax_old/`             | 2026-05-17 21:05 | `4_priv_eval.parquet` |
| 23 | `z_eval/`                  | 2026-05-17 21:05 | `eval_privacy/com_privacy_score.py` |
| 24 | `papillon_privacy/`        | 2026-05-17 20:49 | `0_eval.py`、`0_pp_eval_result.parquet`、`test_with_priv_query_with_pii.parquet` |
| 25 | `med_new/`                 | 2026-05-17 15:13 | `parquet_to_jsonl.py` |
| 26 | `verl_old/`                | 2026-05-16 23:01 | `scripts/key_spans_hit_rate.py` |
| 27 | `model_hf/`                | 2026-05-16 22:54 | `roberta-large/pytorch_model.bin` 等 |
| 28 | `ray_tmp/`                 | 2026-05-16 18:30 | `ray/session_2026-05-16_18-30-34_257970_48465/node_ip_address.json` |
| 29 | `our_med/`                 | 2026-05-16 16:22 | `eval_result.parquet`、`eval.py` |
| 30 | `merge_inference/`         | 2026-05-12 04:10 | `skill.md`（注：仅含 `.md`，但非 README） |
| 31 | `.vscode/`                 | 2026-05-12 01:13 | `settings.json` |
| 32 | `examples/`                | 2026-04-30 11:14 | `formal.py` |
| 33 | `__MACOSX/`                | 2026-04-30 11:02 | macOS 解压元数据文件 |

---

## 二、按时间分段的行为路径推断

### 阶段 0：引入外部代码 / 解压（2026-04-30）
- `__MACOSX/`、`examples/` —— 早期从外部拷贝来的代码与 `infer_fc_*.py`、`fc_class.py` 示例。

### 阶段 1：早期试验（2026-05-12）
- `.vscode/`：项目初始化，IDE 配置。
- `merge_inference/`：第一次跑 merge_inference 流程（含 `test_with_priv_query_add_gptinfo.parquet`、`test_with_merge_inference.parquet`）。

### 阶段 2：医疗数据基线（2026-05-16）
- `our_med/` → `merge_inference.py` / `eval.py` / `inference.py` 跑医疗数据的初版评测。
- `model_hf/`：下载 `roberta-large`、`Llama-3.2-1B/3B-Instruct`、`Qwen2.5-3B-Instruct` 等 HF 模型。
- `verl_old/`：基于 verl 框架，准备 priv/med/gsm8k 的预处理与 GRPO/PPO 训练；当晚跑了若干轮 `outputs/2026-05-16/...`。
- `ray_tmp/`：verl 训练时 Ray 产生的临时 session 目录（自然伴随 verl_old 训练）。

### 阶段 3：med_new 版数据流水线（2026-05-17）
- `med_new/`：`anonymize → clean_pii → key_spans_check(_llama) → key_spans_hit_rate → 答案打标 → fill_ground_truth → 最终处理`，产出 `med.final.{train,test,parquet}`。
- `mix_data_old/`、`prediax_old/`、`papillon_old/`、`papillon_privacy/`、`papillon_pupa/`、`pupa/`、`z_eval/` 同期：
  - `pupa` / `papillon_pupa` / `papillon_privacy`：基于 PUPA / Papillon 的对照基线（推理→merge→eval→privacy 评估）。
  - `prediax_old`、`mix_data_old`：早期的 prediax 与 mix 数据评测（`*_eval_result.parquet` 流水线）。
  - `z_eval/eval_privacy/com_privacy_score.py`：privacy 综合打分。

### 阶段 4：扩展数据 + 写作（2026-05-18）
- `writing/`：开始论文撰写（`paper.md`、`intro.md`、`data_construction.md`）；其下复制了 `layer1_reverse_synthesis/`、`Med_data_expand/` 的快照。
- `papillon_old/`：补 `abstract_examples.jsonl`、`step1_creator_single.py`，做 abstract 检索补充。
- `other/`：抽样产出 `train_subset_3000.parquet`。
- `need2know/`：建立 need2know 主题目录（当时为空，仅占位）。
- `layer2_nature_dialogue/`：开始 Layer 2 自然对话流水线，加载 wildchat 6 份 parquet，跑 `process/stages_full_old/`（00→06）。

### 阶段 5：Layer2 完整流水线 + 收尾（2026-05-19）
- `layer2_nature_dialogue/process/stages_full/`：`00_loaded → 01_struct → 02_suitable(_B/.A) → 03_ea_na_{A,B}` 全量跑通。
- `Med_data_expand/`：扩展 med 数据，补 `8_eval_ea_ne.py`、`med.final.test.600.parquet`、`tem.parquet`。
- `wild/`：`0_eval → 1_eval_ea_ne → 2_concat_sort → 3_top400_select`，从 wildchat 中筛 top400 隐私样本。

### 阶段 6：实验整合（2026-05-20 ~ 21）
- `Experiments/`：组织 `Data.md`、`Method.md`、`skills.md`、`intro.md`、`Main_results/{main,exp,tables}.tex` 等论文实验材料。
- `info/`：维护 `data.md` 数据信息。
- `layer2_nature_dialogue/Data.tex`：Layer2 数据章节定稿。

### 阶段 7：写论文（2026-05-22）
- `Paper/`：把 `Data/`、`LLMasJudge/`、`Experiments/`、`figures/`、`benchmark_survey/`、`skills/` 全部拷过来，开始写 `main.tex`、`Introduction.md`、`Introduction中文设计.md`、`todo.md`。

### 阶段 8：实验主表 + LLM-as-Judge（2026-05-24 ~ 25）
- `Experiments/Main_results/main.tex`：主结果表定稿。
- `papillon/`：完整跑通新的 papillon 流程（`step1_qwen523 → step2_remote → step3_aggregator → step4_eval → step5_anoy`），产出 `5_qwen.parquet`、`step4_eval_result.parquet`。
- `llm_test_data/` 与 `Exp_llm_as_judge/`：跑 LLM-as-Judge（`0_judge_gpt4o_mini.py`），生成 `*_judged.parquet`、`results/analysis/0[1-9]_*` 一系列分析（含 `08_quadrant_distribution`、`09_privacy_leak_table`、`PUFT/...`）。
- `layer1_reverse_synthesis/synth/prompt.tex`：layer1 反向合成的 prompt 文档。

### 阶段 9：protect / update_data 收尾（2026-05-26）
- `protect/`：把 `verl_old` 重新打包（`verl_old.zip`、`Need2Know.zip`），并补 `0_gt_ref.priv_*.parquet`、`run.py`、`pipeline.md`、`prompt.py`，构建 protect 评测管线。
- `update_data/`：基于已有结果生成 `data.jsonl`、`train.parquet`，`process.py` 处理流程。

### 阶段 10：近期回访（2026-06-29，约 1 个多月后）
- `tem/`：临时目录（空，仅 mtime 更新）。
- `prediax/4_priv_eval.py`：再次修改了 prediax 的隐私评估脚本。
- `inference/mix_data/4_sum_111.csv`、`mix_data/4_eval_ability_111.parquet`、`0_privacy/0_eval_by_ability.py`：在已有 mix_data 基础上，跑了一轮新的 ability 维度评测，产出 `*_111` 结果。

---

## 三、备注

1. 时间为文件系统 mtime；同一目录内若有多文件并列于最新分钟，已合并展示。
2. `merge_inference/` 内部仅剩 `skill.md` 等 `.md` 文件，但都不是 `README.md`，故按规则保留。
3. `__MACOSX/`、`.vscode/` 属于辅助文件，可在清理时考虑忽略。
4. `tem/`、`need2know/` 当前为空目录，时间仅反映目录自身被 touch 的时间，可能不代表真实工作。
