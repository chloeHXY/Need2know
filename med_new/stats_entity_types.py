"""Quick stats: list all `entity_type` values found in
extra_info["question_pii_entities"] of a Parquet file, with counts.
"""

import sys
from collections import Counter
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.parquet"
EXTRA_INFO_FIELD = "extra_info"
ENTITIES_KEY = "question_pii_entities"


def to_dict(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    try:
        return dict(obj)
    except Exception:
        return {}


def main(path: str = DEFAULT_INPUT) -> None:
    p = Path(path)
    if not p.is_file():
        print(f"[ERROR] not found: {p}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_parquet(p)
    print(f"rows={len(df)}, columns={df.columns.tolist()}", file=sys.stderr)

    type_counter: Counter = Counter()
    rows_with_pii = 0
    total_entities = 0

    if EXTRA_INFO_FIELD not in df.columns:
        print(f"[ERROR] '{EXTRA_INFO_FIELD}' column missing", file=sys.stderr)
        sys.exit(2)

    for extra_info in df[EXTRA_INFO_FIELD].tolist():
        d = to_dict(extra_info)
        ents = d.get(ENTITIES_KEY)
        # ents may be a numpy array / list / None
        if ents is None:
            ents = []
        else:
            try:
                ents = list(ents)
            except Exception:
                ents = []
        if len(ents) > 0:
            rows_with_pii += 1
        for e in ents:
            ed = to_dict(e)
            et = ed.get("entity_type")
            if et is not None:
                type_counter[str(et)] += 1
                total_entities += 1

    print(f"\nrows_with_pii: {rows_with_pii}")
    print(f"total_entities: {total_entities}")
    print(f"unique_entity_types: {len(type_counter)}")
    print("\nentity_type counts (desc):")
    for et, cnt in type_counter.most_common():
        print(f"  {et}\t{cnt}")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    main(arg)
