"""
对/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_answer_label.parquet 进行处理

1. extra_info.question_pii_entities 更名为 ne
2. extra_info.key_spans            更名为 key_spans
3. extra_info.answer 用extra_info.query_gt替代
4. 将数据集划分为 训练集 350 条 / 测试集 150 条 (写入 extra_info.split)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ----------------------------- paths / constants ----------------------------- #

BASE_DIR = Path("/group/40047/eiraxyhuang/workspace/fc/DataG/med_new")

INPUT_PATH = BASE_DIR / "med.anonymized.cleaned.with_answer_label.parquet"
OUTPUT_PATH = BASE_DIR / "med.final.parquet"
TRAIN_PATH = BASE_DIR / "med.final.train.parquet"
TEST_PATH = BASE_DIR / "med.final.test.parquet"

EXTRA_INFO_FIELD = "extra_info"

# rename map: old_key -> new_key
RENAME_MAP = {
    "question_pii_entities": "ne",
    "key_spans": "key_spans",
}

# replace map: target_key <- source_key (source value overwrites target)
REPLACE_MAP = {
    "answer": "query_gt",
}

TRAIN_SIZE = 350
TEST_SIZE = 150
TOTAL_EXPECTED = TRAIN_SIZE + TEST_SIZE
RANDOM_SEED = 42


# ------------------------------- helpers ------------------------------- #

def to_mutable_dict(obj) -> dict:
    """Normalize a dict-like object (possibly numpy/pandas wrapped) to a plain dict."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    if isinstance(obj, np.ndarray):
        try:
            return dict(obj.tolist())
        except Exception:
            pass
    try:
        return dict(obj)
    except Exception:
        return {}


def transform_extra_info(extra_info) -> dict:
    """Apply rename / replace operations on a single extra_info dict."""
    d = to_mutable_dict(extra_info)

    # 1 & 2. rename keys (preserve insertion order roughly)
    for old_key, new_key in RENAME_MAP.items():
        if old_key in d:
            d[new_key] = d.pop(old_key)

    # 3. replace target value with source value (source kept as-is too)
    for target_key, source_key in REPLACE_MAP.items():
        if source_key in d:
            d[target_key] = d[source_key]

    # 4. add an empty `origin_ea` field for every record
    d["origin_ea"] = []

    return d


def assign_splits(n: int, train_size: int, test_size: int, seed: int) -> np.ndarray:
    """Return an array of length n with values 'train'/'test'."""
    if n != train_size + test_size:
        print(
            f"[WARN] dataset size ({n}) != train({train_size}) + test({test_size}) "
            f"= {train_size + test_size}. Using min sizes that fit.",
            file=sys.stderr,
        )
    rng = np.random.default_rng(seed)
    indices = np.arange(n)
    rng.shuffle(indices)

    splits = np.empty(n, dtype=object)
    test_n = min(test_size, n)
    train_n = min(train_size, n - test_n)

    test_idx = indices[:test_n]
    train_idx = indices[test_n : test_n + train_n]

    splits[:] = "train"  # default; will be overwritten for chosen indices
    splits[test_idx] = "test"
    splits[train_idx] = "train"
    # any leftover (if n > train+test) keeps default 'train'
    return splits


# ---------------------------------- main ---------------------------------- #

def main() -> None:
    if not INPUT_PATH.is_file():
        print(f"[ERROR] input not found: {INPUT_PATH}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading parquet: {INPUT_PATH}", file=sys.stderr)
    df = pd.read_parquet(INPUT_PATH)
    n = len(df)
    print(f"  rows={n}, columns={df.columns.tolist()}", file=sys.stderr)

    if EXTRA_INFO_FIELD not in df.columns:
        print(f"[ERROR] '{EXTRA_INFO_FIELD}' column not found.", file=sys.stderr)
        sys.exit(2)

    # --- step 1-3: transform extra_info ---
    transformed: list[dict] = [
        transform_extra_info(ei) for ei in df[EXTRA_INFO_FIELD].tolist()
    ]

    # --- step 4: assign splits ---
    splits = assign_splits(n, TRAIN_SIZE, TEST_SIZE, RANDOM_SEED)
    for d, s in zip(transformed, splits):
        d["split"] = str(s)

    df[EXTRA_INFO_FIELD] = transformed

    # also expose split as top-level column (helps downstream filtering),
    # but only if it isn't already a column.
    if "split" not in df.columns:
        df["split"] = splits
    else:
        df["split"] = splits  # overwrite to keep consistent

    train_count = int((df["split"] == "train").sum())
    test_count = int((df["split"] == "test").sum())
    print(f"  split: train={train_count}, test={test_count}", file=sys.stderr)

    # --- write outputs ---
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing full parquet: {OUTPUT_PATH}", file=sys.stderr)
    df.to_parquet(OUTPUT_PATH, index=False)

    print(f"Writing train parquet: {TRAIN_PATH}", file=sys.stderr)
    df[df["split"] == "train"].reset_index(drop=True).to_parquet(TRAIN_PATH, index=False)

    print(f"Writing test parquet: {TEST_PATH}", file=sys.stderr)
    df[df["split"] == "test"].reset_index(drop=True).to_parquet(TEST_PATH, index=False)

    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()