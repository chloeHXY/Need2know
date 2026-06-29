# -*- coding: utf-8 -*-
"""
Step 4: Evaluation for the medical single-choice (MCQ) task.

Inputs:
    Parquet from Step 3 (merge_inference.py):
        /group/40047/eiraxyhuang/workspace/fc/DataG/our_med/med_with_merge_inference.parquet

Required columns:
    - `merge_inference_answer`: model prediction (ideally a single uppercase
      letter such as "A" / "B" / "C" / "D"; falls back to robust parsing).
    - `reward_model`: dict with key `ground_truth`, e.g.
        {'style': 'rule', 'ground_truth': 'The correct answer is C. abce.'}
    - `extra_info` (optional): used to print diagnostic samples.

What it does:
    1. Extract the predicted letter from `merge_inference_answer`.
    2. Extract the gold letter from `reward_model['ground_truth']`.
    3. Compute accuracy = #correct / #total.
    4. Print a small breakdown (#parsed, #unparsable, #errors) and a few samples.
    5. Save per-row results to a parquet file.

Usage:
    python eval.py
    python eval.py --input /path/to/med_with_merge_inference.parquet \
                   --output /path/to/eval_result.parquet
"""

import os
import re
import argparse
import pandas as pd


# =============================================================================
# I/O configuration
# =============================================================================
INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/our_med/med_with_merge_inference.parquet"
OUTPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/our_med/eval_result.parquet"

PRED_COL = "merge_inference_answer"
REWARD_COL = "reward_model"
EXTRA_COL = "extra_info"


# =============================================================================
# Parsing helpers
# =============================================================================
# Match patterns like:
#   "C"
#   "Answer: C"
#   "The correct answer is C."
#   "C. abce"
#   "(C)"
# We only support letters A-Z (case-insensitive); for typical 4-option MCQs
# this means A/B/C/D, but is robust to more options.
_LETTER_TOKEN_RE = re.compile(r"\b([A-Z])\b")
_PAREN_LETTER_RE = re.compile(r"\(\s*([A-Za-z])\s*\)")
_LETTER_DOT_RE = re.compile(r"\b([A-Za-z])\s*[\.\):,]")
_ANSWER_IS_RE = re.compile(
    r"(?:correct\s+answer\s+is|answer\s*[:\-]|the\s+answer\s+is)\s*\(?\s*([A-Za-z])",
    re.IGNORECASE,
)


def extract_letter(text) -> str:
    """Extract a single option letter (uppercase) from a free-form string.

    Returns "" if no plausible letter can be found.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    s = text.strip()
    if not s:
        return ""

    # Strip wrapping quotes / backticks / asterisks
    s_stripped = s.strip(" \t\r\n\"'`*")

    # 1) Already a single letter (e.g. "C" or "c")
    if len(s_stripped) == 1 and s_stripped.isalpha():
        return s_stripped.upper()

    # 2) "The correct answer is C..." / "Answer: C"
    m = _ANSWER_IS_RE.search(s_stripped)
    if m:
        return m.group(1).upper()

    # 3) "(C)" form
    m = _PAREN_LETTER_RE.search(s_stripped)
    if m:
        return m.group(1).upper()

    # 4) "C." / "C)" / "C," at the start
    head = s_stripped[:6]  # only look at the head to avoid grabbing options inside text
    m = _LETTER_DOT_RE.match(head)
    if m:
        return m.group(1).upper()

    # 5) Fallback: first standalone uppercase letter token
    m = _LETTER_TOKEN_RE.search(s_stripped.upper())
    if m:
        return m.group(1).upper()

    return ""


def extract_gold_letter(reward_model) -> str:
    """Extract the gold option letter from reward_model['ground_truth'].

    Note: ground_truth here may be either a short canonical sentence (e.g.
    "The correct answer is C. abce.") OR a long free-form explanation that
    finally states the option (e.g. "Based on the details ... \\n\\nB. Borderline").
    The naive extractor `extract_letter` is unsafe on the latter form because
    it would happily return the first standalone capital letter it sees
    (e.g. the "S" in "Symptoms ..."). So we apply a stricter, gold-specific
    parser here, only falling back to the loose extractor as a last resort.
    """
    if reward_model is None:
        return ""
    gt = None
    if isinstance(reward_model, dict):
        gt = reward_model.get("ground_truth", "")
    else:
        try:
            gt = reward_model["ground_truth"]
        except Exception:
            gt = None
    if not gt or not isinstance(gt, str):
        return ""

    # 1) "The correct answer is X" / "answer: X" / "the answer is X"
    m = re.search(
        r"(?:correct\s+answer\s+is|answer\s*[:\-]|the\s+answer\s+is)\s*\(?\s*([A-Da-d])\b",
        gt,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).upper()

    # 2) A line that *starts* with "X." / "(X)" / "X)" followed by option text.
    #    This handles cases like "...\n\nB. Borderline Personality Disorder".
    for line in gt.splitlines():
        line = line.strip(" *`'\"")
        m = re.match(r"\(?([A-Da-d])\)?[\.\):,]\s+\S", line)
        if m:
            return m.group(1).upper()

    # 3) Last-resort fallback: the previous loose extractor.
    return extract_letter(gt)


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Evaluate accuracy for medical MCQ.")
    parser.add_argument("--input", default=INPUT_PATH, help="Input parquet path")
    parser.add_argument("--output", default=OUTPUT_PATH, help="Output parquet path")
    parser.add_argument("--samples", type=int, default=5,
                        help="Number of mismatched samples to print (default 5)")
    args = parser.parse_args()

    print(f"[load] reading parquet: {args.input}")
    df = pd.read_parquet(args.input)
    print(f"[load] rows={len(df)} columns={df.columns.tolist()}")

    if PRED_COL not in df.columns:
        raise KeyError(f"Missing required column: {PRED_COL}")
    if REWARD_COL not in df.columns:
        raise KeyError(f"Missing required column: {REWARD_COL}")

    preds_raw = df[PRED_COL].tolist()
    rewards = df[REWARD_COL].tolist()
    extras = df[EXTRA_COL].tolist() if EXTRA_COL in df.columns else [None] * len(df)

    n = len(df)
    pred_letters = [None] * n
    gold_letters = [None] * n
    correct_flags = [None] * n
    is_error = [False] * n
    is_unparsable = [False] * n

    n_error = 0
    n_unparsable_pred = 0
    n_unparsable_gold = 0
    n_correct = 0
    n_evaluated = 0

    for i in range(n):
        raw = preds_raw[i]
        # Inference-time errors are surfaced as "[ERROR] ..." strings in Step 3.
        if isinstance(raw, str) and raw.startswith("[ERROR]"):
            is_error[i] = True
            n_error += 1
            pred_letters[i] = ""
        else:
            pred_letters[i] = extract_letter(raw)

        gold_letters[i] = extract_gold_letter(rewards[i])

        if not pred_letters[i] and not is_error[i]:
            is_unparsable[i] = True
            n_unparsable_pred += 1

        if not gold_letters[i]:
            n_unparsable_gold += 1

        # Count toward accuracy only when both sides are parseable and pred is not an error.
        if pred_letters[i] and gold_letters[i] and not is_error[i]:
            n_evaluated += 1
            if pred_letters[i] == gold_letters[i]:
                correct_flags[i] = 1
                n_correct += 1
            else:
                correct_flags[i] = 0
        else:
            correct_flags[i] = 0  # treat unparseable / error as incorrect

    # =============================================================================
    # Reporting
    # =============================================================================
    # Strict accuracy: numerator = correct, denominator = all rows
    # (errors / unparsable predictions count as wrong).
    acc_strict = n_correct / n if n > 0 else 0.0
    # Lenient accuracy: only over rows with parseable gold + non-error predictions
    # (still counts unparsable predictions as wrong, but excludes rows w/ no gold).
    n_with_gold = sum(1 for g in gold_letters if g)
    acc_with_gold = n_correct / n_with_gold if n_with_gold > 0 else 0.0
    # Pure-pred accuracy: only over rows where both pred and gold are parseable.
    acc_parsed = n_correct / n_evaluated if n_evaluated > 0 else 0.0

    print("\n=== Result ===")
    print(f"total rows                : {n}")
    print(f"inference errors          : {n_error}")
    print(f"unparsable predictions    : {n_unparsable_pred}")
    print(f"unparsable ground truths  : {n_unparsable_gold}")
    print(f"correct                   : {n_correct}")
    print(f"accuracy (strict, /total) : {acc_strict:.4f}")
    print(f"accuracy (rows w/ gold)   : {acc_with_gold:.4f}")
    print(f"accuracy (both parsed)    : {acc_parsed:.4f}  [n={n_evaluated}]")

    # Print a few mismatched samples for inspection
    if args.samples > 0:
        shown = 0
        print("\n--- Mismatch samples ---")
        for i in range(n):
            if shown >= args.samples:
                break
            if correct_flags[i] == 1:
                continue
            q = ""
            if isinstance(extras[i], dict):
                q = extras[i].get("question", "") or ""
            raw_pred = preds_raw[i] if isinstance(preds_raw[i], str) else str(preds_raw[i])
            print(f"\n[idx={i}] pred='{pred_letters[i]}' gold='{gold_letters[i]}' "
                  f"error={is_error[i]} unparsable={is_unparsable[i]}")
            print(f"  question  : {q[:200]}")
            print(f"  raw_pred  : {raw_pred[:200]}{'...' if len(raw_pred) > 200 else ''}")
            shown += 1

    # =============================================================================
    # Persist per-row results
    # =============================================================================
    out_df = pd.DataFrame({
        "pred_raw": [str(x) if x is not None else "" for x in preds_raw],
        "pred_letter": pred_letters,
        "gold_letter": gold_letters,
        "is_error": is_error,
        "is_unparsable": is_unparsable,
        "correct": correct_flags,
    })
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    out_df.to_parquet(args.output, index=False)
    print(f"\n[save] wrote per-row eval results to: {args.output}")


if __name__ == "__main__":
    main()
