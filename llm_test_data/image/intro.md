## 背景
我们使用LLM-as-Judge作为兜底仲裁，叠加在现有 cov + BERTScore 双判据之上（）
现有评估评估方法：/group/40047/eiraxyhuang/workspace/fc/DataG/inference/0_privacy/0_eval_by_ability.py
考虑到现有方法可能存在：
- 推理性泄露
- 组合泄露

我们希望通过LLM-as-Judge去弥补。

## baseline
- papillon：是使用一个本地模型llama3.1-8b-instruct模型撰写提示词对用户question进行改写得到priv_query
- prediax: 是一个pii屏蔽方法，直接对question中的pii进行识别然后覆盖，得到priv_query
- our: 如果你想知道我们方法的细节，可以看：/group/40047/eiraxyhuang/workspace/temp/Method.md
- 如果你想知道我们评估数据的细节可以看：/group/40047/eiraxyhuang/workspace/temp/Data.md
  
## models
我们使用gpt-4o-mini
prompt:/group/40047/eiraxyhuang/workspace/fc/DataG/judge_prompt.md

## 结果
我们的方法：/group/40047/eiraxyhuang/workspace/fc/DataG/llm_test_data/our_judged.parquet
对比方法：
- papillon: pipillon_judged.parquet
- prediax: prediax_judged.parquet
  
## 统计结果目录
/group/40047/eiraxyhuang/workspace/fc/DataG/llm_test_data/analysis_report

