You are an expert annotator for medical question-answering benchmarks.

Your task is to identify which spans in the original medical question are important for deriving the correct answer, using the provided model response and chain-of-thought/rationale as evidence.

You will be given:
1. A medical multiple-choice question.
2. The model's final response or explanation.
3. The model's chain-of-thought or rationale.

Your goal is NOT to identify all medical entities.
Your goal is to identify only the information in the original question that is relevant to solving the question.

Definitions:

1. essential_spans:
A span from the original question should be labeled as essential if it is directly required to derive the correct answer, distinguish the correct option from other options, or establish the key diagnosis, mechanism, anatomical location, causal relationship, or clinical reasoning path.

A span is essential if removing or heavily abstracting it would likely make the answer incorrect, ambiguous, or much harder to justify.

2. helpful_or_uncertain_spans:
A span from the original question should be labeled as helpful_or_uncertain if it provides useful background, risk factors, severity, timing, clinical realism, or supporting context, but it is not clearly answer-determining based on the response and rationale.

Use this category when:
- the span appears relevant but is not clearly necessary;
- the span is a risk factor or background condition;
- the span helps make the clinical scenario coherent;
- you are unsure whether the span is strictly essential.

Do NOT include:
- boilerplate phrases such as "comes to the physician", "which of the following", "most likely";
- answer options unless they are explicitly part of the question stem;
- spans that are not present in the original question;
- reasoning facts that appear only in the response or CoT but not in the original question.

Important rules:
- Extract spans exactly as they appear in the original question whenever possible.
- Do not rewrite, paraphrase, or normalize spans.
- Prefer concise spans over entire sentences.
- If a long sentence contains both essential and non-essential information, extract only the relevant phrase.
- If a span is mentioned in the response or CoT as part of the answer reasoning chain, it is more likely to be essential.
- If a span is only background information and the answer would likely remain the same without it, place it in helpful_or_uncertain_spans or omit it.
- When in doubt between essential and helpful_or_uncertain, choose helpful_or_uncertain.
- Do not include personally identifying details unless they are medically or logically relevant to the answer.

Return your answer in valid JSON only. Do not include markdown, explanations, or extra text.

Output schema:
{
  "essential_spans": [
    {
      "span": "...",
      "reason": "Briefly explain why this span is necessary for deriving the answer."
    }
  ],
  "helpful_or_uncertain_spans": [
    {
      "span": "...",
      "reason": "Briefly explain why this span may help but is not clearly answer-determining."
    }
  ]
}

Now annotate the following example.

Question:
A 32-year-old man presents to the emergency department with a severe headache. He says that the pain has been getting progressively worse over the last 24 hours and is located primarily in his left forehead and eye. The headaches have woken him up from sleep and it is not relieved by over-the-counter medications. He has been recovering from a sinus infection that started 1 week ago. His past medical history is significant for type 1 diabetes and he has a 10 pack-year history of smoking. Imaging shows thrombosis of a sinus above the sella turcica. Which of the following findings would most likely also be seen in this patient?
A. Anosmia
B. Mandibular pain
C. Ophthalmoplegia
D. Vertigo
E. Vision loss

Response:
The most likely finding in this patient, given the information provided, is ophthalmoplegia. The severe headache in the left forehead and eye area, in conjunction with a sinus thrombosis located above the sella turcica, suggests possible involvement of the cavernous sinus. The cavernous sinus is closely related to several cranial nerves that control eye movement. If these nerves are affected due to the thrombosis, it can lead to ophthalmoplegia, or paralysis of the muscles around the eye, which would be a logical extension of his current symptoms. Therefore, option C, ophthalmoplegia, is the most fitting additional finding in this scenario.

Chain-of-thought / rationale:
So, we've got a 32-year-old man with a really bad headache that's just been getting worse, especially in the left forehead and eye area. And wow, it even wakes him up at night! He's mentioning something about a sinus infection from a week ago, which might be related here.

Let's think about the location of the pain. Since it's around his eye and forehead, I bet something is up around there structurally. Plus, the imaging shows he's got a sinus thrombosis above the sella turcica—that's suspiciously close to the cavernous sinus.

Now, what's in the cavernous sinus? Oh right, several important cranial nerves pass through here: those responsible for eye movement and some facial sensation. If there's a clot, those nerves might get affected, leading to some very specific symptoms.

Speaking of symptoms, he's not responding to over-the-counter meds, which makes sense for something serious like this. And because of the location and those cranial nerves, he could end up with issues controlling eye movements. This is something we'd call ophthalmoplegia, which is quite typical if those nerves get compressed or affected.

Other possibilities like anosmia don't fit as well since the olfactory nerve isn't nearby. Hmm, mandibular pain doesn't match as much either because it doesn’t quite fit the areas impacted by cavernous sinus issues. Vision loss seemed like a contender, but wait, the optic nerve isn't in the cavernous sinus, so scratch that—it can't be it.

I'm thinking vertigo doesn't quite match with our location either. Yep, considering everything, ophthalmoplegia really stands out. It ties in directly with the possible complications of having those cranial nerves tangled with a thrombosis in the cavernous sinus.

So, yeah, I'm going with ophthalmoplegia as the most likely issue he's having in addition to that monstrous headache.