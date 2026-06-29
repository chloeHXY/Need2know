"""
Rewrite the `split` field of every row in the given Parquet file(s) from
"test" to "train".

Handles two layouts transparently:
  1. `split` is a top-level column.
  2. `split` is a key inside the `extra_info` dict-like column.

Usage:
    python change_split.py \
        --input  /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.parquet \
        --output /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.parquet

If --output is omitted, the input file is overwritten in place.
You can pass --input multiple times to process several files.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Change the `split` field from "test" to "train" in a Parquet file.'
    )
    parser.add_argument(
        "--input", "-i", action="append", required=True,
        help="Path to an input Parquet file. Can be given multiple times.",
    )
    parser.add_argument(
        "--output", "-o", action="append", default=None,
        help="Path to the output Parquet file (matches --input order). "
             "If omitted, each input file is overwritten in place.",
    )
    parser.add_argument(
        "--extra-info-field", default="extra_info",
        help="Name of the column containing the dict-like object (default: extra_info).",
    )
    parser.add_argument(
        "--split-key", default="split",
        help="Name of the split column / key (default: split).",
    )
    parser.add_argument(
        "--from-value", default="test",
        help="Original split value to replace (default: test).",
    )
    parser.add_argument(
        "--to-value", default="train",
        help="New split value to assign (default: train).",
    )
    return parser.parse_args()


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


def process_one(
    input_path: Path,
    output_path: Path,
    extra_info_field: str,
    split_key: str,
    from_value: str,
    to_value: str,
) -> None:
    print(f"Loading parquet: {input_path}", file=sys.stderr)
    df = pd.read_parquet(input_path)
    print(f"  rows={len(df)}, columns={df.columns.tolist()}", file=sys.stderr)

    changed = 0
    handled = False

    # Case 1: top-level `split` column.
    if split_key in df.columns:
        mask = df[split_key] == from_value
        changed = int(mask.sum())
        df.loc[mask, split_key] = to_value
        handled = True
        print(f"  top-level '{split_key}' column: changed {changed} rows "
              f"from '{from_value}' to '{to_value}'.", file=sys.stderr)

    # Case 2: `split` nested under extra_info dict.
    if not handled and extra_info_field in df.columns:
        new_col = []
        for extra_info in df[extra_info_field].tolist():
            d = to_mutable_dict(extra_info)
            if d.get(split_key) == from_value:
                d[split_key] = to_value
                changed += 1
            new_col.append(d)
        df[extra_info_field] = new_col
        handled = True
        print(f"  nested '{extra_info_field}.{split_key}': changed {changed} rows "
              f"from '{from_value}' to '{to_value}'.", file=sys.stderr)

    if not handled:
        print(f"[ERROR] Neither '{split_key}' column nor '{extra_info_field}' "
              f"column found in {input_path}.", file=sys.stderr)
        sys.exit(2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing parquet: {output_path}", file=sys.stderr)
    df.to_parquet(output_path, index=False)
    print("Saved.\n", file=sys.stderr)


def main() -> None:
    args = parse_args()
    inputs = [Path(p) for p in args.input]
    if args.output:
        if len(args.output) != len(inputs):
            print("[ERROR] --output count must match --input count.", file=sys.stderr)
            sys.exit(1)
        outputs = [Path(p) for p in args.output]
    else:
        outputs = inputs  # in-place overwrite

    for in_path, out_path in zip(inputs, outputs):
        if not in_path.is_file():
            print(f"[ERROR] input file not found: {in_path}", file=sys.stderr)
            sys.exit(1)
        process_one(
            input_path=in_path,
            output_path=out_path,
            extra_info_field=args.extra_info_field,
            split_key=args.split_key,
            from_value=args.from_value,
            to_value=args.to_value,
        )


if __name__ == "__main__":
    main()
