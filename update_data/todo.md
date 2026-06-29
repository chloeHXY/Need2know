/group/40047/eiraxyhuang/workspace/fc/DataG/update_data
处理该文件夹下的两个parquet文件
处理成一个大的jsonl文件
字段映射逻辑
question: extra_info中的question
essential_spans: extra_info中的 ea key_spans origin_ea 的和
non_essential_spans: extra_info中的 ne
gold_reformulation: reward model 中的ground_truth
essential_policy: extra_info中的essential_policy
data_source: ability
split:
- /group/40047/eiraxyhuang/workspace/fc/DataG/update_data/train.parquet 中的都是train
- /group/40047/eiraxyhuang/workspace/fc/DataG/update_data/0_.parquet中的都是test
最终请打乱顺序