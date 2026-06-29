## 文件夹中 A / B 的区别

**A 与 B 不是"两套并行的方法"或"两位 judge"，而是同一份数据按"上下文隐私适用性 (contextual privacy suitability)"做的二级类别**。

A/B 来自 [find.py](/group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/process/find.py) 中那段 system prompt 定义的 **A/B/C/D/E 五分类**，由 `gpt-4o-mini` 在阶段 2 给每条 WildChat 单轮 query 打的标签：

| 类别 | 名称 | 含义 |
|---|---|---|
| **A** | `suitable_request_centered_with_overdisclosure` | 请求型 query；含敏感信息；**至少有一些敏感信息看起来与任务无关 / 过度披露** —— 这是 benchmark 最想要的"金样本" |
| **B** | `suitable_request_centered_sensitive_but_maybe_necessary` | 请求型 query；含敏感信息；但**大多数甚至全部敏感信息可能都是任务必需的** —— 作为 hard / borderline 例子保留 |
| C | `request_centered_no_sensitive_disclosure` | 请求型，但没有有意义的敏感披露 |
| D | `artifact_centered_transformation` | 翻译/纠错/总结/改写等 artifact-centered 任务，**排除**出主 benchmark |
| E | `ambiguous_or_insufficient_context` | 太短、太依赖上文、无法独立判断 |

> 原文规则节选：A 中"some sensitive information appears potentially unnecessary or **over-disclosed**"，B 中"most or all sensitive information may be **necessary**"。这正是 contextual privacy benchmark 区分 `E`（必要）vs `N`（非必要）所要测试的两种边界情况。

### 落到具体文件

阶段 2（`process/2_filter_suitable.py`）输出：

| 产物 | 内容 | 说明 |
|---|---|---|
| [`02_suitable.jsonl`](/group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/process/stages_full/02_suitable.jsonl) | 全部 5 类（A/B/C/D/E）打标后的完整结果 | 71 MB，所有记录均含 `suit_category` 字段 |
| [`02_suitable.A.jsonl`](/group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/process/stages_full/02_suitable.A.jsonl) | **`suit_category=="A"` 的镜像子集** | 967 KB；脚本里写明 `mirror of records whose suit_category == "A"`，656 条 |
| `02_suitable_B.jsonl` | `suit_category=="B"` 的子集（手动从 `02_suitable.jsonl` 抽出） | 110 KB；脚本本身没自动产 B 文件，是用同样思路把 B 类导出后命名的 |

阶段 3（`process/3_tag_ea_na_A.py`）—— 用 `gpt-4o` 抽取 `(primary_context, E, N)`：

| 产物 | 输入 | 含义 |
|---|---|---|
| [`03_ea_na_A.jsonl`](/group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/process/stages_full/03_ea_na_A.jsonl) | `02_suitable.A.jsonl`（A 类） | A 类的 E/N 标注，**主 benchmark 的核心金样本**，277 行 |
| `03_ea_na_B.jsonl` | `02_suitable_B.jsonl`（B 类） | B 类的 E/N 标注，作为"几乎全是必要信息"的 **hard / borderline** 子集 |

> 注意：脚本文件名虽叫 `3_tag_ea_na_A.py`，但实际跑的时候只是改了文件头部的 `INPUT_PATH / OUTPUT_PATH` 常量，把同一份脚本复用到 B 类输入上跑了一遍 —— 所以两个 jsonl 的字段 schema 完全相同（都包含 `primary_context / ea / na / tag_model / tag_ok ...`），区别只在于"上游候选池是 A 还是 B"。

### 与旧版 `stages_full_old/` 的对比

旧版（5_/6_ 前缀，`word_max=2500`）文件里也能看到同样的 A/B 命名：

- `05_suitable.A.jsonl` / `05_suitable_B.jsonl`
- `06_ea_na_A.jsonl`（注意旧版里没有 `06_ea_na_B.jsonl`，说明 B 是后来在新版才补跑的）

### 一句话总结

**A = "存在过度披露（non-essential 多）"的优质金样本，是 benchmark 的主测集；B = "敏感信息基本都是必要 (essential 多)"的 borderline 样本，用来挑战 over-removal 失败模式。** 两者由同一段 prompt 在 `gpt-4o-mini` 下打标产生，并各自走同一套 EA/NA 抽取脚本，最终共同构成自然对话锚点集 (`E`, `N`) 的两个互补子集。

如果你愿意，我可以把这段说明补进 [README.md](/group/40047/eiraxyhuang/workspace/fc/DataG/layer2_nature_dialogue/README.md) 里（在"目录结构"和"重要约定"之间加一节 §A/B 类别）。需要我加吗？



## 关于每一阶段的数据量的说明
运行layer2_nature_dialogue/process/length_stats.py得到:
原本就是350,163条真实对话，然后单轮+英语+长度筛选出来时5W条，然后gpt4o-mini打标 ABCD，最终论文披露的656是指02_suitable.A.jsonl 中的条数。
``` txt
=== Natural single-turn English (turn=1, lang=en, toxic=F, redacted=F) ===
  N        = 129,038
  mean     = 259.5
  median   = 111
  stdev    = 348.7
  min,max  = 1, 6959
  percentiles:
    p1    =      4.0
    p5    =      7.0
    p10   =     10.0
    p25   =     29.0
    p50   =    111.0
    p75   =    450.0
    p90   =    492.0
    p95   =    806.0
    p99   =   1615.0
  share in [25,250] = 50,030 / 129,038 = 38.77%
  histogram:
          [0,10)    11,346  #####
         [10,25)    17,819  ########
         [25,50)    13,550  ######
        [50,100)    19,233  ########
       [100,150)     8,725  ####
       [150,200)     5,141  ##
       [200,250)     3,320  #
       [250,350)     4,683  ##
       [350,500)    32,805  ###############
       [500,750)     5,204  ##
      [750,1000)     2,835  #
     [1000,1500)     2,740  #
     [1500,2500)     1,348  
    [2500,1000000000)       289  

=== Raw S0 (no language/turn filter) ===
  N        = 350,163
  mean     = 167.8
  median   = 22
  stdev    = 342.1
  min,max  = 1, 22343
  percentiles:
    p1    =      1.0
    p5    =      1.0
    p10   =      1.0
    p25   =      6.0
    p50   =     22.0
    p75   =    152.0
    p90   =    455.0
    p95   =    807.0
    p99   =   1526.0
  share in [25,250] = 97,849 / 350,163 = 27.94%
  histogram:
          [0,10)   118,781  ####################
         [10,25)    61,680  ##########
         [25,50)    33,338  #####
        [50,100)    33,245  #####
       [100,150)    14,987  ##
       [150,200)     9,374  #
       [200,250)     6,802  #
       [250,350)     9,247  #
       [350,500)    35,623  ######
       [500,750)     8,156  #
      [750,1000)     4,966  
     [1000,1500)     9,631  #
     [1500,2500)     3,899  
    [2500,1000000000)       434  

=== After S1 (01_struct.jsonl, already clipped to 25..250) ===
  N        = 50,030
  mean     = 91.6
  median   = 75
  stdev    = 56.3
  min,max  = 25, 250
  percentiles:
    p1    =     25.0
    p5    =     28.0
    p10   =     33.0
    p25   =     47.0
    p50   =     75.0
    p75   =    123.0
    p90   =    180.0
    p95   =    212.0
    p99   =    247.0
  share in [25,250] = 50,030 / 50,030 = 100.00%
  histogram:
          [0,10)         0  
         [10,25)         0  
         [25,50)    13,550  ################
        [50,100)    19,233  #######################
       [100,150)     8,725  ##########
       [150,200)     5,141  ######
       [200,250)     3,320  ###
       [250,350)        61  
       [350,500)         0  
       [500,750)         0  
      [750,1000)         0  
     [1000,1500)         0 
```

同时进一步的使用gpt-4o反向校验，大概有，276（03_ea_na_A.jsonl）+192（06_ea_na_A.jsonl）的数据进入下一层

但不是终点，还需要去wild中进行进一步的筛选