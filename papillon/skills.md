
PAPILLON pipeline 实现

数据集均使用我们的测试数据：/group/40047/eiraxyhuang/workspace/fc/DataG/inference/test.parquet

Step 1：Prompt Creator
创建推理脚本，使用 Creator prompt， 输入原始用户请求 q，由本地模型生成一个隐私保护 prompt q'。本地模型使用llama-3.1-8b-instruct,
单条推理脚本：/group/40047/eiraxyhuang/workspace/fc/DataG/test2.py
也可以参考：/group/40047/eiraxyhuang/workspace/fc/DataG/merge_inference/merge_inference.py

Step 2：Remote Model Response
创建一个推理脚本：把 q' 发给远程模型，得到中间回答 CR。
远程模型：gpt-4o
参考脚本 /group/40047/eiraxyhuang/workspace/fc/DataG/inference/inference.py

Step 3：Information Aggregator

本地模型拿到：

* 原始用户请求 q
* 远程模型回答 CR

创建一个融合推理脚本，使用 aggregator prompt，推理出最终的答案，本地模型仍然使用llama-3.1-8b-instruct。
可以参考：/group/40047/eiraxyhuang/workspace/fc/DataG/merge_inference/merge_inference.py

Step 4: z_eval

撰写脚本，使用step3的结果进行z_eval中的评估。
可以参考：/group/40047/eiraxyhuang/workspace/fc/DataG/z_eval/eval.py
