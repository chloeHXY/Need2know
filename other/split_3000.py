"""
Split 3000 rows from train-00000-of-00006.parquet to a new parquet file.
"""
import os
import pandas as pd

SRC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "train-00000-of-00006.parquet")
DST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_subset_3000.parquet")
N = 3000


def main():
    print(f"Reading: {SRC_PATH}")
    df = pd.read_parquet(SRC_PATH)
    print(f"Original rows: {len(df)}, columns: {list(df.columns)}")

    n = min(N, len(df))
    subset = df.head(n)
    subset.to_parquet(DST_PATH, index=False)
    print(f"Saved {len(subset)} rows to: {DST_PATH}")
    print(f"Output file size: {os.path.getsize(DST_PATH) / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    main()
