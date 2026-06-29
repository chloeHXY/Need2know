1. 项目背景

我正在构建一个面向 LLM 用户交互隐私保护的 benchmark。这个 benchmark 的核心不是传统的 PII 检测，例如姓名、邮箱、地址识别，而是评估模型是否能够理解 contextual privacy / 上下文隐私。

这里的上下文隐私指的是：

用户在 prompt 中披露的信息，是否对于完成当前任务是必要的。

也就是说，同一个敏感属性在不同任务语境下可能具有不同的必要性。例如：

* 在一个糖尿病治疗建议任务中，“type 1 diabetes” 是必要信息；
* 在一个只需要根据解剖定位判断颅神经受累表现的医学题中，“type 1 diabetes” 可能只是背景病史，并非解题必要信息。

因此，我希望构建一个 challenge set / 挑战集，专门测试模型是否能够判断敏感属性的上下文必要性，而不是简单地看到敏感信息就删除，或者看到医学题就全部保留。

2. 我的核心诉求

我希望你帮助我完成一个数据挖掘和预处理流程：

从已有医学推理数据集中，以敏感属性关键词为锚点，检索包含这些属性的题目，对题目进行聚类，并辅助我标注或筛选出“同一类敏感属性在不同题目中是否必要”的自然对照样本。

请注意：
我不希望从零合成医学题干，因为医学题一旦由模型合成，可能会引入医学事实错误。更可靠的做法是从已有医学推理数据中挖掘自然存在的对照样本。

3. 输入数据说明

输入数据可能来自类似 medical-o1-reasoning 的医学推理数据集。/group/40047/eiraxyhuang/workspace/fc/DataG/layer1_reverse_synthesis/medical_o1_sft.json
一个示例：
{
        "Question": "Given the symptoms of sudden weakness in the left arm and leg, recent long-distance travel, and the presence of swollen and tender right lower leg, what specific cardiac abnormality is most likely to be found upon further evaluation that could explain these findings?",
        "Complex_CoT": "Okay, let's see what's going on here. We've got sudden weakness in the person's left arm and leg - and that screams something neuro-related, maybe a stroke?\n\nBut wait, there's more. The right lower leg is swollen and tender, which is like waving a big flag for deep vein thrombosis, especially after a long flight or sitting around a lot.\n\nSo, now I'm thinking, how could a clot in the leg end up causing issues like weakness or stroke symptoms?\n\nOh, right! There's this thing called a paradoxical embolism. It can happen if there's some kind of short circuit in the heart - like a hole that shouldn't be there.\n\nLet's put this together: if a blood clot from the leg somehow travels to the left side of the heart, it could shoot off to the brain and cause that sudden weakness by blocking blood flow there.\n\nHmm, but how would the clot get from the right side of the heart to the left without going through the lungs and getting filtered out?\n\nHere's where our cardiac anomaly comes in: a patent foramen ovale or PFO. That's like a sneaky little shortcut in the heart between the right and left atria.\n\nAnd it's actually pretty common, found in about a quarter of adults, which definitely makes it the top suspect here.\n\nSo with all these pieces - long travel, leg clot, sudden weakness - a PFO fits the bill perfectly, letting a clot cross over and cause all this.\n\nEverything fits together pretty neatly, so I'd bet PFO is the heart issue waiting to be discovered. Yeah, that really clicks into place!",
        "Response": "The specific cardiac abnormality most likely to be found in this scenario is a patent foramen ovale (PFO). This condition could allow a blood clot from the venous system, such as one from a deep vein thrombosis in the leg, to bypass the lungs and pass directly into the arterial circulation. This can occur when the clot moves from the right atrium to the left atrium through the PFO. Once in the arterial system, the clot can travel to the brain, potentially causing an embolic stroke, which would explain the sudden weakness in the left arm and leg. The connection between the recent travel, which increases the risk of deep vein thrombosis, and the neurological symptoms suggests the presence of a PFO facilitating a paradoxical embolism."
    },

4. 要挖掘的敏感属性类型

请先支持以下医学场景中常见、且具有上下文必要性变化空间的属性类型：
建议你先浏览一下数据，找到经常出现的一些词或者属性，一下是我暂时想到的。
age  
sex_gender: man, woman, male, female, boy, girl
diabetes: type 1 diabetes, type 2 diabetes, diabetes mellitus, diabetic
family_history:family history, mother, father, sibling, brother, sister

等等，建议你可以现在数据中挖掘一下。

