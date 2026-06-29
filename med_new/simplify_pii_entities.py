"""
Simplify `extra_info["question_pii_entities"]` of a Parquet file.

Replace each entity dict (with fields like `text`, `entity_type`,
`start`, `end`, ...) by just its `text` string, so the field becomes
a plain list[str].

Usage:
    python simplify_pii_entities.py \
        --input  /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_answer_label.parquet \
        --output /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_answer_label.parquet
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm


DEFAULT_INPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/"
    "med.anonymized.cleaned.with_answer_label.parquet"
)
DEFAULT_OUTPUT = DEFAULT_INPUT  # in-place by default

EXTRA_INFO_FIELD = "extra_info"
ENTITIES_KEY = "question_pii_entities"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Simplify question_pii_entities to a list of text strings."
    )
    p.add_argument("--input", "-i", default=DEFAULT_INPUT)
    p.add_argument("--output", "-o", default=DEFAULT_OUTPUT)
    return p.parse_args()


def to_mutable_dict(obj) -> dict:
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


def entity_text(e) -> str | None:
    """Extract the `text` field from an entity-like object."""
    if e is None:
        return None
    if isinstance(e, str):
        return e
    if isinstance(e, dict):
        t = e.get("text")
        return None if t is None else str(t)
    # numpy struct / record-like fallback
    try:
        d = dict(e)
        t = d.get("text")
        return None if t is None else str(t)
    except Exception:
        pass
    try:
        t = getattr(e, "text", None)
        return None if t is None else str(t)
    except Exception:
        return None


def simplify_entities(entities) -> list[str]:
    if entities is None:
        return []
    try:
        ents = list(entities)
    except Exception:
        return []
    out: list[str] = []
    for e in ents:
        t = entity_text(e)
        if t is not None:
            out.append(t)
    return out


def process(input_path: Path, output_path: Path) -> None:
    print(f"Loading parquet: {input_path}", file=sys.stderr)
    df = pd.read_parquet(input_path)
    print(f"  rows={len(df)}", file=sys.stderr)
    if EXTRA_INFO_FIELD not in df.columns:
        print(f"[ERROR] '{EXTRA_INFO_FIELD}' column not found.", file=sys.stderr)
        sys.exit(2)

    new_col: list[dict] = []
    total_before = 0
    total_after = 0
    rows_with_pii = 0

    for ei in tqdm(df[EXTRA_INFO_FIELD].tolist(), desc="Simplifying entities"):
        d = to_mutable_dict(ei)
        ents = d.get(ENTITIES_KEY)
        try:
            total_before += 0 if ents is None else len(list(ents))
        except Exception:
            pass
        texts = simplify_entities(ents)
        total_after += len(texts)
        if texts:
            rows_with_pii += 1
        d[ENTITIES_KEY] = texts
        new_col.append(d)

    df[EXTRA_INFO_FIELD] = new_col

    print(
        f"Done. entities before={total_before}, kept_texts={total_after}; "
        f"rows_with_pii={rows_with_pii}/{len(df)}",
        file=sys.stderr,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing parquet: {output_path}", file=sys.stderr)
    df.to_parquet(output_path, index=False)
    print("Saved.", file=sys.stderr)


def main() -> None:
    args = parse_args()
    in_path = Path(args.input)
    out_path = Path(args.output)
    if not in_path.is_file():
        print(f"[ERROR] input not found: {in_path}", file=sys.stderr)
        sys.exit(1)
    process(in_path, out_path)


if __name__ == "__main__":
    main()
