#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert a Parquet file to JSONL (JSON Lines).

Usage:
    python parquet_to_jsonl.py <input.parquet> [-o <output.jsonl>]
                               [--orient records] [--batch-size 1000]
                               [--no-ensure-ascii] [--columns col1,col2]

Examples:
    python parquet_to_jsonl.py med.anonymized.cleaned.parquet
    python parquet_to_jsonl.py med.anonymized.cleaned.parquet -o out.jsonl
    python parquet_to_jsonl.py data.parquet --columns id,text,label
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, date, time
from decimal import Decimal

import numpy as np
import pyarrow.parquet as pq


def _default_serializer(obj):
    """Fallback JSON serializer for objects not natively supported."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        # Convert NaN/Inf to None to keep JSONL strictly valid
        f = float(obj)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            return obj.hex()
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _clean_value(v):
    """Recursively clean values: convert NaN/NaT to None, numpy -> python."""
    if v is None:
        return None
    # Pandas NaT or numpy NaN
    if isinstance(v, float):
        if v != v:  # NaN
            return None
        return v
    if isinstance(v, np.floating):
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.ndarray):
        return [_clean_value(x) for x in v.tolist()]
    if isinstance(v, list):
        return [_clean_value(x) for x in v]
    if isinstance(v, tuple):
        return [_clean_value(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _clean_value(val) for k, val in v.items()}
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return v.hex()
    return v


def parquet_to_jsonl(
    input_path: str,
    output_path: str = None,
    batch_size: int = 1000,
    ensure_ascii: bool = False,
    columns=None,
):
    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Input parquet file not found: {in_path}")

    if output_path is None:
        output_path = str(in_path.with_suffix(".jsonl"))
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pf = pq.ParquetFile(str(in_path))
    schema_names = [f.name for f in pf.schema_arrow]
    if columns:
        missing = [c for c in columns if c not in schema_names]
        if missing:
            raise ValueError(
                f"Columns not found in parquet: {missing}. Available: {schema_names}"
            )
        read_columns = columns
    else:
        read_columns = None

    total = 0
    with out_path.open("w", encoding="utf-8") as fout:
        for batch in pf.iter_batches(batch_size=batch_size, columns=read_columns):
            # to_pylist is the most reliable: it produces native python types
            rows = batch.to_pylist()
            for row in rows:
                cleaned = {k: _clean_value(v) for k, v in row.items()}
                fout.write(
                    json.dumps(
                        cleaned,
                        ensure_ascii=ensure_ascii,
                        default=_default_serializer,
                    )
                )
                fout.write("\n")
                total += 1

    print(f"[OK] {in_path}  ->  {out_path}")
    print(f"     rows: {total}, columns: {read_columns or schema_names}")
    return total


def main():
    parser = argparse.ArgumentParser(
        description="Convert a Parquet file to JSONL (JSON Lines)."
    )
    parser.add_argument("input", help="Input parquet file path")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output jsonl path (default: same name with .jsonl extension)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=1000,
        help="Batch size for streaming read (default: 1000)",
    )
    parser.add_argument(
        "--ensure-ascii", action="store_true",
        help="Escape non-ASCII chars in JSON (default: keep utf-8)",
    )
    parser.add_argument(
        "--columns", default=None,
        help="Comma-separated subset of columns to export (default: all)",
    )
    args = parser.parse_args()

    cols = [c.strip() for c in args.columns.split(",")] if args.columns else None

    parquet_to_jsonl(
        input_path=args.input,
        output_path=args.output,
        batch_size=args.batch_size,
        ensure_ascii=args.ensure_ascii,
        columns=cols,
    )


if __name__ == "__main__":
    main()
