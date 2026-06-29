"""
Process two parquet files into a single shuffled jsonl.

Field mapping:
- question: extra_info["question"]
- essential_spans: extra_info["ea"] + extra_info["key_spans"] + extra_info["origin_ea"]
- non_essential_spans: extra_info["ne"]
- gold_reformulation: reward_model["ground_truth"]
- essential_policy: extra_info["essential_policy"]
- data_source: mapped from row["ability"] via DATA_SOURCE_MAP
- split: "train" for train.parquet, "test" for 0_.parquet
"""

import json
import os
import random

import pandas as pd

DATA_DIR = "/group/40047/eiraxyhuang/workspace/fc/DataG/update_data"
TRAIN_PARQUET = os.path.join(DATA_DIR, "train.parquet")
TEST_PARQUET = os.path.join(DATA_DIR, "0_.parquet")
OUTPUT_JSONL = os.path.join(DATA_DIR, "data.jsonl")
SEED = 42

# Map raw `ability` value -> output `data_source` value.
# Unmapped values fall through unchanged.
DATA_SOURCE_MAP = {
    "privacy": "general_synthesis",
    "wild": "general_wild",
}


def to_list(value):
    """Normalize ndarray / list / None / scalar into a list of items."""
    if value is None:
        return []
    # numpy ndarray
    if hasattr(value, "tolist"):
        try:
            value = value.tolist()
        except Exception:
            pass
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    # scalar -> wrap
    return [value]


def build_record(row, split):
    extra = row["extra_info"] or {}
    reward = row["reward_model"] or {}

    ea = to_list(extra.get("ea"))
    key_spans = to_list(extra.get("key_spans"))
    origin_ea = to_list(extra.get("origin_ea"))
    essential_spans = list(ea) + list(key_spans) + list(origin_ea)

    non_essential_spans = to_list(extra.get("ne"))

    ability = row.get("ability")
    data_source = DATA_SOURCE_MAP.get(ability, ability)

    record = {
        "question": extra.get("question"),
        "essential_spans": essential_spans,
        "non_essential_spans": non_essential_spans,
        "gold_reformulation": reward.get("ground_truth"),
        "essential_policy": extra.get("essential_policy"),
        "data_source": data_source,
        "split": split,
    }
    return record


def load_records(parquet_path, split):
    df = pd.read_parquet(parquet_path)
    records = []
    for _, row in df.iterrows():
        records.append(build_record(row, split))
    return records


def main():
    train_records = load_records(TRAIN_PARQUET, "train")
    test_records = load_records(TEST_PARQUET, "test")

    print(f"train records: {len(train_records)}")
    print(f"test records: {len(test_records)}")

    all_records = train_records + test_records
    rng = random.Random(SEED)
    rng.shuffle(all_records)

    print(f"total records: {len(all_records)}")

    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"written -> {OUTPUT_JSONL}")


if __name__ == "__main__":
    main()
