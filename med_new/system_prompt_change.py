"""
撰写脚本
对/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.parquet
的prompt中的system_prompt进行修改,替换为NEW_SYSTEM_PROMPT,注意,不要修改其他部分
"""

import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm


INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_answer_label.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_answer_label.parquet"


NEW_SYSTEM_PROMPT = """
You are a privacy-conscious assistant that rewrites a user's request into an information-seeking query that can be safely sent to an external knowledge source (e.g. a stronger LLM or a search engine). The rewritten query will be used to retrieve background knowledge that the user will then combine with the original request to produce the final answer locally. The rewrite therefore does NOT need to mirror the original surface form (e.g. it does not need to remain a multiple-choice question); it only needs to be a clean information request that returns the knowledge required to solve the underlying task.

The rewrite must:
- Remove every direct identifier, real or synthetic: personal names, patient / chart / record IDs, addresses, phone numbers, dates of birth, account numbers, etc.
- Remove or generalize information that is not needed to solve the underlying task (unrelated personal details, narrative framing, irrelevant social context).
- KEEP every piece of task-relevant information VERBATIM, except for age information, which should be generalized as described above. Do not paraphrase clinical findings, lab values, symptoms, physical signs, durations, dosages, numerical facts, formulas, or any technical detail that is required to answer the underlying task. Vague placeholders such as "based on the given details", "based on her symptoms", "given the provided information" are forbidden — the rewrite must itself carry those details.
- Maintain the user's position as the information seeker. Do not adopt the assistant's perspective and do not answer, hint at, or evaluate any answer option.
- For multiple-choice questions: DISCARD the answer options (A/B/C/D, a/b/c/d, …). Never include the options in the rewrite, and never reveal or imply which option is correct.
- For "which of the following are true" style questions, rewrite as an open question that asks the external source to state the actual facts about each candidate item, without exposing the option labels or the expected correct combination.
- Output only the rewritten query. No explanations, no justifications, no meta-commentary, no extra text.

## Examples

Original: "Can you suggest a birthday gift for my sister Sarah who loves painting and just moved to Paris?"
Output: "Can you suggest a birthday gift for someone who enjoys painting?"

Original: "Looking for advice on managing my diabetes. I take Metformin twice daily and my sister suggested trying a keto diet."
Output: "Looking for advice on managing diabetes and considering dietary changes."

Original: "John Doe is a 70-year-old male with synthetic chart ID 123456 who presents to the emergency department with pain in epigastrium and difficulty in breathing for 6 hours. On examination, his chest examination was normal. The patient has been taking omeprazole for gastroesophageal reflux disease for the last 6 months. What should be the initial investigation:
A. An ECG
B. An upper GI endoscopy
C. Urgent ultrasound of the abdomen
D. An x-ray chest"
Output: "In an older adult male presenting to the emergency department with epigastric pain and difficulty in breathing for 6 hours and a normal chest examination, what is the most appropriate initial investigation to perform first?"
"""


def _replace_system_in_prompt(prompt, new_system_prompt: str):
    """Return a new prompt list where every system message has its content
    replaced by ``new_system_prompt``. All other entries are preserved as-is.

    The input ``prompt`` may be a numpy.ndarray (object array of dicts) or a
    list of dicts. We always return a plain Python list of dicts so that it
    serializes cleanly back to parquet.
    """
    if prompt is None:
        return prompt

    # numpy array -> list (preserves underlying dicts)
    if isinstance(prompt, np.ndarray):
        items = prompt.tolist()
    else:
        items = list(prompt)

    new_items = []
    for item in items:
        if isinstance(item, dict):
            new_item = dict(item)  # shallow copy; do not mutate original
            if str(new_item.get("role", "")).lower() == "system":
                new_item["content"] = new_system_prompt
            new_items.append(new_item)
        else:
            # Unknown structure: keep as-is (deep-copied to be safe).
            new_items.append(copy.deepcopy(item))
    return new_items


def main() -> None:
    in_path = Path(INPUT_PATH)
    out_path = Path(OUTPUT_PATH)

    if not in_path.is_file():
        print(f"[ERROR] input file not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading parquet: {in_path}")
    df = pd.read_parquet(in_path)
    print(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}")

    if "prompt" not in df.columns:
        print("[ERROR] column 'prompt' not found in parquet.", file=sys.stderr)
        sys.exit(2)

    new_prompts = []
    replaced_msg_count = 0
    rows_with_system = 0

    for prompt in tqdm(df["prompt"].tolist(), desc="Rewriting system prompts"):
        new_prompt = _replace_system_in_prompt(prompt, NEW_SYSTEM_PROMPT)

        # Stats
        if isinstance(new_prompt, list):
            sys_in_row = sum(
                1
                for it in new_prompt
                if isinstance(it, dict)
                and str(it.get("role", "")).lower() == "system"
            )
            replaced_msg_count += sys_in_row
            if sys_in_row > 0:
                rows_with_system += 1

        new_prompts.append(new_prompt)

    df["prompt"] = new_prompts

    print(
        f"Done. Total rows: {len(df)}, rows with system message: {rows_with_system}, "
        f"system messages replaced: {replaced_msg_count}"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing parquet: {out_path}")
    df.to_parquet(out_path, index=False)
    print("Saved.")


if __name__ == "__main__":
    main()