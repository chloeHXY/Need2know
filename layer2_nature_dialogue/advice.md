需要注意，而且这会直接决定你的 benchmark 是否“可信、可复现、可发布”。如果你基于第一篇的出发点加入真实交互数据，我建议重点讲这几个方面。

1. 不要把真实数据直接等同于“真实隐私风险”

真实交互数据的优势是自然，但它也有很多噪声。用户可能开玩笑、虚构角色、粘贴别人的文本、让模型改写小说、翻译邮件或总结材料。

所以第一步不能只是问：

这条 prompt 里有没有敏感信息？

而是要先判断：

这条 prompt 是否代表一个真实用户在向 LLM 完成某个任务？
其中的信息主体是谁？是用户本人、第三方、虚构角色，还是被引用文本中的人物？

第一篇文章也强调 contextual privacy 要从 sender、subject、receiver、context、transmission principle 这些信息流要素出发，而不是只看实体本身。 ￼

⸻

2. 真实数据要先做“任务适配筛选”

如果你的 benchmark 评估的是“用户是否过度披露了完成任务不必要的信息”，那就要筛掉不适合这个任务的数据。

建议至少过滤掉：
多轮强依赖上下文的 query	原因:很难判断当前轮中哪些信息必要
极短 prompt	原因:缺少足够语境
极长 prompt	原因:标注成本高，span 边界复杂
纯代码、纯数学、纯格式转换	原因:通常不涉及上下文隐私
明显虚构/角色扮演文本	原因:不一定代表真实披露
用户要求逐字翻译/润色的文本	原因:“保留原文”本身可能是任务要求
包含大段第三方邮件、简历、合同的文本	原因:需要单独标记“引用文本/第三方信息”

第一篇的做法是从 ShareGPT 的 9 万多条对话中，只保留 单轮、25–2,500 words 的样本，最后得到 11,305 条候选，再进一步筛出 2,849 条明确存在 contextual privacy violation 的样本。这个筛选逻辑很值得借鉴。 ￼

⸻

3. 要区分“显式 PII”和“上下文敏感信息”

你的 benchmark 如果想继承第一篇的出发点，就不要只标姓名、地址、邮箱、公司这些 PII。

真实交互中很多风险不是传统 PII，而是：

类型    示例
健康状态    疾病、诊断、用药、心理状态
家庭关系	配偶、孩子、父母、朋友关系
财务压力	收入、债务、医疗开销、负担能力
行踪计划	具体时间、地点、同行人
工作教育	被裁员、公司、学校、职位
第三方信息	朋友、家人、同事的经历和身份
情感/社会处境	婚姻、亲密关系、身份困境

第一篇里的例子就不是单纯 PII 检测：比如“朋友 Mark 被 Google 裁员”“和 Gina、Emma 在某地跑步”“儿子被诊断糖尿病”“妻子和女儿名字”等，重点是这些信息对原任务是否必要。 ￼

⸻

4. 必须标注“信息必要性”，否则 benchmark 会退化成 PII benchmark

这是最关键的一点。

每个敏感片段都应该标注：

字段	含义
sensitive span	原文中的敏感片段
subject	信息关于谁
sensitivity type	健康、财务、身份、地点、家庭等
necessity label	essential / helpful but not necessary / non-essential
recommended action	keep / generalize / remove / ask user
rationale	为什么这个信息必要或不必要

例如：

“我朋友 Mark 刚从 Google 被裁员，想找 ML 和 Python 工作，有什么建议？”

可以标成：

片段	必要性	处理
Mark	non-essential	remove
Google	helpful but not necessary	generalize to “large tech company”
laid off	helpful / possibly essential	keep or generalize
ML and Python	essential	keep

这样你的 benchmark 才能体现 contextual privacy，而不是简单红掉所有敏感词。

⸻

5. 要保留“任务效用”维度，避免过度匿名化

真实数据里，一个常见问题是：隐私保护模型为了安全，把任务需要的信息也删掉了。

例如医疗咨询中，“糖尿病”是敏感信息，但对回答治疗建议是必要的。第一篇明确把 contextual privacy 定义为：用户 query 不包含 nonessential sensitive attributes，而不是不包含任何敏感属性。 ￼

所以你的 benchmark 需要同时评估：

是否删除了非必要敏感信息；
是否保留了必要信息；
是否还能完成原任务。

否则模型可能通过“一刀切删除所有敏感信息”拿到很高隐私分，但实际不可用。

⸻

6. 真实交互数据要做伦理和发布处理

如果你要发布 benchmark，尤其要注意：

真实数据即使来自公开数据集，也不代表可以原样再分发。最好做几层保护：

1. 删除或泛化直接身份标识，如姓名、邮箱、电话、社交账号、具体地址。
2. 对第三方信息格外谨慎，因为被提到的人未必同意数据公开。
3. 对高风险领域做更强处理，如医疗、法律、未成年人、财务危机、家庭冲突。
4. 发布时尽量提供脱敏文本、标注标签和改写版本，而不是原始完整 prompt。
5. 对特别具体、可搜索、可复原身份的样本进行删除，而不是匿名化。

PAPILLON 也提到，虽然 WildChat 用户交互已经发生在 ChatGPT/GPT-4 上，但他们仍然会在发布 PUPA 时替换完整姓名，并移除不合适内容。这个伦理处理思路可以借鉴。 ￼

⸻

7. 标注时不要完全依赖 LLM judge

可以用 LLM 做初筛，但最终 benchmark 最好有人工验证，至少对核心测试集做人工标注。

因为“必要性”很主观，LLM 容易出现两类错误：

错误	影响
把必要信息判成非必要	损害任务效用
把非必要信息判成必要	造成隐私泄露
把虚构内容当真实隐私	误报
忽略第三方隐私	漏报
对不同文化/领域背景判断不稳定	标注偏差

第一篇虽然使用 Llama-3.1-405B-Instruct 做 judge，但也承认需要通过人工评估检验改写是否移除了非必要信息、保留必要信息、保留原意且自然。 ￼

⸻

8. 建议设计“真实数据 + 控制挑战集”的组合

单纯真实数据有自然性，但覆盖不均衡。你可以这样讲 benchmark 设计：

We combine naturally occurring user-LLM interactions with a controlled challenge set. The real-world subset captures authentic patterns of user over-disclosure, while the challenge subset systematically varies the necessity and sensitivity of information under different task contexts.

中文：

我们将真实用户交互数据与控制式挑战集结合。真实数据用于捕捉自然发生的用户过度披露模式，挑战集则系统控制敏感信息类型、任务语境和必要性标签，以测试模型是否真正理解上下文必要性。

这个设计会比只用 ShareGPT/WildChat 更稳。

⸻

9. 可以把真实数据构建流程说成这样

你可以在论文里这样描述：

We first collect candidate prompts from public user-LLM interaction datasets. To align the data with our contextual privacy task, we filter for single-turn prompts that contain a clear user intent and sufficient contextual information. We exclude prompts that are highly context-dependent, purely fictional, purely technical, or dominated by quoted third-party documents. Each remaining prompt is annotated with the user intent, subject of disclosure, sensitive spans, sensitivity type, contextual necessity, and recommended privacy-preserving action. To improve annotation quality, we use LLMs for candidate mining and preliminary labeling, followed by human verification on the benchmark test set. Finally, we release only sanitized prompts and structured annotations to reduce the risk of re-identification.

中文可以写成：

我们首先从公开用户—LLM 交互数据中收集候选 prompt。为使数据与上下文隐私任务一致，我们筛选具有明确用户意图、能够单轮理解且包含潜在敏感披露的样本，并剔除强依赖上下文、明显虚构、纯技术任务或以大段第三方引用文本为主的样本。随后，我们为每条样本标注用户意图、信息主体、敏感片段、敏感类型、上下文必要性以及推荐处理方式。标注过程中，LLM 用于候选挖掘和初步标注，人工标注者负责验证核心测试集。最终发布时，我们仅公开脱敏后的 prompt 和结构化标注，以降低重新识别风险。

⸻

一句话总结

加入真实交互数据时，最重要的是不要只追求“真实”，而要保证它能服务于 上下文必要性判断。你需要同时处理四个问题：

样本是否真的代表用户任务；信息是否敏感；敏感信息是否对任务必要；发布后是否会再次伤害用户隐私。