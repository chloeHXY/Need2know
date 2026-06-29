input="""
You are an expert in medical exam question analysis and evidence-span annotation.

I will provide three inputs:
1. A medical question;
2. A senior doctor’s chain of thought (CoT);
3. The doctor’s final answer.

Your task is to analyze the key reasoning points from the doctor’s CoT and final answer, then select the most important evidence spans from the original medical question.

Please follow these requirements strictly:

1. Extract spans only from the original medical question. Do not rewrite, summarize, or add information.
2. Each span should be a key piece of information that supports the diagnosis, differential diagnosis, treatment choice, test selection, or final answer.
3. A span should not be a full sentence. It should be a short continuous text segment, such as a symptom, sign, lab result, imaging finding, medical history, medication history, age/sex, or disease timeline.
4. Prioritize spans that are repeatedly used, clearly relied on, or directly decisive in the doctor’s CoT and final answer.
5. Do not select irrelevant background information, generic descriptions, stylistic wording, or details that do not materially affect the answer.
6. If multiple spans together form the basis of the solution, list all of them.
7. Each span must preserve the exact wording from the original question. Do not split words or use synonyms.
8. For each span, explain why it is important, but base the explanation only on the doctor’s CoT and final answer. Do not introduce outside medical knowledge.

Input format:

Medical Question:
{{Question}}

Doctor’s CoT:
{{Complex_CoT}}

Doctor’s Final Answer:
{{Response}}

Output only the following JSON format:

{
  "answer_summary": "Summarize the doctor’s reasoning approach and final judgment in 1-2 sentences.",
  "key_spans": [
    {
      "span": "A key continuous text segment extracted exactly from the original medical question",
      "reason": "Explain why this span is important based on the doctor’s CoT and final answer."
    }
  ],
  "excluded_information": [
    {
      "text": "Optional example of information from the question that was not selected as a key span",
      "reason": "Optional explanation of why it was not a key piece of evidence"
    }
  ]
}

Important notes:
- Every value in "key_spans.span" must be copied verbatim from the original medical question.
- Do not output the doctor’s full CoT.
- Do not generate a new diagnostic reasoning chain. Only extract the key evidence already used by the doctor.
- If the doctor’s CoT conflicts with the final answer, prioritize the final answer when selecting key spans, and mention the inconsistency in "answer_summary".
- Think through the analysis internally, but do not show detailed reasoning. Output only JSON.
"""