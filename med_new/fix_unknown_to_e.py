"""
Replace every extra_info['answer_label'] == 'UNKNOWN' with 'E' in the labeled
parquet, and overwrite the file in place.
"""

import copy
from collections import Counter

import pandas as pd

PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_answer_label.parquet"


def main():
    print(f"Loading: {PATH}")
    df = pd.read_parquet(PATH)
    print(f"Loaded {len(df)} rows.")

    before = Counter()
    after = Counter()
    changed = 0

    new_extra_infos = []
    for ei in df["extra_info"].tolist():
        if isinstance(ei, dict):
            new_ei = copy.deepcopy(ei)
        elif ei is None:
            new_ei = {}
        else:
            try:
                new_ei = dict(ei)
            except Exception:
                new_ei = {"_original_extra_info": ei}

        label = new_ei.get("answer_label")
        before[label] += 1

        if label == "UNKNOWN":
            new_ei["answer_label"] = "E"
            changed += 1

        after[new_ei.get("answer_label")] += 1
        new_extra_infos.append(new_ei)

    df["extra_info"] = new_extra_infos

    print(f"Changed {changed} rows: UNKNOWN -> E")
    print(f"Before: {dict(before)}")
    print(f"After:  {dict(after)}")

    print(f"Writing back: {PATH}")
    df.to_parquet(PATH, index=False)
    print("Saved.")


if __name__ == "__main__":
    main()
