# PUFT 数据结果归因分析

> 数据源: `Exp_llm_as_judge/results/PUFT_judged.parquet`，n=500；评测器=GPT‑4o‑mini  
> 对照: `our` / `papillon` / `prediax`（每个 500 条相同问题集）

---

## 1. 现象（What）

| dataset | good % | accept % | bad % | reid_risk (mean) | utility (mean) |
|---|---|---|---|---|---|
| our | 44.4 | 23.2 | 32.4 | 0.149 | 0.782 |
| papillon | 39.0 | 28.8 | 32.2 | 0.043 | 0.717 |
| prediax | 12.2 | 38.8 | 49.0 | **0.578** | 0.787 |
| **PUFT** | 19.0 | 18.2 | **62.8** | 0.047 | **0.501** |

**PUFT 的失败模式与 prediax 完全相反**：
- prediax 失败因为 **隐私泄露**（reid_risk 高达 0.58）；
- PUFT 失败因为 **效用塌陷**（utility 0.50，是四者中唯一低于 0.7 的），隐私其实做得相当好（reid_risk 0.047，与 papillon 持平）。

象限分布印证了这一点：
- PUFT **58.4 %** 的样本落在「低效用 + 低风险」象限（远高于 our 20.2 / papillon 29.2 / prediax 4.6）；
- 高效用 + 低风险（理想区）只有 **19.6 %**（our 45 / papillon 40.8）。

也就是说 **PUFT 的策略是"宁可不可用，也不能泄露"**，把绝大多数 query 改写到了过度匿名化的死区。

---

## 2. 直接归因：过度压缩 / 过度抽象 (Why-1)

**rewrite 长度** 是最直观的证据：

| dataset | 原 query 词数 | rewrite 词数 | 长度比中位数 | 短于原文 50% 的样本数 | 短于 30% 的样本数 |
|---|---|---|---|---|---|
| our | 94.95 | 33.79 | 0.36 | 376 | 168 |
| papillon | 94.95 | 45.32 | 0.51 | 245 | 90 |
| prediax | 94.95 | 91.69 | 1.00 | 0 | 0 |
| **PUFT** | 94.95 | **25.04** | **0.25** | **425** | **293** |

PUFT 平均把 95 个词压缩到 25 个词（**~26 %**），其中 **58.6 %（293/500）** 的 rewrite 长度不到原文的 30 %。这是四个系统中最激进的压缩。

**评测器侧的对应失效模式**（占样本比例）：

| 失效模式 | our | papillon | prediax | **PUFT** |
|---|---|---|---|---|
| excessive abstraction causing intent loss | 43.2 | 57.0 | 29.8 | **76.8** |
| lost_constraint 出现 | 43.2 | 57.0 | 29.8 | **76.8** |
| 平均每条样本 lost_constraint 数 | 1.06 | 1.44 | 0.58 | **2.41** |
| 单样本最多 lost_constraint 数 | 13 | 10 | 7 | **16** |
| direct_leak | 16.0 | 4.6 | 72.8 | 5.2 |
| semantic_leak | 6.2 | 6.0 | 30.8 | 4.2 |

PUFT 把 **76.8 %** 的样本改写到丢失关键约束（lost_constraint）的地步，平均每条样本被砍掉 **2.4 个** 必要约束，是 our 的 2.3 倍、prediax 的 4.2 倍。**PUFT 的失败 = 过度激进的"宁删勿留"匿名化**。

---

## 3. 进一步归因：什么样的 query PUFT 砍得最狠 (Why-2)

按 rewrite 长度比分桶看 PUFT 的效用：

| word_ratio bucket | n | mean utility | bad % |
|---|---|---|---|
| <0.3 | 291 | **0.44** | **71.1 %** |
| 0.3–0.5 | 134 | 0.57 | 54.5 % |
| 0.5–0.8 | 64 | 0.66 | 39.1 % |
| 0.8–1.0 | 9 | 0.59 | 77.8 % |

`word_ratio` 与 utility 的 Pearson 相关 = **+0.31**，与 reid_risk 相关 = +0.19。也就是说在 PUFT 内部，"砍得越狠 → 越差"。**ratio<0.3** 这一组（占 PUFT 的 58 %）的 utility 仅 0.44，bad 率高达 71 %，是 PUFT 整体表现塌方的元凶。

**典型失败案例**（来自 `PUFT_collapse_cases.md`，全部 verdict=bad，util=0，risk=0）：

1. **医学考题**：原题给出"13 岁男孩、频繁吃零食、每日刷牙两次、口腔检查多发窝沟龋……A.CAMBRA / B.ADA / C.AAPD / D.Cariogram"，PUFT 直接改写为 **"D. Cariogram"** ——把题目变成了答案。
2. **生活诉求题**：原文是关于家人被邻居劝说做手术，求"为家人代祷的最长祷词"，PUFT 改成 **"What's a good way to initiate a conversation with someone about their health concerns regarding adenoid surgery?"** —— 任务漂移 + 抽空所有上下文。
3. **职业咨询题**：原题给出"Clemson 大学准大四、商管专业、辅修政治科学、夏季在 Charlotte 一家小型理财公司实习"，PUFT 把这些约束（学校、专业、实习地点、实习类型）全部抹掉，rewrite 只剩 "What are some potential career paths for a college student who has completed a summer internship?"——专业建议无从给出。
4. **纠纷投诉题**：原题描述"早晨送孩子上学回家倒车时撞到自家车道里的施工标志"，PUFT 改写时同时抹掉了"送孩子"、"具体时间"、"倒车"、"详细描述事件"等多个对申诉信至关重要的约束。
5. **情感咨询题**：原题"我 25 岁、从未有过恋情、自我评价低"，PUFT 改写成万能模板 "What's a good way to initiate a conversation with someone I'd like to connect with?"——丢失了核心痛点。

`lost_reason_clusters_PUFT.csv` 中前 10 个 reason 模式也印证：高频出现 "essential task attribute missing"、"answer options missing"、"specific muscle strength ratings missing"、"drug options necessary missing"——这些都是 PUFT **把回答任务所必需的领域细节当作 PII 一并删除** 的证据。

**对照 PUFT 的成功案例**（`PUFT_good_cases.md`，util=1.0）几乎都有共同结构：

- 都是 **"姓名 + 合成 ID + 一道独立题目"** 的模板（医学 MCQ、写邮件、PostgreSQL vs MySQL 等）；
- PUFT 只删除了人名/ID 等表层 PII，问题主体没受影响；
- 因为题目和身份是天然解耦的，所以 PUFT 的「先删再留」策略恰好能用。

---

## 4. 跨系统对比解释（PUFT vs 其它）

把四个系统按"压缩强度 vs 隐私强度"摆成谱系：

```
prediax  ── papillon ── our ── PUFT
  ↑                                ↑
保留太多 (reid 0.58)        删得太狠 (util 0.50)
direct_leak 主导             lost_constraint 主导
```

- **prediax**：基本不改写（长度比 1.00），只做表面替换 → 直接泄露 72.8 %；
- **our** / **papillon**：中等压缩（0.36–0.51），效用与隐私都较平衡；
- **PUFT**：激进压缩（0.25），把任务约束当 PII 一起抹除。

四个系统的隐私失败和效用失败几乎是**互斥**的：

- 当 rewrite 越接近原文（prediax）→ 隐私问题为主；
- 当 rewrite 越短（PUFT）→ 效用问题为主；
- 二者**没有同时变差**（PUFT 隐私其实优于 our）。

这也再次说明 PUFT 不是"模型能力差"，而是**策略校准失衡**——把"识别风险"的阈值压得太低，把"任务约束"的边界画得太宽。

---

## 5. 根因总结（Root cause）

1. **过度匿名化（over-conservative anonymization）是 PUFT 的核心问题**。所有失败模式都收敛到同一根因：rewrite 过短 + 过度抽象。
   - 76.8 % 的样本出现 lost_constraint；
   - 58.6 % 的样本被压到原文 30 % 以下；
   - "低效用 + 低风险"象限占比 58.4 %（其它系统最高 29.2 %）。
2. **任务-约束 与 PII 没有被区分对待**。考题的选项、医疗题的症状/检查发现、咨询题的当事人语境，都是回答正确所必需的"任务约束"，但 PUFT 在重写时把它们与"姓名/年龄/学校"等真正的 PII 一并删除。
3. **PUFT 对短而清晰的"模板化"问题（医学 MCQ、写邮件等）有效**，对**长上下文 / 多约束的开放问题严重失效**。其策略似乎是"提取核心问题句再丢弃一切上下文"，因此当上下文本身就是任务的一部分时就崩盘。
4. **PUFT 几乎不会引入新敏感信息**（new_sensitive 0 %），也几乎没有 task_drift 之外的复杂错误。也就是说 PUFT 的失败**不是"乱写"**，而是**"什么都不写"**。

---

## 6. 改进建议

1. **加入"任务约束保留"约束/奖励信号**：在 PUFT 的 rewrite 目标中显式区分 "PII 实体" 和 "任务约束实体"，前者删/泛化，后者必须保留。
2. **长度下限护栏**：对原文长度 > 60 词的输入，给 rewrite 一个最低长度比（例如 0.5）作为正则项，可单独缓解 ~58 % 样本的塌方。
3. **分类型策略**：
   - 含 MCQ 选项的题目：硬规则要求保留所有选项；
   - 长场景叙事题：先抽取"任务核心"（写信/分析/比较），再分别决定哪些场景细节是任务输入、哪些是身份线索；
4. **以本归因脚本（`results/attribute_PUFT.py`）作为回归测试**：每次模型迭代后比较 word_ratio 分布、lost_constraint per sample，作为内部排行榜补充。

---

## 7. 产出文件索引

- `len_stats.csv`：四系统的原文与 rewrite 长度统计；
- `length_corr.csv` / `length_buckets_PUFT.csv`：长度比 vs 效用/风险；
- `lost_constraint_counts.csv`、`lost_span_tokens_PUFT.csv`、`lost_reason_clusters_PUFT.csv`：lost_constraint 的细化挖掘；
- `PUFT_by_verdict.csv`：按 good/acceptable/bad 分组的统计；
- `PUFT_collapse_cases.md`：低效用低风险的代表性失败案例；
- `PUFT_good_cases.md`：PUFT 表现良好的案例画像；
- `PUFT_len_vs_util.png` / `lost_constraint_per_sample.png`：可视化。
