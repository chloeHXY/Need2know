# 评估
撰写一个脚本对于输入文件进行评测
输入：/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/2_.parquet

输入文件的数据根据ability字段不同，评测指标和方式也不同
如果ability=privacy:
评测逻辑参考：/group/40047/eiraxyhuang/workspace/fc/DataG/z_eval/eval.py

如果ability=Med，说明是明确的单选题目。
调用gpt4o,使用prompt判断答案一致性.
最后统计一个准确率即可。
prompt="""
You are a strict answer-consistency evaluator. Your task is to determine whether the final answer expressed in the natural-language answer matches the answer_label.

Evaluation rules:
1. Focus only on the final option or answer explicitly stated in answer.
2. Output 1 if the option selected in answer exactly matches answer_label.
3. Output 0 if answer selects a different option, does not clearly select an option, gives multiple conflicting options, or the final answer cannot be determined.
4. Do not judge whether the explanation is medically, scientifically, or factually correct; only judge whether the final selected answer matches answer_label.
5. Output only a single character: 1 or 0. Do not output any explanation, punctuation, spaces, or extra text.

Input:
answer: {merge_inference_answer}
answer_label: {answer_label}

Output:
"""

