
# 数据构建

## 1. 总体设计

与传统 PII 检测或脱敏数据集主要回答"哪些 token 是敏感信息"不同，本文聚焦于上下文过度披露 (contextual over-disclosure)：在用户与大语言模型 (LLM) 的交互场景中，一段敏感属性是否应被保留并不取决于其是否敏感，而取决于其对于完成当前任务是否必要。围绕这一定义，我们构建了一个面向 *contextual privacy* 的 benchmark，用以系统评测改写器 (rewriter) 能否在保持任务效用的前提下，区分**任务必要的敏感信息 (essential, E)** 与**任务非必要的敏感信息 (non-essential, NE)**，并据此对用户 prompt 进行最小化重写。

整个数据集由两层组成，覆盖"通用域 + 医学高风险域"两种互补的评测视角：

* **第一层（L1）：通用反向合成数据**。用于构造覆盖广、可控性强、可批量扩展的训练与评测样本，是当前训练阶段的主体数据。
* **第二层（L2）：医学领域挑战集**。在真实医学考试题之上注入受控的、非任务相关的私人信息，用于压力测试模型在"敏感即任务核心"场景下的过度删除问题 (over-removal)。

下文将分别给出两层数据的方法学描述，并在每一层强调其相对于已有 PII / 隐私改写数据集的差异化贡献。

## 2. 第一层：基于反向合成的通用 contextual-privacy benchmark

### 2.1 反向合成的动机

直接让 LLM 生成"包含 over-sharing 的用户 prompt"再事后标注，将 essential 与 non-essential 的判定完全交由后置标注模型，存在两个问题：(i) 后置标注的 essential / non-essential 标签缺少可验证的"金标准"基线，难以与生成内容形成闭环约束；(ii) 难以系统覆盖 domain × task × subject × 写作风格 × 情绪基调等组合空间，容易在风格上塌缩到某几个高频模式，从而被改写器以近似"模式记忆"方式 reward-hacking。

为此，我们采用**反向合成 (reverse synthesis)** 策略：先以结构化方式采样出语义骨架（包括领域、任务类型、提问主体、敏感属性集合及其 essential / non-essential 标签），再由生成模型把这些骨架自然地嵌入到一段语气、风格、长度受控的用户 prompt 中。最后由一个独立的 LLM judge 对生成 prompt 反向抽取其 primary context、essential 与 non-essential 属性，与采样阶段的预设标签做一致性校验，仅保留通过校验的样本。这一闭环使得每条样本都同时具备：自然的口语化表达、可控且高覆盖的属性组合，以及由独立模型反向认证的 E/NE 金标签。

### 2.2 三阶段闭环：Sampler → Generator → Judge → Reformulator

#### 2.2.1 结构化采样器 (Sampler)

我们以三个层次的分类体系为采样空间：

* **领域 (domain)** 11 类，覆盖健康与保健、金融与企业、雇佣与申请、学术与教育、法律、人际关系、旅行、爱好与习惯、性与情爱、政治、宗教（沿用 Ngong et al., 2025 附录 D 的领域定义）。
* **任务类型 (task)** 20 类，涵盖摘要、代码生成与调试、翻译、信息检索、个人建议、角色扮演、多选问答等典型用户场景（沿用其附录 E.3）。
* **敏感属性 (attribute)** 30 项，包括姓名、邮箱、地址、电话、社保号、年龄、医疗与心理健康、家族史、饮食、爱好、宗教、性取向、雇佣、财务、法律、日期等（参考 AirGap / Bagdasaryan et al., 2024）。

为了让采样既具备高覆盖、又服从合理的语义先验，我们引入两个层级的设计：

**(a) 领域级"必要属性候选池" (per-domain essential pool)**。我们针对每个领域人工策划一个候选属性子集，其策划准则是：*"在该领域中，若用户拥有此属性，它在多大程度上可能影响一个有用回答？"* 例如健康域的候选池包含 `physical_health / mental_health / medications / allergies / disabilities / exercise_hours / diet_type / age`，而旅行域的候选池则包含 `vacation_prefs / dates / address / diet_type / disabilities` 等。这是一个**软先验**：我们不会硬性要求 essential 一定来自该池，而是允许后续的任务策略在合适场景下覆盖该先验。

**(b) 任务级"必要性策略" (per-task essential policy)**。我们观察到，并非所有任务都存在"任务必要的敏感信息"：例如代码生成、翻译、摘要、文本编辑、多选问答这类**任务自洽 (task-driven)** 的请求，理论上不依赖任何用户敏感属性即可被正确回答；而个人建议、问题求解、生活建议等**用户语境驱动 (advice-driven)** 的请求则天然依赖部分用户属性；再如沟通生成、剧本/诗歌生成、人物刻画等**指名对象 (addressed-person)** 任务，被指名的人物姓名本身即为任务必要信息。我们将 20 类任务按上述三种语义模式分别映射到 `none / domain / addressed_person` 三种采样策略：

  * `none` 策略：不抽取任何 essential 敏感属性，转而从一个非敏感的"任务简述池 (task brief)"中抽取一条具体请求作为任务核心（如"写一段去重 Python 函数"、"翻译一段法语到英语"）；同时上调 NE 属性数量 (≥2)，模拟真实用户在任务驱动请求中过度披露无关私人信息的行为。
  * `domain` 策略：从该领域的 essential 候选池中抽取 1–2 个属性作为 E，再从剩余属性中抽取 1–3 个作为 NE。
  * `addressed_person` 策略：强制将 `name` 纳入 E（部分子任务还包含 `age / gender`），并以 0.4 的概率从领域池追加一个 E 属性，模拟"为某位具名对象写邮件/诗歌"等场景。

**(c) 多样性轴 (diversity axes) 与困惑样本 (confusion samples)**。我们另外引入三条正交的多样性轴：提问主体 (`self / family / friend / coworker / third_party`)、嵌入风格 (`direct / narrative / implicit / multi_sentence`) 与情绪基调 (`neutral / frustrated / casual / urgent / formal / anxious`)，强制生成器在文体层面进行变化，避免模板化输出。在此之上，我们以 15% 的概率主动构造两类**对抗性困惑样本**：

  * *Shared-attribute 困惑*：同一类型属性（如 `physical_health`）同时出现在 E 与 NE 中，但 NE 那条被显式标记为属于第三方（亲属、同事、朋友、泛交），生成器需在自然措辞中区分两者归属。这一设计直接攻击改写器"按属性类型粗粒度删除"的捷径策略。
  * *Over-removal trap*：在 addressed-person 任务上，强制将 `name`（与可选的领域属性）置为 essential，用于检验改写器是否会因为"姓名通常敏感"这一先验而过度脱敏，导致诸如"为 Anastasia 写一首生日诗"在脱敏后失去其指代对象的极端失效。

每个属性的具体取值由一个**值库 (value bank)** 提供：每个属性维护一个约 10–30 项的人工策划取值列表（如医疗用药、过敏原、家族病史模板、收入与法律状态等），结构化字段（电话、邮箱、SSN、驾照号、年龄、日期）由本地化的合成函数即时生成；生成器在 prompt 中被明确允许对该值进行同义改写或微调，使得值库仅作为多样性的种子，而非硬模板。

#### 2.2.2 生成器 (Generator)

生成器是一个 LLM-based 文本合成器，其 prompt 严格依赖采样器输出的结构化 spec，按 essential 策略分支为两套模板：

* 对 `none` 策略，告诉生成器"任务可以在不知道用户任何信息的前提下被回答"，要求其在自然嵌入所有 NE 属性的同时把任务陈述写清楚，模拟"被无关私人信息淹没的任务请求"。
* 对 `domain / addressed_person` 策略，则进一步约束 essential 属性必须在文中"如果删除则回答不再成立"，NE 属性必须"删除不影响回答质量"，并附加领域、写作风格、情绪基调与第三方主体提示等多种自然语言指令。

为对抗生成器的常见失效模式（输出 JSON、加引号、过短、过长、临时编造新 PII），我们在 pipeline 中加入轻量级输出守门：拒绝以 `{` 开头的输出、拒绝长度超出 [20, 4000] 字符区间的输出，并对失败样本进行有限次重试。

#### 2.2.3 一致性裁判 (Judge) 与软/硬失败分级

一致性校验是反向合成闭环的关键。我们使用一个独立的 LLM judge 在仅看到生成 prompt 的前提下，输出 `(primary_context, essential_attributes, nonessential_attributes)` 三元组（提示模板对齐 Ngong et al., 2025 附录 E.1，并强制使用 JSON mode）。然后将 judge 抽取结果与 sampler 的预设标签做属性级配对。配对采用**两级匹配器**：

1. *Token 重叠匹配*：以去停用词后的 token 集合计算"采样值 ∩ judge 抽取值"的覆盖率，阈值 0.5；
2. *Embedding 余弦回退*：当 token 匹配未命中时，使用预先批量计算的 embedding 做余弦相似度匹配，阈值 0.65；这一回退专门用于处理 judge 自然改写带来的表层偏移（如 "grandmother died from alcoholism" ↔ "grandmother passed away from complications related to heavy drinking"）。

匹配结果汇总为 essential recall、non-essential recall，以及四类**误归类指标**：`essential_misses`、`nonessential_misses`、`swapped_essential_into_ne`（采样为 E 却被 judge 归为 NE，提示生成器嵌入不到位）、`swapped_ne_into_essential`（采样为 NE 却被 judge 视为 E，提示 NE 选取不合理）以及 judge 额外标出的 `extra_nonessential`（可能是模型自带 PII 泄露或值得保留作为 reward shaping 信号）。综合上述指标，我们将每条样本划分为三档：

* **PASS**（floor ≥ 0.8）：进入主训练 / 评测集；
* **SOFT\_FAIL**（floor ∈ \[0.5, 0.8)）：保留并打 SOFT\_FAIL 标签，用于 RL 评测与困难样本挖掘；
* **HARD\_FAIL**（floor < 0.5）：默认仍写入但状态置位，可下游过滤。

对 `none`-策略样本，由于不存在 essential 敏感属性，essential recall 定义为 1.0，但若 judge 将多数 NE "提拔"为 essential，会通过对 `swapped_ne_into_essential` 比例的惩罚反映在最终 floor 上，从而约束 NE 的合理性。

#### 2.2.4 黄金改写 (Reformulator) 与最终样本结构

每条通过一致性校验的样本进一步被送入第三个 LLM ——**改写器 (reformulator)**，按照对齐 Ngong et al., 2025 附录 E.6 的提示设计，将原 prompt 改写为一条"保留 essential、删除或泛化 NE、不回答原请求"的最小化版本，作为该样本的**黄金改写参考 (gold reformulation)**。最终每条样本以 JSONL 形式存储以下字段：原始 spec（domain / task / subject / 风格 / 情绪 / E / NE / 困惑类型）、生成的 raw\_prompt、judge 抽取结果、一致性报告及 PASS/SOFT/HARD 状态、黄金改写文本，以及生成与改写所用模型端点和时间戳等元数据。

### 2.3 工程实现要点

整个流水线以异步并发方式实现：通过 `asyncio` 信号量绑定全局并发度、行缓冲方式追加 JSONL 输出，使任意阶段的中断都不会破坏已落盘样本；LLM 端点抽象层支持 OpenAI 兼容协议与企业代理（Venus）双后端，并对每次调用记录 token 用量与 USD 计费，便于对生成器、judge、改写器三个角色的成本进行独立审计。

### 2.4 第一层数据的方法学贡献

综合上述设计，第一层数据相对已有 PII 数据集的差异化贡献可归纳为：

1. **以 essential / non-essential 为一等公民的标签体系**：每条样本都同时携带"采样侧金标签"与"独立 judge 反向标签"，并经一致性匹配过滤，避免使用单一模型既出题又评分带来的循环偏差。
2. **任务驱动 vs. 语境驱动的统一建模**：通过 `none / domain / addressed_person` 三种 essential 策略，把"代码题这种本就不需要 PII 的请求"和"个人健康咨询这种本就依赖 PII 的请求"统一在同一框架下，覆盖了已有数据集普遍忽视的"任务自洽下的纯过度披露"分布。
3. **可控的对抗性困惑样本**：shared-attribute 与 over-removal-trap 两类困惑样本直接针对改写器最常见的两种捷径——"按属性类型粗粒度删除"与"凡名字皆删"——形成定向压力测试。
4. **可审计的失败样本保留**：SOFT\_FAIL / HARD\_FAIL 与若干误归类指标被显式保留，可直接用作 RL 阶段的困难样本挖掘信号或 reward shaping 输入，而非简单丢弃。

## 3. 第二层：医学领域挑战集

### 3.1 设计动机

在医学场景下，contextual privacy 评测面临一个特殊困境：**敏感信息往往同时也是任务核心信息**。一个"凡是健康相关字段一律删除"的隐私改写器，在常规隐私指标上可以获得很高的分数，却会把"45 岁男性、糖尿病史、近三月体重下降 8 kg"等关键临床证据一并抹去，导致下游医学问答严重失能。常规通用 benchmark 难以暴露这类失败。

为此，我们构建了医学挑战集 L2：以**真实医学执业考试风格的多选题**为骨架（基于公开的 medical-o1 SFT 数据），并向其中**受控注入与医学任务无直接关系的合成私人信息**（姓名、合成病历号、合成挂号 ID、合成邮箱/电话、中性职业、就诊渠道等）。挑战目标是：模型必须在保留所有医学决策证据的同时，识别并删除这些附带性 (incidental) 隐私信息。

### 3.2 七阶段处理流程

L2 数据流以 parquet 为持久化格式，按编号脚本顺序串联七个阶段，每个阶段均为可独立复现的纯函数式变换：

**阶段 0 — 关键证据片段标注 (key-span labeling)**。我们以高级临床医生的解题链 (Chain-of-Thought) 与最终答案为锚，让 GPT-4o 从原始题面中**逐字抽取**最具决定性的连续证据片段 (key spans)，每个 span 同时附带"为什么这一片段对最终答案至关重要"的简短解释。提示词中显式约束 span 必须**逐字保留原题措辞**、不得跨句、不得合并、不得引入题外医学知识，并在医生 CoT 与最终答案冲突时以最终答案为准并标注不一致。这一阶段产生该样本的"医学必要信息白名单"，是后续评测改写器**未删除关键证据**的真实金标签。该阶段以异步并发请求 + JSON 强解析（含 markdown 围栏剥离与对象级正则回退）实现，并支持断点续跑：每次运行会自动加载历史标注 JSONL 中已有的 `index` 与 `Question` 集合作为排除集，避免重复消耗 token。

**阶段 1 — 合成 PII 注入 (synthetic PII injection)**。我们以高度严格的改写指令引导 GPT-4o 把每道原始题改写为 `Syn_Question`：所有临床相关字段（年龄、性别、症状、体征、化验、影像、诊断、用药、剂量、时间线、风险因素、既往史、问题本身与四个选项及正确答案）必须**逐字保留**；只允许追加合成的姓名、合成病历号 / 就诊 ID、`example.com` 邮箱、明显伪造的电话号、以及不影响医学推理的中性职业等；明确禁止追加种族、地理位置、家族史、出行史、性史、物质使用、饮食、运动、孕产、疫苗、社经地位、环境暴露等"看似无关但可能干扰临床推理"的字段。这一**白/灰/黑名单三段式**改写约束，是 L2 区别于普通 PII 注入数据集的关键：它从源头上保证注入的 PII **不会对正确答案产生任何医学语义干扰**，从而让后续评测能将"删除 PII 后医学正确率"作为干净的 over-removal 度量。改写阶段使用稍高温度 (0.7) 以增加合成 PII 的多样性。

**阶段 2 — Presidio PII 检测 (PII annotation)**。我们使用 Microsoft Presidio 对 `Syn_Question` 做实体级检测，得到 `(entity_type, span 起止, 置信度, 文本)` 五元组列表，并直接写回 `extra_info` 字段下，避免破坏上游已有的 schema。

**阶段 3 — 规则化实体清洗 (entity cleaning)**。Presidio 的召回偏宽，会把一些"看起来像但实际并非 PII"的片段也纳入。我们设计了一组面向医学题面的清洗规则：保留 `PERSON / US_DRIVER_LICENSE / US_BANK_NUMBER`；对 `DATE_TIME` 仅保留形如 "45-year-old / 3-month-old" 的年龄表达；对 `LOCATION` 仅保留人工策划的真实地名白名单（含国家、地区、美国州简码等），并且会先剥离 MCQ 选项前缀（"A. ", "B) " 等）后再做匹配，命中后回写校正后的 span 起止与文本，使 span 严格指向地名本身。其余如 `NRP / US_PASSPORT / US_ITIN / URL / PHONE_NUMBER` 等噪声实体一律丢弃。这一步显著降低了 NE 标签的假阳率，是 L2 评测可信度的前提。

**阶段 4 — 黄金答案推理 (ground-truth reasoning)**。我们以 GPT-4o 对每条样本的对话格式 prompt 进行推理，将自然语言形式的解释性回答写入 `extra_info.query_gt`。这一步给出每道题的**模型可达上界 (upper-bound)** 答案，作为后续评测改写器是否破坏医学推理链的参考。

**阶段 5 — 自然语言答案到选项标签的映射 (answer label normalization)**。原始数据集的 answer 字段是自然语言解释。我们使用一个零温度、最多 16 token 的"严格选项裁判"：在系统提示中明确要求其只输出 `A/B/C/D/E/UNKNOWN` 之一，并通过正则后处理与多重 fallback 抽取最终选项标签，写入 `extra_info.answer_label`。这使得医学正确率可以用最简单的字符串匹配进行精确评测，避免自由文本答案带来的评分歧义。

**阶段 6 — Schema 收敛与字段精简 (schema cleanup)**。该阶段由若干小补丁脚本构成：
* 6\_1：将 `key_spans` 从 `{span, reason}` 字典列表精简为纯 span 字符串列表（reason 信息保留在备份中，仅供消融分析使用，不进入正式样本）；
* 6\_2：用正则匹配并移除残留在 `key_spans` 中的形如 "year/month/week/day/yr/mo/...-old" 的年龄串，避免年龄串同时出现在 NE（来源于 Presidio 的 DATE\_TIME 年龄识别）与 key\_spans 之中造成评测口径冲突；同步生成原文件备份；
* 6\_3：把医学黄金答案 `extra_info.query_gt` 同步写入 RL 训练所需的 `reward_model.ground_truth` 字段，缺失值不覆盖。

**阶段 7 — 字段重命名、分割与发布 (final packaging)**。最终阶段执行三组操作：(a) 把上游名称统一为公开 schema：`question_pii_entities → ne`、`key_spans` 保持不变、`answer ← query_gt`，并新增 `origin_ea` 占位字段以兼容外部 evaluator 接口；(b) 用固定随机种子按 0/1000 比例切分 train/test（当前阶段医学层完全用作测试集），同时把 split 标签写入 `extra_info.split` 与顶层列；(c) 写出整体 parquet 与 train / test 切片三份文件。

### 3.3 第二层数据的方法学贡献

L2 的核心贡献在于：**把"敏感即任务核心"的医学场景显式建模为一个 contextual-privacy 极端点**，并提供了三类标签对的解耦：

1. *医学必要白名单* (`key_spans`) — 由医生级 CoT 反向抽取、逐字校验，作为不可删除的硬约束；
2. *任务无关 PII 黑名单* (`ne`) — 由严格白/灰/黑名单注入 + Presidio 检测 + 规则清洗共同生成，保证 NE 与 E 在医学语义上严格不耦合；
3. *答案口径双标签* (`query_gt` 自然语言 + `answer_label` 选项字母) — 自然语言用于评测推理链是否完整保留，选项字母用于做精确正确率统计。

借助这三组标签，L2 可以同时给出三类指标：(i) 隐私分数（NE 删除率）、(ii) 任务效用分数（医学正确率）、(iii) 关键证据保留率（key\_spans 在改写后是否仍可恢复）。这种**多视角指标**使得"删得多 = 隐私分高"的简单基线在 L2 上会立刻暴露任务效用塌陷，从而把 over-removal 问题前置到 benchmark 设计层面，而非延后到下游应用中才被发现。

## 4. 数据使用与定位总结

* L1 反向合成数据规模可批量扩展，并自带 PASS / SOFT\_FAIL / HARD\_FAIL 状态与误归类指标，是当前模型训练与通用评测的主体来源；
* L2 医学挑战集规模相对受限但标签密度高，专用于过度删除压力测试与跨域泛化评估；
* 两层数据共享统一的 essential / non-essential 抽象，使得在 L1 上训练的改写器可以直接在 L2 上做零成本评测，不需要额外的 schema 适配。

整体而言，本数据集将 contextual privacy 从一个偏理念性的指标具象化为一组**可控、可复现、可审计**的样本生成流水线，并通过通用域 + 医学域的两层组合，覆盖了"任务驱动 / 语境驱动 / 敏感即核心"三种典型 contextual-privacy 形态，为后续的隐私改写器训练与评测提供了相对完整的数据基座。
