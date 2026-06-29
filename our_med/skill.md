
our pipeline 实现
## 你真正要做的
step3脚本修改+撰写第4步的脚本

## 背景信息

Step 1
 输入原始用户请求 q，由本地训练好的模型生成一个隐私保护 prompt q'。字段：priv_query
 已经生成好：/group/40047/eiraxyhuang/workspace/fc/DataG/our_med/med_with_priv_query.parquet

Step 2：Remote Model Response
创建一个推理脚本：把 priv_query 发给远程模型，得到中间回答 CR。
远程模型：gpt-4o
脚本 /group/40047/eiraxyhuang/workspace/fc/DataG/our_med/inference.py

Step 3：Information Aggregator

本地模型拿到：

* 原始用户请求 q
* 远程模型回答 CR
脚本：/group/40047/eiraxyhuang/workspace/fc/DataG/our_med/merge_inference.py
请将上面的脚本的PROMPT_TEMPLATE改为适合单选题的模板，方便我们在第四部中评估。


Step 4: 评估，由于题目为单选题
根据第三部中的输出，评估正确率
gt: reward_model['ground_truth']中
