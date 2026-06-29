# 目标：
评测测试集的隐私泄露率，由于priv_query是暴露给远端不受信任llm的唯一信息端口，即唯一可能隐私泄露源头，因此我们的隐私泄露率主要基于priv_query去计算。

## 输入
使用训练好的模型，对测试集question进行改写得到priv_query字段。
input_file:/group/40047/eiraxyhuang/workspace/fc/DataG/inference/test_with_priv_query.parquet
## 输出
隐私泄露率

## 如何衡量隐私的泄露呢？
1. 参考训练时reward的计算逻辑
/group/40047/eiraxyhuang/workspace/fc/DataG/z_eval/eval_privacy/com_privacy_score.py
具体来说，包括两个部分：
隐私泄露检测 (priv)：基于 `extra_info["ne"]` (= C) 与重写后回答 A
    1.1 Jaccard token Coverage(c in A) == 1.0  → 字面完全覆盖 → return -1
    1.2 BERTScore (rescale_with_baseline=True) 的 P (C→A) 上若 max > 0.3
           → 语义级泄露 → return -1 
2. 计算pii的泄露率，感觉这样更有说服力？
