# 目标

这是数据 /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_answer_label.parquet
中的一个片段：
"query_gt":"What is the expected PaO2 level in an adult presenting with tachypnea, tachycardia, and cough following a pulmonary embolism?"
"question":"Mary Johnson is a 65-year-old woman with synthetic chart ID 123456 who presents four days after undergoing an elective total hip replacement. She develops a DVT that embolizes to the lung. Along with tachypnea, tachycardia, and cough, the patient would most likely present with a PaO2 of what?\nA. 120 mmHg\nB. 110 mmHg\nC. 100 mmHg\nD. 85 mmHg\nE. 60 mmHg"

"key_spans":[{"reason":"This span is important because the doctor identified recent surgery as a risk factor for DVT and subsequent PE.","span":"elective total hip replacement"},{"reason":"The patient's age is relevant as it may increase the risk of complications like DVT and PE.","span":"65-year-old woman"},{"reason":"This span directly describes the condition leading to the patient's symptoms and hypoxemia.","span":"develops a DVT that embolizes to the lung"},{"reason":"These symptoms are critical in diagnosing PE and assessing the severity of hypoxemia.","span":"tachypnea, tachycardia, and cough"}]

我们获取了key_spans后，需要进行二次校验，即确保这里面的每个数据项是真的对于question的解答必要。
你觉得可以怎么校验？

