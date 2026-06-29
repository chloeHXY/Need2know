# -*- coding: utf-8 -*-
"""
Add a `gpt_answer` column to file B by matching `extra_info["question"]`
against the reference parquet file. Overwrites file B in place.

Reference: /group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_gt_ref.parquet
Target B : /group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_step150.parquet
"""

import pandas as pd


REF_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_gt_ref.parquet"
B_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/0_.parquet"


def _get_question(extra_info) -> str:
    """Safely extract `question` field from an extra_info cell."""
    if extra_info is None:
        return ""
    try:
        if isinstance(extra_info, dict):
            v = extra_info.get("question", "")
        else:
            v = extra_info["question"]
    except Exception:
        return ""
    return str(v) if v is not None else ""


def main():
    print(f"[load] reference: {REF_PATH}")
    ref_df = pd.read_parquet(REF_PATH)
    print(f"[load] ref rows={len(ref_df)} cols={ref_df.columns.tolist()}")

    if "gpt_answer" not in ref_df.columns:
        raise KeyError("Reference file does not have 'gpt_answer' column.")
    if "extra_info" not in ref_df.columns:
        raise KeyError("Reference file does not have 'extra_info' column.")

    print(f"[load] target B : {B_PATH}")
    b_df = pd.read_parquet(B_PATH)
    print(f"[load] B rows={len(b_df)} cols={b_df.columns.tolist()}")

    if "extra_info" not in b_df.columns:
        raise KeyError("B file does not have 'extra_info' column.")

    # Build question -> gpt_answer map from reference.
    # On duplicate questions, keep the first non-empty gpt_answer.
    q2a: dict = {}
    dup_count = 0
    for q_raw, ans in zip(ref_df["extra_info"].tolist(), ref_df["gpt_answer"].tolist()):
        q = _get_question(q_raw)
        if not q:
            continue
        if q in q2a:
            dup_count += 1
            # Prefer first non-empty answer; if existing is empty, overwrite.
            if not q2a[q] and ans:
                q2a[q] = ans
            continue
        q2a[q] = ans

    print(f"[map] unique questions in ref={len(q2a)}  duplicates skipped={dup_count}")

    # Match B rows.
    b_questions = [_get_question(x) for x in b_df["extra_info"].tolist()]
    gpt_answers = []
    matched = 0
    missing = 0
    for q in b_questions:
        if q and q in q2a:
            gpt_answers.append(q2a[q])
            matched += 1
        else:
            gpt_answers.append(None)
            missing += 1

    b_df["gpt_answer"] = gpt_answers
    print(f"[match] matched={matched}  missing={missing}  total={len(b_df)}")

    # Overwrite B in place.
    b_df.to_parquet(B_PATH, index=False)
    print(f"[save] overwritten: {B_PATH}")
    print(f"[save] new cols={b_df.columns.tolist()}")


if __name__ == "__main__":
    main()
