1. 数据来源：/group/40047/eiraxyhuang/workspace/fc/DataG/merge_inference/test_with_priv_query_add_gptinfo.parquet
2. 关于如何利用数据
prompt= """
You are a highly skilled assistant capable of generating engaging and innovative responses. Analyze the user's request thoroughly and provide a detailed response that not only answers their query but also showcases creativity and understanding of the context. Your output should include well-structured content, relevant examples, and an engaging tone appropriate for the task at hand. Always aim to surprise the user with insightful perspectives that go beyond basic information, ensuring clarity and emotional resonance in your communication.

Your input fields are:
1. `userQuery` (str): The user's request to be fulfilled.
2. `commonQuery`: A query that is similar to `userQuery`, but simpler and more general.
3. `modelExampleResponses` (str): You have the following information from a better language model responding to `commonQuery`. Complete the user query by referencing this information. Only you have access to this information.

## Input
- userQuery: {question}
- commonQuery: {priv_query}
- modelExampleResponses: {priv_gpt_answer}

Return only your response. Do not include any other text.
"""


3. 请撰写推理脚本，根据数据文件，进行推理。
可以参考单条推理脚本：/group/40047/eiraxyhuang/workspace/fc/DataG/test2.py
输出如下：
Output:
{'choices': [{'delta': {'role': 'assistant'}, 'finish_reason': None, 'index': 0}], 'created': 1778520525, 'gpu_name': 'H20', 'id': 'test_query_id_36aec8dd-502d-43ee-a56a-cb5694a77ecf', 'model': 'llama_inference', 'object': 'chat.completion.chunk', 'usage': {'completion_tokens': 0, 'prompt_tokens': 0, 'total_tokens': 0}}
我是基于 Llama 2 模型的。Llama 2 是由 Meta 开发的一种大型语言模型，它通过学习大量的文本数据来学习语言知识和理解能力。{'choices': [{'delta': {}, 'domain_tag': '', 'finish_msg': '', 'finish_reason': 'stop', 'index': 0, 'intervene_rule_id': 0}], 'created': 1778520525, 'gpu_name': 'H20', 'id': 'test_query_id_36aec8dd-502d-43ee-a56a-cb5694a77ecf', 'model': 'llama_inference', 'object': 'chat.completion.chunk', 'usage': {'completion_tokens': 44, 'prompt_tokens': 49, 'total_tokens': 93}}

4. 撰写完毕后，在这个文件后补充写如何使用
5. 如何使用

推理脚本：[merge_inference.py](./merge_inference.py)

### 5.1 依赖
```bash
pip install pandas pyarrow requests tqdm
```
> 脚本不依赖 `sseclient-py`：SSE 帧由 `requests.iter_lines()` 手动解析，避免该库在本服务上偶发丢中间帧的问题。

### 5.2 默认运行（处理整份 parquet）
```bash
cd /group/40047/eiraxyhuang/workspace/fc/DataG/merge_inference
python merge_inference.py
```
执行流程：
- 读取输入：`test_with_priv_query_add_gptinfo.parquet`（共 150 行）
- 按 prompt 模板拼接 → 调用部署的 `llama_inference` 模型（SSE 流式）
- 把模型回复写入新列 `merge_inference_answer`
- 输出文件：`test_with_merge_inference.parquet`

### 5.3 自定义参数
```bash
python merge_inference.py \
    --input  /path/to/in.parquet \
    --output /path/to/out.parquet \
    --workers 8 \
    --limit 5            # 仅试跑前 5 条非空数据
```

### 5.4 断点续跑
中途失败 / 部分行返回 `[ERROR] ...` 时，加 `--resume` 重跑，仅对未完成或出错的行重新推理：
```bash
python merge_inference.py --resume
```

### 5.5 主要可调参数（脚本顶部常量）
- `MAX_WORKERS`：并发线程数（默认 8）
- `MAX_RETRIES` / `RETRY_BACKOFF`：失败重试次数与退避秒数
- `REQUEST_TIMEOUT`：单次请求超时（默认 300s）
- `GEN_PARAMS`：`temperature / top_p / top_k / output_seq_len / max_input_seq_len`
- `DEBUG_STREAM=True`：临时打开后会逐行打印原始 SSE 帧，方便排查解析问题

### 5.6 输出说明
- 成功：对应行的 `merge_inference_answer` 为模型完整回答字符串
- 失败：内容以 `[ERROR] ...` 开头，便于过滤与重跑
- 空 query：直接写入空字符串
