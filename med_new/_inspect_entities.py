"""Sample raw `text` values for DATE_TIME and LOCATION to design filter rules."""

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.parquet"


def to_dict(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    try:
        return dict(obj)
    except Exception:
        return {}


def main():
    df = pd.read_parquet(PATH)
    dt_counter: Counter = Counter()
    loc_counter: Counter = Counter()
    for ei in df["extra_info"].tolist():
        d = to_dict(ei)
        ents = d.get("question_pii_entities")
        if ents is None:
            continue
        for e in list(ents):
            ed = to_dict(e)
            et = ed.get("entity_type")
            tx = ed.get("text", "")
            if et == "DATE_TIME":
                dt_counter[str(tx).strip()] += 1
            elif et == "LOCATION":
                loc_counter[str(tx).strip()] += 1

    print("=== DATE_TIME unique texts (top 80) ===")
    for t, c in dt_counter.most_common(80):
        print(f"  {c:4d}  {t!r}")
    print(f"  total unique DATE_TIME texts: {len(dt_counter)}")

    print("\n=== LOCATION unique texts (top 80) ===")
    for t, c in loc_counter.most_common(80):
        print(f"  {c:4d}  {t!r}")
    print(f"  total unique LOCATION texts: {len(loc_counter)}")


if __name__ == "__main__":
    main()
