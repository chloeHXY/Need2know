# -*- coding: utf-8 -*-

import os
import time
import uuid
import json
import requests
import sseclient

ss_url = "http://21.119.245.18:81/openapi/chat/completions" # ip参考《环境准备》一节，每次请求时通过北极星sdk解析得到ip来调用
model = "llama_inference2" #这里填写部署后模型的名字
wsid = "10143" #这里固定
enable_stream = True

headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer 7auGXNATFSKl7dF",
    "Wsid": wsid,
}

json_data = {
    "model": model,
    "query_id": "test_query_id_" + str(uuid.uuid4()),
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "你是llama什么版本的模型"},
    ],
    "temperature": 1,
    "top_p": 0.8,
    "top_k": 40,
    "repetition_penalty": 1,
    "output_seq_len": 1024,
    "max_input_seq_len": 2048,
    "stream": enable_stream,
    #"openai_infer": True #司外开源模型用开源框架vllm、sglang等服务调用时必须加上此字段，不加会有冗余逻辑，导致首字耗时超时
}

print('Input:\n{} | {} | {}'.format(ss_url, headers, json_data))
resp = requests.post(ss_url, headers=headers, json=json_data, stream=True)

print('Output:')
if enable_stream:
  client = sseclient.SSEClient(resp)
  for event in client.events():
      if event.data != '':
          data_js = json.loads(event.data)
          try:
              print(data_js['choices'][0]['delta']['content'], end='', flush=True)
          except Exception as e:
              print(data_js)
else:
  print(resp.json())