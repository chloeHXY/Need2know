# `wild` 目录说明

本目录用来从 **wild（WildChat 风格的开放领域）** 子集里筛出"隐私改写效果较好（`ne` 泄漏少）"的样本，最终产出一份 `top-K` 精选数据，供后续主流水线（[`inference/mix_data`](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/)）评测使用。

整个目录是一条单向的小流水线：

```
wild_with_priv_query.parquet  ┐
                              ├─► 1_eval_ea_ne.py ─► 1_eval_*_result.parquet
wild_200_with_priv_query.parquet  ┘                            │
                                                               ▼
                                                       2_concat_sort.py
                                                               │
                                                               ▼
                                          1_eval_ea_ne_concat_sorted.parquet
                                                               │
                                                               ▼
                                                       3_top400_select.py
                                                               │
                                                               ▼
                                            top400_wild_priv_query.parquet  ★最终产物
```

> ⚠️ **命名注意**
>
> 1. 文件名上的 `0_/1_/2_/3_` 表示**运行顺序**，不代表层级或依赖深度。
> 2. `0_eval.py` 的 `DEFAULT_OUTPUT` 写的是 `0_eval_result.parquet`，但目录里**没有**这个文件 —— 当前主链路用的是 `1_eval_ea_ne.py`，`0_eval.py` 仅作为参考实现保留（多了 PII / haystack 过滤逻辑）。
> 3. `1_eval_ea_ne.py` 顶部 docstring 写"输入是 `wild_with_priv_query.parquet`"，但代码里 `DEFAULT_INPUT` 已经改成了 `top400_wild_priv_query.parquet`，**实际两个输入都跑过**（结果分别是 `1_eval_ea_ne_result.parquet` 与 `1_eval_200_ea_ne_result.parquet`）。docstring 没同步更新，请以代码为准。
> 4. `top420_wild_priv_query.parquet` 没有对应生成脚本，是 `3_top400_select.py` 早期版本（`TOP_K=420`）的历史快照，**不要再使用**，请用 `top400_wild_priv_query.parquet`。
> 5. `tem.parquet` 是 `1_eval_ea_ne.py` 的 `DEFAULT_OUTPUT` / `DEFAULT_NOLEAK_OUTPUT` 占位文件（两个默认值指向同一路径会互相覆盖），仅作临时缓存，可随时清理。

---

## 数据来源（输入 parquet）

这两个 parquet 不是本目录生成的，而是上游"模型对 wild 子集生成 `priv_query`"后丢进来的快照：

| 文件 | 行数 | 说明 |
|---|---|---|
| `wild_with_priv_query.parquet` | 192 | 第一批 wild 子集，`extra_info.index ∈ [0, 191]`，含 `priv_query` + 原始 `extra_info`（带 `ea`/`ne`/`question` 等）。也是 [`inference/`](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/) 下多个 `8_eval_ea_ne.py` 的引用输入。|
| `wild_200_with_priv_query.parquet` | 276 | 第二批 wild 子集（命名里的 `200` 是项目内部代号，不是行数；实际 276 行），`extra_info.index ∈ [0, 275]`。两批的 index 各自从 0 开始，所以下游必须用 `(source, index)` 作为唯一键。|

---

## 主链路脚本（按运行顺序）

| 序号 | 脚本 | 作用 |
|---|---|---|
| 0 | [`0_eval.py`](/group/40047/eiraxyhuang/workspace/fc/DataG/wild/0_eval.py) | **参考脚本，当前主链路并不使用**。综合 `extra_info["ne"]` + `question_pii_entities`（Presidio/GPT-4o 打标的 PII）+ `extra_info["ea"]` 做泄漏 / 保留率评测；阈值与 [`z_eval/eval_privacy/com_privacy_score.py`](/group/40047/eiraxyhuang/workspace/fc/DataG/z_eval/eval_privacy/com_privacy_score.py) 的训练时奖励对齐：泄漏 `cov ≥ 1.0 OR bertP > 0.3`，`ea` 保留 `cov ≥ 0.5 OR bertP > 0.3`。会用 `extra_info['key_spans'] + extra_info['ea']` 拼成 haystack 过滤"本就该保留"的内容，并跳过形如 `A.xxx B.xxx ...` 的多选噪声。需要 `question_pii_entities` 列，wild 这两份输入并没有，所以本目录没有该脚本的产物。|
| 1 | [`1_eval_ea_ne.py`](/group/40047/eiraxyhuang/workspace/fc/DataG/wild/1_eval_ea_ne.py) | **当前主用的评测脚本**。只看 `extra_info["ne"]`（绝不能泄漏）和 `extra_info["ea"]`（应该保留），完全不使用 `question_pii_entities`，也不做 haystack 过滤。同样的双阈值（`ne` 泄漏 `cov ≥ 1.0 OR bertP > 0.3`、`ea` 保留 `cov ≥ 0.5 OR bertP > 0.3`），逐行输出 `n_ne / n_ne_leak / n_ea / n_ea_hit / sample_leak` 等列，并把 `n_ne_leak == 0` 的子集另存到 `--noleak_output`。命令行参数：`--input/--output/--noleak_output/--no_bert/--limit`。|
| 2 | [`2_concat_sort.py`](/group/40047/eiraxyhuang/workspace/fc/DataG/wild/2_concat_sort.py) | 把 `1_eval_200_ea_ne_result.parquet` + `1_eval_ea_ne_result.parquet` 两批评测结果纵向拼起来，按 `n_ne_leak` 升序稳定排序，输出 `1_eval_ea_ne_concat_sorted.parquet`。这一步只是给人肉看排序用的归档版本，**最终选 top 400 不依赖它**（`3_top400_select.py` 自己重新读两份 eval 文件做排序）。|
| 3 | [`3_top400_select.py`](/group/40047/eiraxyhuang/workspace/fc/DataG/wild/3_top400_select.py) | **最终选样脚本**。同时读两份 eval 结果（提供 `n_ne_leak` 用于排名）和两份原始 parquet（提供下游需要的完整 schema），用 `(source, index)` 做唯一键 join。把 union 后的 eval 行按 `n_ne_leak` 升序稳定排序、取前 `TOP_K = 400`，回到原始 parquet 取出对应行，写出 `top400_wild_priv_query.parquet`，并附上 `source`（`wild` / `wild_200`）和 `n_ne_leak` 两列。|

---

## 评测中间产物（per-row parquet）

| 文件 | 来源 | 说明 |
|---|---|---|
| `1_eval_ea_ne_result.parquet` | `1_eval_ea_ne.py --input wild_with_priv_query.parquet` | 第一批（192 行）的逐行评测结果。|
| `1_eval_ea_ne_noleak.parquet` | 同上的 `--noleak_output` | 第一批中 `n_ne_leak == 0` 的子集。|
| `1_eval_200_ea_ne_result.parquet` | `1_eval_ea_ne.py --input wild_200_with_priv_query.parquet` | 第二批（276 行）的逐行评测结果。|
| `1_eval_200_ea_ne_noleak.parquet` | 同上的 `--noleak_output` | 第二批中 `n_ne_leak == 0` 的子集。|
| `1_eval_ea_ne_concat_sorted.parquet` | `2_concat_sort.py` | 上面两份 result 的纵向拼接 + `n_ne_leak` 升序版（仅人肉查看用）。|
| `tem.parquet` | `1_eval_ea_ne.py` 的默认输出占位 | 由于脚本里 `DEFAULT_OUTPUT` 与 `DEFAULT_NOLEAK_OUTPUT` 指向同一路径，运行时会被 `noleak` 子集覆盖；当临时缓存看待，可删。|

每行评测结果里关键的列：

- `index`：来自 `extra_info["index"]`，配合 `source` 唯一定位原始样本。
- `question` / `priv_query`：原问题与改写后的问题。
- `ne_items / ne_leak_flags / ne_coverage / ne_bert_p / n_ne / n_ne_leak`：`ne` 项目逐项的判定明细 + 计数。
- `ea_items / ea_hit_flags / ea_coverage / ea_bert_p / n_ea / n_ea_hit`：`ea` 项目逐项的保留判定 + 计数。
- `sample_leak`：`n_ne_leak > 0` 即为 True，是样本级泄漏的 boolean。

---

## 最终产物

| 文件 | 内容 |
|---|---|
| `top400_wild_priv_query.parquet` | **当前唯一应被下游消费的 wild 精选数据**：用 `n_ne_leak` 升序在两批 wild parquet 的并集里挑前 400 行，保留原始 schema（`extra_info` / `priv_query` / `ability` / ...），并附加 `source`（`wild` 或 `wild_200`）和 `n_ne_leak` 两列。|
| `top420_wild_priv_query.parquet` | 历史快照，对应 `3_top400_select.py` 早期 `TOP_K = 420` 时期的产出。**已废弃**，请使用 `top400_wild_priv_query.parquet`。|

---

## 典型运行顺序速记

```bash
# 1) 评测两批 wild 数据（产出 1_eval_*_result + 1_eval_*_noleak）
python /group/40047/eiraxyhuang/workspace/fc/DataG/wild/1_eval_ea_ne.py \
    --input  /group/40047/eiraxyhuang/workspace/fc/DataG/wild/wild_with_priv_query.parquet \
    --output /group/40047/eiraxyhuang/workspace/fc/DataG/wild/1_eval_ea_ne_result.parquet \
    --noleak_output /group/40047/eiraxyhuang/workspace/fc/DataG/wild/1_eval_ea_ne_noleak.parquet

python /group/40047/eiraxyhuang/workspace/fc/DataG/wild/1_eval_ea_ne.py \
    --input  /group/40047/eiraxyhuang/workspace/fc/DataG/wild/wild_200_with_priv_query.parquet \
    --output /group/40047/eiraxyhuang/workspace/fc/DataG/wild/1_eval_200_ea_ne_result.parquet \
    --noleak_output /group/40047/eiraxyhuang/workspace/fc/DataG/wild/1_eval_200_ea_ne_noleak.parquet

# 2) （可选，归档）拼接 + 按 n_ne_leak 升序
python /group/40047/eiraxyhuang/workspace/fc/DataG/wild/2_concat_sort.py

# 3) 在 union 上选 top-400 并取原始行
python /group/40047/eiraxyhuang/workspace/fc/DataG/wild/3_top400_select.py
# 产出 -> top400_wild_priv_query.parquet
```

下游再把 `top400_wild_priv_query.parquet` 接进 [`inference/mix_data`](/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/) 主流水线（`0_add_gpt_answer.py → 1_inference.py → 2_merge_inference.py → 3_eval.py → 4_anoy.py → 0_privacy/0_eval_by_ability*.py`）做最终的混合能力评测。

---

## 文件最后修改时间

下面这张表来自 `find -printf '%T+ %p'`（截至 2026-06-29 README 编写时刻），按 mtime 升序排列。所有数据 / 脚本都集中在 **2026-05-19** 这一天迭代完成，时间顺序大致就是真实的运行顺序，可以和上面的"主链路"互相印证。

| 最后修改时间 | 文件 | 角色 |
|---|---|---|
| 2026-05-19 13:12:46 | `wild_with_priv_query.parquet` | 输入 A（192 行）|
| 2026-05-19 13:13:27 | `0_eval.py` | 参考评测脚本（未实际进入主链路）|
| 2026-05-19 13:24:41 | `1_eval_ea_ne_result.parquet` | A 的 eval 结果 |
| 2026-05-19 13:24:41 | `1_eval_ea_ne_noleak.parquet` | A 中 `n_ne_leak == 0` 的子集 |
| 2026-05-19 15:53:21 | `wild_200_with_priv_query.parquet` | 输入 B（276 行）|
| 2026-05-19 15:54:37 | `1_eval_200_ea_ne_result.parquet` | B 的 eval 结果 |
| 2026-05-19 15:54:37 | `1_eval_200_ea_ne_noleak.parquet` | B 中 `n_ne_leak == 0` 的子集 |
| 2026-05-19 16:05:31 | `2_concat_sort.py` | 拼接 + 排序脚本 |
| 2026-05-19 16:05:38 | `1_eval_ea_ne_concat_sorted.parquet` | 上一步产物（归档版）|
| 2026-05-19 16:10:52 | `top420_wild_priv_query.parquet` | 早期 `TOP_K=420` 历史快照（已废弃）|
| 2026-05-19 16:14:10 | `3_top400_select.py` | 最终选样脚本 |
| 2026-05-19 16:14:17 | `top400_wild_priv_query.parquet` | ★最终产物 |
| 2026-05-19 16:15:11 | `1_eval_ea_ne.py` | 当前主用评测脚本（这里有过最后一次微调）|
| 2026-05-19 16:15:40 | `tem.parquet` | `1_eval_ea_ne.py` 默认输出占位（临时缓存）|
| 2026-06-29 12:12:21 | `README.md` | 本文档 |

> 说明
> - 表中只列了本目录第一层文件，子目录暂无。
> - `top420_wild_priv_query.parquet`（16:10:52）早于 `3_top400_select.py`（16:14:10），印证了它是脚本里 `TOP_K` 还是 420 时的产出，之后脚本被改成 `TOP_K = 400` 才得到现在的 `top400_wild_priv_query.parquet`。
> - `1_eval_ea_ne.py` 的 mtime（16:15:11）晚于它生成的所有 `1_eval_*` 结果文件，说明那次最后修改只是事后调整 `DEFAULT_INPUT/DEFAULT_OUTPUT` 等路径常量，并没有重新跑评测；这也是为什么 docstring 与 `DEFAULT_INPUT` 当前不一致。
