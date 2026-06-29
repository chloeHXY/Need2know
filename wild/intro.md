## 初试文件
A：/group/40047/eiraxyhuang/workspace/fc/DataG/wild/wild_with_priv_query.parquet
B：/group/40047/eiraxyhuang/workspace/fc/DataG/wild/wild_200_with_priv_query.parquet

## 这两个文件哪里来的？
A：layer2_nature_dialogue/process/stages_full_old/06_ea_na_A.jsonl
B：layer2_nature_dialogue/process/stages_full/03_ea_na_A.jsonl

然后我们使用筛选出来的first_user作为question，去使用训练好的privq模型，获取priv_query,然后我们会先进行一波隐私性评测（就是我们后面用来算SLR EA NE）的脚本，然后先进行一波排序，按照ne泄露个数从低到高排序。

