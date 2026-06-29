## baseline

- papillon：是使用一个本地模型llama3.1-8b-instruct模型撰写提示词对用户question进行改写得到priv_query
- prediax: 是一个pii屏蔽方法，直接对question中的pii进行识别然后覆盖，得到priv_query
- our: 如果你想知道我们方法的细节，可以看：Method.md
- 如果你想知道我们评估数据的细节可以看：Data.md

## 评估

eval_privacy.py

- SLR EA NE PII
- utility评估：eval_utiility.py

有关评估结果：
res.txt

最终实验呈现见exp.tex