撰写脚本，对文件进行pii标注，标注结果放在 extra_info字段下面

/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.parquet

标注脚本可以参考：/group/40047/eiraxyhuang/workspace/fc/DataG/layer1_reverse_synthesis/Baseline/anonymize.py


用 pandas.read_parquet 读入数据。

对每行的 extra_info：

用 to_mutable_dict 把它统一规范化为可变 dict（兼容 dict / numpy 包装等情况）。

取出 extra_info["question"] 作为待标注文本。

用 Presidio 的 AnalyzerEngine + AnonymizerEngine 进行检测和脱敏。

把结果写回 extra_info 字典：

extra_info["question_anonymized"]：脱敏后的文本。

extra_info["question_pii_entities"]：实体列表，每个实体包含 entity_type start end score text。

把整列 extra_info 用新字典回填，保存到 med.anonymized.parquet。