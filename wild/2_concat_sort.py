"""Concatenate the two ea/ne evaluation parquet files and sort by n_ne_leak asc."""

from __future__ import annotations

import pandas as pd

INPUT_A = "/group/40047/eiraxyhuang/workspace/fc/DataG/wild/1_eval_200_ea_ne_result.parquet"
INPUT_B = "/group/40047/eiraxyhuang/workspace/fc/DataG/wild/1_eval_ea_ne_result.parquet"
OUTPUT = "/group/40047/eiraxyhuang/workspace/fc/DataG/wild/1_eval_ea_ne_concat_sorted.parquet"


def main() -> None:
    df_a = pd.read_parquet(INPUT_A)
    df_b = pd.read_parquet(INPUT_B)
    print(f"[load] A rows={len(df_a)} cols={df_a.columns.tolist()}")
    print(f"[load] B rows={len(df_b)} cols={df_b.columns.tolist()}")

    df = pd.concat([df_a, df_b], ignore_index=True)
    print(f"[concat] total rows={len(df)}")

    if "n_ne_leak" not in df.columns:
        raise KeyError("merged dataframe missing column 'n_ne_leak'")

    df = df.sort_values(by="n_ne_leak", ascending=True, kind="mergesort").reset_index(drop=True)
    print(
        f"[sort] by n_ne_leak asc; min={int(df['n_ne_leak'].min())} "
        f"max={int(df['n_ne_leak'].max())}"
    )

    df.to_parquet(OUTPUT, index=False)
    print(f"[save] -> {OUTPUT} (rows={len(df)})")


if __name__ == "__main__":
    main()
