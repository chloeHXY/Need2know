"""Inspect parquet schema and a couple of rows to find the right fields."""
from pathlib import Path
import pandas as pd
import json

ROOT = Path(__file__).resolve().parent
df = pd.read_parquet(ROOT / "our_judged.parquet")
print("columns:", list(df.columns))
print("shape:", df.shape)
print("\nFirst row dump:")
row = df.iloc[0].to_dict()
for k, v in row.items():
    s = str(v)
    print(f"  {k}: {s[:300]}{'...' if len(s) > 300 else ''}")

print("\nUnique types in utility_issues across first 5 rows:")
for i in range(min(5, len(df))):
    ui = df.iloc[i].get("utility_issues") if "utility_issues" in df.columns else None
    print(f"  row {i} type={type(ui).__name__} value={str(ui)[:200]}")
