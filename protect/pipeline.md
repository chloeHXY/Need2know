这是最核心的部分。论文的框架处理用户 prompt 分三步：

1. context identification：判断对话 domain 和 task
2. sensitive information classification：把敏感信息分成 essential 和 non-essential
3. reformulation：删除或改写 non-essential sensitive information，同时保留用户意图


模型调用参看“test.py
demo.py是一个简单的流程脚本
prompt.py中包含所用的prompt

请撰写正式的run.py

包含两种一个是输入一句话作为测试

一种是输入一个parquet文件：/group/40047/eiraxyhuang/workspace/fc/DataG/protect/0_gt_ref.parquet
输入是extra_info中的question字段


改写后的输出，放到/覆盖字段：priv_query中