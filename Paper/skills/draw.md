我觉得你抓到重点了：顶会论文里的“主图”不是先画出来的，而是先想清楚它要帮读者完成什么理解动作。工具只是最后一步。

可以把主图理解成论文的“压缩版论证”。它不是装饰，而是在回答：

这篇论文到底提出了什么？为什么和以前不一样？它是怎么工作的？读者看完图能不能在 10 秒内记住核心贡献？

一、主图通常不是从“画什么”开始，而是从一句话开始

* 很多好图背后都有一句非常明确的中心句，例如：

我们的方法把原本需要人工标注/复杂推理/多阶段训练的问题，转化成了一个更简单、更可控的框架。

或者：

现有方法只利用了局部信息，而我们显式建模了全局结构，因此能解决某类失败案例。

这句话就是图的“骨架”。
如果这句话不清楚，图通常也会散。

你可以先逼自己写一句：

This figure shows that ______.

然后再画图。不是先画模块，而是先决定这张图要让读者相信什么。

二、顶会主图常见的几种“内容结构”

1. Problem → Gap → Our Method

这是最常见也最有效的结构。

图里通常会有三块：

左边：输入或任务
中间：已有方法的局限
右边：我们的方法如何解决

它的潜台词是：

不是我凭空提出一个新模型，而是因为旧方法在这里失败，所以我的设计是必要的。

这种图特别适合 NLP 论文，因为 NLP 很多贡献不是“换了个模块”，而是重新定义了任务、训练方式、推理流程或数据构造方式。

⸻

2. Pipeline / Framework

这种图展示方法流程：

输入 → 编码/检索/规划/对齐/训练 → 输出

但好的 pipeline 图不是把所有细节都塞进去，而是突出关键创新节点。

比如一个方法有 7 步，主图可能只画 3 步：

1. 构造信号
2. 进行核心推理/学习
3. 产生目标输出

剩下的放到方法细节或附录。

技能点是：
不要画实现流程，要画认知流程。

实现流程是“代码怎么跑”。
认知流程是“为什么这个方法合理”。

⸻

3. Comparison with Prior Work

这类图通常用来强调“我们和别人不一样”。

例如：

* 以前：single-agent reasoning
* 我们：multi-agent debate
* 以前：static prompt
* 我们：adaptive prompt refinement
* 以前：token-level supervision
* 我们：process-level supervision
* 以前：retrieve then generate
* 我们：retrieve, verify, revise

这种图的重点是对比维度，而不是模块数量。

一个技巧是先写一个表：

维度	旧方法	我们的方法
信息来源	单一	多源
训练信号	结果级	过程级
推理方式	一次性	迭代式
控制能力	弱	强

然后从里面挑最重要的 1–2 个维度画出来。

⸻

4. Conceptual Mechanism

有些顶会图不是 pipeline，而是解释一个“机制”。

比如：

模型为什么会 hallucinate？
为什么某种对齐方法会改善 reasoning？
为什么检索增强可以减少错误？
为什么 instruction tuning 改变了表示空间？

这类图经常是抽象的：圆圈、箭头、空间、分布、层级结构、因果链。

它的构思方式通常是：

现象是什么 → 背后的机制是什么 → 我们的方法干预了哪里

这种图很适合理论味、分析味、interpretability 或 alignment 论文。

三、构思主图时可以用的 skills

Skill 1：先写“图标题”，不是 caption

不要一开始写正式 caption。先写一个像演讲 slide 标题一样的图标题。

差的标题：

Overview of our method.

好的标题：

Our method converts noisy model responses into verifiable training signals.

或者：

Existing retrieval methods retrieve evidence, while ours retrieves evidence and checks its usefulness.

这个标题越有观点，图越容易画。

Skill 2：把论文贡献压缩成 3 个名词模块

顶会主图一般不会让读者记住 8 个模块。它通常让人记住 2–4 个核心模块。

比如：

* Input
* Reasoning Planner
* Verifier
* Final Answer

或者：

* Instruction
* Candidate Responses
* Preference Signal
* Aligned Model

你可以问自己：

如果别人只能记住我方法里的三个词，我希望是哪三个？

这三个词就是图里的大模块。

Skill 3：每个箭头都要有“语义”

很多普通图的问题是箭头只是“下一步”。
好图里的箭头通常表达更具体的关系：

* transforms into
* retrieves
* filters
* aligns
* supervises
* verifies
* decomposes
* aggregates
* contrasts
* updates

也就是说，不要只写：

A → B → C

而要想：

A 被分解成 B
B 被验证后生成 C
C 作为反馈更新 A

主图的高级感很多来自箭头的语义清楚。

Skill 4：区分“主线”和“辅助线”

一张图只能有一条主线。

主线通常是读者眼睛移动的路线：

从左到右，或从上到下。

辅助内容可以放旁边，比如：

* examples
* loss function
* data source
* failure case
* training objective
* evaluation signal

但辅助内容不能抢主线。

一个判断标准：

把辅助内容删掉后，这张图还能不能讲清核心贡献？

能，就说明结构健康。

Skill 5：图里要有一个“before/after”或“pain point”

很多强主图都有戏剧性：
它不只是说“我们做了什么”，还说“为什么需要它”。

比如左边画：

Existing LLM produces plausible but unsupported answer.

右边画：

Our system retrieves evidence, verifies claims, and revises answer.

这比单纯画一个系统 pipeline 更有说服力。

因为读者会先理解问题，再理解方法。

四、一个实用构思模板

你可以每次画主图前填这个：

图想表达的一句话：
我们的方法通过 ______，解决了 ______ 中的 ______ 问题。

读者看图后应记住的三个词：

    ⸻
    ⸻
    ⸻

图的主线：
______ → ______ → ______ → ______

和已有方法的区别：
以前是 ______，我们是 ______。

图中必须出现的例子：
输入：______
中间变化：______
输出：______

如果这五项填不出来，说明还没到画图阶段。

五、顶级论文主图的本质

我觉得最核心的 skill 是：

把方法从“实现细节”翻译成“读者可理解的认知结构”。

普通图在说：

我的模型有这些模块。

好图在说：

这个问题以前为什么难；我的方法抓住了哪个关键变量；这些模块如何共同解决它。

所以你可以把主图当成一个 mini story：

1. 困境：现有方法哪里不够
2. 洞察：我们发现应该利用什么
3. 机制：我们如何利用它
4. 结果：因此输出更可靠/更可控/更高效

画图之前，先把这个 story 写出来。
图只是这个 story 的视觉压缩。
