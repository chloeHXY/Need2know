# `data/` 目录文件最近修改时间表 (timeline)

> 统计时间：2026-06-30
> 数据来源：文件系统 mtime（北京时间，`find -printf "%T+"` 截断到秒）
> 范围：`/group/40047/eiraxyhuang/workspace/fc/DataG/layer1_reverse_synthesis/data/` 下所有常规文件
> 用途：用于快速判断各文件的最近一次保存 / 改动时间。

---

## 1. 全量列表（按 mtime 倒序）

| # | mtime (Asia/Shanghai) | 大小 (B) | 相对路径 |
| ---: | --- | ---: | --- |
|  1 | 2026-06-30 01:28:31 |       183 | `o1/Intro.md` |
|  2 | 2026-06-30 01:27:34 |    12,584 | `o1/label.py` |
|  3 | 2026-05-19 17:44:57 | 2,440,400 | `smoke_518.jsonl` |
|  4 | 2026-05-15 11:19:39 |       943 | `o1/command.txt` |
|  5 | 2026-05-15 10:38:52 | 3,814,280 | `o1/syn_questions/med.jsonl` |
|  6 | 2026-05-15 10:36:38 |     2,344 | `o1/__pycache__/prompt2.cpython-310.pyc` |
|  7 | 2026-05-15 10:36:38 |     9,453 | `o1/__pycache__/synthesize_question.cpython-310.pyc` |
|  8 | 2026-05-15 10:34:31 |    12,785 | `o1/synthesize_question.py` |
|  9 | 2026-05-15 10:32:35 |     2,164 | `o1/prompt2.py` |
| 10 | 2026-05-15 10:14:27 |       365 | `o1/labels/labels_gpt-4o_start0_n500_20260515_101049.usage.json` |
| 11 | 2026-05-15 10:14:27 | 3,044,581 | `o1/labels/labels_gpt-4o_start0_n500_20260515_101049.jsonl` |
| 12 | 2026-05-15 10:09:39 |     2,964 | `o1/__pycache__/prompt.cpython-310.pyc` |
| 13 | 2026-05-15 10:09:38 |     8,580 | `o1/__pycache__/label.cpython-310.pyc` |
| 14 | 2026-05-15 10:04:10 |       383 | `o1/skill.md` |
| 15 | 2026-05-15 10:01:17 |     2,784 | `o1/prompt.py` |
| 16 | 2026-05-14 21:24:29 | 11,839,243 | `o1/medical_o1_sft_mcq.json` |
| 17 | 2026-05-14 03:43:16 | 2,787,657 | `smoke_58.clean_with_tags.jsonl` |
| 18 | 2026-05-14 03:34:17 | 1,502,293 | `smoke_58.clean_tag.jsonl` |
| 19 | 2026-05-14 03:26:44 | 2,491,505 | `smoke_58.clean.jsonl` |
| 20 | 2026-05-13 23:57:23 |    17,291 | `small.pii.jsonl` |
| 21 | 2026-05-13 23:47:30 |    13,281 | `small.pii_old.jsonl` |
| 22 | 2026-05-13 23:39:09 |    25,349 | `small.jsonl` |
| 23 | 2026-05-13 21:58:29 |    49,999 | `smoke_medqa.jsonl` |
| 24 | 2026-05-13 21:56:07 |    33,006 | `medqa/_value_bank_cache.json` |
| 25 | 2026-05-13 21:24:50 |    39,464 | `smoke_v2.jsonl` |
| 26 | 2026-05-13 18:37:23 | 2,075,679 | `medqa/phrases_no_exclude_test.jsonl` |
| 27 | 2026-05-13 18:37:22 | 16,211,077 | `medqa/phrases_no_exclude_train.jsonl` |
| 28 | 2026-05-09 00:02:27 | 2,232,657 | `smoke_58_merged.clean.jsonl` |
| 29 | 2026-05-09 00:01:48 | 4,455,419 | `smoke_58_merged.jsonl` |
| 30 | 2026-05-08 23:53:16 | 1,490,245 | `smoke_58_3.jsonl` |
| 31 | 2026-05-08 21:46:50 | 2,185,456 | `med/medqa_test_convo.jsonl` |
| 32 | 2026-05-08 21:46:50 | 3,382,911 | `med/medqa_dev_convo.jsonl` |
| 33 | 2026-05-08 21:07:19 | 1,969,181 | `smoke_58_2.jsonl` |
| 34 | 2026-05-08 20:58:05 |   995,993 | `smoke_58.jsonl` |
| 35 | 2026-04-30 17:54:14 |   258,848 | `smoke.clean.jsonl` |
| 36 | 2026-04-30 17:49:11 |   493,608 | `smoke.jsonl` |
| 37 | 2026-04-30 11:46:03 |       447 | `README.md` |

> 空目录：`contextual_priv/`（mtime: 2026-05-14 21:20:00，目录本身存在但暂无文件）

---

## 2. 按子目录分组

### 2.1 顶层 `data/`

| mtime | 大小 (B) | 文件 |
| --- | ---: | --- |
| 2026-05-19 17:44:57 | 2,440,400 | `smoke_518.jsonl` |
| 2026-05-14 03:43:16 | 2,787,657 | `smoke_58.clean_with_tags.jsonl` |
| 2026-05-14 03:34:17 | 1,502,293 | `smoke_58.clean_tag.jsonl` |
| 2026-05-14 03:26:44 | 2,491,505 | `smoke_58.clean.jsonl` |
| 2026-05-13 23:57:23 |    17,291 | `small.pii.jsonl` |
| 2026-05-13 23:47:30 |    13,281 | `small.pii_old.jsonl` |
| 2026-05-13 23:39:09 |    25,349 | `small.jsonl` |
| 2026-05-13 21:58:29 |    49,999 | `smoke_medqa.jsonl` |
| 2026-05-13 21:24:50 |    39,464 | `smoke_v2.jsonl` |
| 2026-05-09 00:02:27 | 2,232,657 | `smoke_58_merged.clean.jsonl` |
| 2026-05-09 00:01:48 | 4,455,419 | `smoke_58_merged.jsonl` |
| 2026-05-08 23:53:16 | 1,490,245 | `smoke_58_3.jsonl` |
| 2026-05-08 21:07:19 | 1,969,181 | `smoke_58_2.jsonl` |
| 2026-05-08 20:58:05 |   995,993 | `smoke_58.jsonl` |
| 2026-04-30 17:54:14 |   258,848 | `smoke.clean.jsonl` |
| 2026-04-30 17:49:11 |   493,608 | `smoke.jsonl` |
| 2026-04-30 11:46:03 |       447 | `README.md` |

### 2.2 `data/o1/`

| mtime | 大小 (B) | 文件 |
| --- | ---: | --- |
| 2026-06-30 01:28:31 |       183 | `Intro.md` |
| 2026-06-30 01:27:34 |    12,584 | `label.py` |
| 2026-05-15 11:19:39 |       943 | `command.txt` |
| 2026-05-15 10:38:52 | 3,814,280 | `syn_questions/med.jsonl` |
| 2026-05-15 10:36:38 |     2,344 | `__pycache__/prompt2.cpython-310.pyc` |
| 2026-05-15 10:36:38 |     9,453 | `__pycache__/synthesize_question.cpython-310.pyc` |
| 2026-05-15 10:34:31 |    12,785 | `synthesize_question.py` |
| 2026-05-15 10:32:35 |     2,164 | `prompt2.py` |
| 2026-05-15 10:14:27 |       365 | `labels/labels_gpt-4o_start0_n500_20260515_101049.usage.json` |
| 2026-05-15 10:14:27 | 3,044,581 | `labels/labels_gpt-4o_start0_n500_20260515_101049.jsonl` |
| 2026-05-15 10:09:39 |     2,964 | `__pycache__/prompt.cpython-310.pyc` |
| 2026-05-15 10:09:38 |     8,580 | `__pycache__/label.cpython-310.pyc` |
| 2026-05-15 10:04:10 |       383 | `skill.md` |
| 2026-05-15 10:01:17 |     2,784 | `prompt.py` |
| 2026-05-14 21:24:29 | 11,839,243 | `medical_o1_sft_mcq.json` |

### 2.3 `data/medqa/`

| mtime | 大小 (B) | 文件 |
| --- | ---: | --- |
| 2026-05-13 21:56:07 |    33,006 | `_value_bank_cache.json` |
| 2026-05-13 18:37:23 | 2,075,679 | `phrases_no_exclude_test.jsonl` |
| 2026-05-13 18:37:22 | 16,211,077 | `phrases_no_exclude_train.jsonl` |

### 2.4 `data/med/`

| mtime | 大小 (B) | 文件 |
| --- | ---: | --- |
| 2026-05-08 21:46:50 | 2,185,456 | `medqa_test_convo.jsonl` |
| 2026-05-08 21:46:50 | 3,382,911 | `medqa_dev_convo.jsonl` |

### 2.5 `data/contextual_priv/`

空目录（目录 mtime: 2026-05-14 21:20:00）。

---

## 3. 重新生成方式

```bash
find /group/40047/eiraxyhuang/workspace/fc/DataG/layer1_reverse_synthesis/data \
     -type f -printf "%T+ %s %p\n"
```

或者只看相对路径与可读时间：

```bash
cd /group/40047/eiraxyhuang/workspace/fc/DataG/layer1_reverse_synthesis/data
find . -type f -printf "%TY-%Tm-%Td %TH:%TM:%TS  %s  %p\n"
```
