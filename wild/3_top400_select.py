"""Select the original rows behind the top-400 (sorted by n_ne_leak asc).

Sources
-------
- Eval-result files (carry n_ne_leak, used for ranking):
    A: 1_eval_ea_ne_result.parquet      <- evaluated from wild_with_priv_query.parquet
    B: 1_eval_200_ea_ne_result.parquet  <- evaluated from wild_200_with_priv_query.parquet

- Original parquet (carry the original schema we want to keep):
    A: wild_with_priv_query.parquet      (192 rows, extra_info.index 0..191)
    B: wild_200_with_priv_query.parquet  (276 rows, extra_info.index 0..275)

We tag each side with a `source` string so that (source, index) is a unique
key across the union. We rank the union of eval rows by `n_ne_leak` ascending
(stable sort), take the first 400, then go back to the originals to fetch the
matching rows. The output preserves the original schema and adds `source`
plus `n_ne_leak` for downstream filtering.
"""

from __future__ import annotations

import os
import pandas as pd

WILD_DIR = "/group/40047/eiraxyhuang/workspace/fc/DataG/wild"

# (eval_result_path, original_path, source_tag)
PAIRS = [
    (
        os.path.join(WILD_DIR, "1_eval_ea_ne_result.parquet"),
        os.path.join(WILD_DIR, "wild_with_priv_query.parquet"),
        "wild",
    ),
    (
        os.path.join(WILD_DIR, "1_eval_200_ea_ne_result.parquet"),
        os.path.join(WILD_DIR, "wild_200_with_priv_query.parquet"),
        "wild_200",
    ),
]

OUTPUT = os.path.join(WILD_DIR, "top400_wild_priv_query.parquet")
TOP_K = 400


def _row_index(extra_info, fallback: int) -> int:
    """Pull `index` from extra_info dict-like; fall back to row position."""
    if extra_info is None:
        return fallback
    try:
        v = extra_info.get("index") if isinstance(extra_info, dict) else extra_info["index"]
    except Exception:
        return fallback
    if v is None:
        return fallback
    try:
        return int(v)
    except Exception:
        return fallback


def main() -> None:
    eval_frames = []
    orig_frames = []

    for eval_path, orig_path, tag in PAIRS:
        ev = pd.read_parquet(eval_path)
        ev = ev.copy()
        ev["source"] = tag
        # Eval files already store `index` (mirrored from extra_info.index).
        if "index" not in ev.columns:
            raise KeyError(f"{eval_path} missing 'index' column")
        ev["index"] = ev["index"].astype(int)
        eval_frames.append(ev[["source", "index", "n_ne_leak"]])
        print(f"[load][eval ] {tag}: {len(ev)} rows from {eval_path}")

        og = pd.read_parquet(orig_path)
        og = og.copy()
        og["source"] = tag
        # Derive an `index` column from extra_info.index so we can join.
        og["index"] = [
            _row_index(og["extra_info"].iloc[i], i) for i in range(len(og))
        ]
        og["index"] = og["index"].astype(int)
        orig_frames.append(og)
        print(f"[load][orig ] {tag}: {len(og)} rows from {orig_path}")

    eval_all = pd.concat(eval_frames, ignore_index=True)
    orig_all = pd.concat(orig_frames, ignore_index=True)
    print(f"[concat] eval rows={len(eval_all)}  orig rows={len(orig_all)}")

    # Sanity: every eval (source,index) must have exactly one match in orig.
    eval_keys = eval_all[["source", "index"]].drop_duplicates()
    orig_keys = orig_all[["source", "index"]].drop_duplicates()
    if len(orig_keys) != len(orig_all):
        dup = orig_all[orig_all.duplicated(["source", "index"], keep=False)]
        raise ValueError(
            f"original parquet has duplicate (source,index) pairs: {len(dup)} rows"
        )
    missing = eval_keys.merge(
        orig_keys, on=["source", "index"], how="left", indicator=True
    )
    missing = missing[missing["_merge"] == "left_only"]
    if len(missing) > 0:
        print(f"[warn] {len(missing)} eval rows have no matching original row")

    # Rank by n_ne_leak asc (stable) and take top-K.
    ranked = eval_all.sort_values(
        by="n_ne_leak", ascending=True, kind="mergesort"
    ).reset_index(drop=True)
    top = ranked.head(TOP_K).copy()
    print(
        f"[rank] keeping top {len(top)} of {len(ranked)} by n_ne_leak asc; "
        f"min={int(top['n_ne_leak'].min())} max={int(top['n_ne_leak'].max())}"
    )

    # Join back to original rows. Use a left join from `top` so we preserve
    # the n_ne_leak ordering of the selection.
    merged = top.merge(orig_all, on=["source", "index"], how="left")
    if merged.isna().any().any():
        n_missing_rows = merged["extra_info"].isna().sum()
        if n_missing_rows:
            print(f"[warn] {n_missing_rows} top rows could not be joined to originals")

    # Reorder columns: original columns first, then bookkeeping ones.
    orig_cols = [c for c in orig_all.columns if c not in ("source", "index")]
    out = merged[orig_cols + ["source", "index", "n_ne_leak"]]

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    out.to_parquet(OUTPUT, index=False)
    print(f"[save] -> {OUTPUT} (rows={len(out)})")
    print(f"[stats] source breakdown:\n{out['source'].value_counts().to_string()}")


if __name__ == "__main__":
    main()
