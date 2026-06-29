"""
Overwrite the `priv_query` column with the values from `question_anonymized`.

Input : /group/40047/eiraxyhuang/workspace/fc/DataG/prediax/0_.parquet
Output: /group/40047/eiraxyhuang/workspace/fc/DataG/prediax/5_.parquet
"""

import sys
from pathlib import Path

import pandas as pd


INPUT_PATH = Path(
    "/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/0_.parquet"
)
OUTPUT_PATH = Path(
    "/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/5_.parquet"
)

SRC_COL = "question_anonymized"
DST_COL = "priv_query"


def main() -> None:
    print(f"Loading parquet: {INPUT_PATH}", file=sys.stderr)
    df = pd.read_parquet(INPUT_PATH)
    print(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}", file=sys.stderr)

    if SRC_COL not in df.columns:
        print(f"[ERROR] source column '{SRC_COL}' not found.", file=sys.stderr)
        sys.exit(2)
    if DST_COL not in df.columns:
        print(f"[WARN] destination column '{DST_COL}' not found; it will be created.",
              file=sys.stderr)

    # Overwrite priv_query with question_anonymized values
    df[DST_COL] = df[SRC_COL]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing parquet: {OUTPUT_PATH}", file=sys.stderr)
    df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Saved. Rows: {len(df)}, Columns: {df.columns.tolist()}", file=sys.stderr)


if __name__ == "__main__":
    main()
