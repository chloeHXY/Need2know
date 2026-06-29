# 目标：比较两个回答的质量
## 输入：两个文件
文件A：/group/40047/eiraxyhuang/workspace/fc/DataG/merge_inference/test_with_merge_inference.parquet
文件B：/group/40047/eiraxyhuang/workspace/fc/DataG/inference/test_with_gpt_answer.parquet
response_A :文件A的merge_inference_answer字段
response_B : 文件B的gpt_answer字段
注意两个文件之间的对齐
## 输出
- 打印测试集的平均得分
- 将所有的response_A,response_B,score存储到一个结果集中
## 中间输出
随机打印2条，（response_A,response_B,score）

## 比较逻辑
使用prompt调用大模型gpt4o比较，推理代码参考/group/40047/eiraxyhuang/workspace/fc/DataG/inference/inference.py

### prompt
f_QJ="""
You are an impartial evaluator comparing two responses to the same user query.

Determine whether Response A is at least as good as Response B.

Answer "yes" if Response A is equal to or better than Response B overall.
Answer "no" if Response A is worse than Response B overall.

Evaluate based on correctness, completeness, relevance, helpfulness, safety, and clarity.

Do not favor a response simply because it is longer.

Return exactly one word: "yes" or "no". Do not include any explanation.

User Query:
{user_query}

Response A:
{response_A}

Response B:
{response_B}

Answer:
"""

## 比较逻辑
该算法用于判断一个管线输出 C_L 相对于目标输出 C_T 是否保持了质量。核心思想是：使用同一个大模型评审器，在正向和反向两个候选顺序下分别比较两个回答，以降低位置偏差，并检测评审结果是否一致。

具体流程如下：

1. 给定用户问题 q、管线输出 C_L、目标输出 C_T、大模型评审器 M_J，以及质量判断提示词 f_QJ。
2. 第一次调用评审器，令：
    * Response A = C_L
    * Response B = C_T
    评审器需要判断：C_L 是否至少和 C_T 一样好。
    若输出 yes，记为 s_1 = 1；若输出 no，记为 s_1 = 0。
3. 第二次调用评审器时，交换两个候选回答的顺序，令：
    * Response A = C_T
    * Response B = C_L
    此时评审器判断：C_T 是否至少和 C_L 一样好。
    若输出 yes，记为 s_2 = 1；若输出 no，记为 s_2 = 0。
4. 比较两次判断结果：
    * 如果 s_1 = s_2，说明评审器在正反两个顺序下给出了不一致的偏好信号。例如两个方向都认为 A 不差于 B，或者两个方向都认为 A 差于 B。这种情况无法明确判断哪个回答质量更高，因此返回 1，表示评审结果不可靠或存在并列/冲突情况。
    * 如果 s_1 ≠ s_2，说明评审器在交换顺序后仍能形成一致的相对偏好，此时返回 s_1 作为最终质量保持结果。

最终，Q_AL(C_L, C_T) 的含义可以理解为：

* 返回 1：认为管线输出 C_L 至少与目标输出 C_T 一样好，或评审结果不一致时采用保守通过策略。
* 返回 0：认为管线输出 C_L 明确弱于目标输出 C_T。


------------
实现要点
1. 数据加载与对齐
文件 A: merge_inference/test_with_merge_inference.parquet，取 merge_inference_answer 字段作为 response_A (即 C_L)

文件 B: inference/test_with_gpt_answer.parquet，取 gpt_answer 字段作为 response_B (即 C_T)

对齐策略（按优先级）：

优先使用 extra_info.question 作为 join key（这是 user_query）

退化到 priv_query 对齐

最后才用位置对齐

user_query 从 extra_info["question"] 提取（与 merge_inference.py 中的处理方式保持一致）

2. 评审逻辑（双向比较，消除位置偏差）
严格按 skill.md 的 Q_AL 算法：

第一次调用：A=C_L, B=C_T → s1（C_L 是否不差于 C_T）

第二次调用：A=C_T, B=C_L → s2（C_T 是否不差于 C_L）

打分规则：

s1 == s2 → 评审不一致/并列 → score = 1（保守通过）

s1 != s2 → score = s1

3. 大模型调用
完全复用 inference.py 中的 GPT-4o 代理配置（TOKEN/URL/MODEL/HEADERS）

使用 f_QJ prompt，temperature=0.0 保证评审稳定

输出仅解析 yes/no 关键词，避免大模型多余文字干扰

4. 性能与健壮性
16 路并发 + 重试退避 + 超时控制

空回答短路处理（避免空字符串浪费 LLM 调用）

失败默认计 0，避免静默拉高分数

5. 输出
终端打印 平均得分

终端随机打印 2 条 (user_query, response_A, response_B, score) 样例

完整结果保存到 z_eval/eval_result.parquet，包含字段：user_query, response_A, response_B, s1, s2, score

运行方式
cd /group/40047/eiraxyhuang/workspace/fc/DataG/z_eval
python eval.py                       # 全量评估
python eval.py --limit 50            # 先小批量验证
python eval.py --workers 8           # 调整并发 


## 5.12结果
=== Result ===
total pairs : 150
average     : 0.90 #0.8温度

=== pii Result ===
total pairs : 150
average     : 0.8867 #1温度

