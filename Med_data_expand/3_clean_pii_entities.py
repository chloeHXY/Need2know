"""
Clean up `extra_info["question_pii_entities"]` of a Parquet file.

Keep ONLY:
  * PERSON              -> all
  * US_DRIVER_LICENSE   -> all
  * US_BANK_NUMBER      -> all
  * DATE_TIME           -> only age-like patterns: e.g. "45-year-old",
                           "3-month-old", "1-week-old", "2-day-old"
  * LOCATION            -> only real place names (whitelist match).
                           If text is prefixed by an MCQ option marker
                           like "A. ", "B. ", "C. ", "D. ", strip the
                           prefix before matching; on hit, the entity's
                           `text` / `start` / `end` are adjusted to point
                           at the place name only.

Everything else (NRP, US_PASSPORT, US_ITIN, URL, PHONE_NUMBER, and any
DATE_TIME / LOCATION not matching the rules above) is dropped.

Usage:
    python clean_pii_entities.py \
        --input  /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.parquet \
        --output /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.parquet
"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm


DEFAULT_INPUT = "/group/40047/eiraxyhuang/workspace/fc/DataG/Med_data_expand/2_.parquet"
DEFAULT_OUTPUT = "/group/40047/eiraxyhuang/workspace/fc/DataG/Med_data_expand/3_.parquet"

EXTRA_INFO_FIELD = "extra_info"
ENTITIES_KEY = "question_pii_entities"

# DATE_TIME age-like pattern: e.g. "45-year-old", "3-month-old",
# "1-week-old", "2-day-old". Hyphen / en-dash both accepted. Case-insensitive.
AGE_PATTERN = re.compile(
    r"^\s*\d+\s*[-\u2013]\s*(year|month|week|day)\s*[-\u2013]\s*old\s*$",
    flags=re.IGNORECASE,
)

# MCQ option prefix: "A. ", "B. ", "C. ", "D. " (also tolerate ")" form).
OPTION_PREFIX = re.compile(r"^([A-Da-d])\s*[\.\)]\s+")

# Whitelist of real place names (case-insensitive exact match after
# stripping any leading article like "the ").
PLACE_WHITELIST = {
    # countries / regions
    "india", "europe", "peru", "colorado", "new hampshire", "singapore",
    "asia", "norway", "nigeria", "usa", "us", "u.s.", "u.s.a.",
    "ancash region", "lima", "dominican republic", "united states",
    "republic of congo", "glasgow", "south america",
    # US state abbreviation codes that appeared in samples
    "wy", "mi",
    # extras that may appear: keep this list extensible
    "africa", "north america", "china", "japan", "germany", "france",
    "italy", "spain", "uk", "united kingdom", "canada", "mexico",
    "brazil", "russia", "australia", "korea", "south korea",
    "north korea", "vietnam", "thailand", "indonesia", "philippines",
    "pakistan", "bangladesh", "sri lanka", "nepal", "afghanistan",
    "iran", "iraq", "egypt", "south africa", "kenya", "ethiopia",
    "tanzania", "uganda", "ghana", "morocco", "argentina", "chile",
    "colombia", "venezuela", "ecuador", "bolivia", "paraguay", "uruguay",
    "cuba", "haiti", "jamaica", "panama", "guatemala", "honduras",
    "nicaragua", "costa rica", "el salvador",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Clean question_pii_entities by entity_type rules."
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


def is_age_text(text: str) -> bool:
    return bool(AGE_PATTERN.match(text or ""))


def normalize_place(text: str) -> str:
    """Lowercase, strip leading article 'the ', collapse spaces."""
    s = (text or "").strip().lower()
    if s.startswith("the "):
        s = s[4:].strip()
    s = re.sub(r"\s+", " ", s)
    # remove trailing punctuation
    s = s.rstrip(".,;:!?")
    return s


def match_place(text: str) -> tuple[bool, str | None, int]:
    """Try to match the entity text against the whitelist.

    Returns (hit, normalized_place_text, offset_in_original_text).
    `offset_in_original_text` is the number of leading characters that
    were stripped (e.g. for "A. Norway" -> 3). When hit is False,
    returns (False, None, 0).
    """
    if not text:
        return False, None, 0
    raw = text
    offset = 0
    # Strip MCQ option prefix once.
    m = OPTION_PREFIX.match(raw)
    if m:
        offset = m.end()
        raw = raw[offset:]
    candidate = normalize_place(raw)
    if candidate in PLACE_WHITELIST:
        # Compute the substring of the original text we actually keep.
        # Walk forward from `offset`, skip leading spaces / "the " to
        # align with `candidate`'s starting char in the original text.
        kept = text[offset:]
        # Strip leading whitespace.
        lead_ws = len(kept) - len(kept.lstrip())
        offset += lead_ws
        kept = kept.lstrip()
        # Strip leading "the " (case-insensitive) so the kept span
        # matches the canonical place name.
        if kept.lower().startswith("the "):
            offset += 4
            kept = kept[4:]
        # Strip trailing punctuation/whitespace from kept span.
        kept_stripped = kept.rstrip(".,;:!? \t\r\n")
        return True, kept_stripped, offset
    return False, None, 0


def filter_entities(entities) -> list[dict]:
    """Apply the keep/drop rules to an iterable of entity dicts."""
    if entities is None:
        return []
    try:
        ents = list(entities)
    except Exception:
        return []

    out: list[dict] = []
    for e in ents:
        ed = to_mutable_dict(e)
        et = ed.get("entity_type")
        text = ed.get("text", "") or ""

        if et in ("PERSON", "US_DRIVER_LICENSE", "US_BANK_NUMBER"):
            out.append(ed)
            continue

        if et == "DATE_TIME":
            if is_age_text(text):
                out.append(ed)
            continue

        if et == "LOCATION":
            hit, kept_text, offset = match_place(text)
            if hit and kept_text:
                # Adjust span to point at the kept place name.
                try:
                    new_start = int(ed.get("start", 0)) + offset
                    new_end = new_start + len(kept_text)
                    ed["start"] = new_start
                    ed["end"] = new_end
                    ed["text"] = kept_text
                except Exception:
                    # If anything weird, keep original.
                    pass
                out.append(ed)
            continue

        # NRP / US_PASSPORT / US_ITIN / URL / PHONE_NUMBER / others -> drop.
    return out


def process(input_path: Path, output_path: Path) -> None:
    print(f"Loading parquet: {input_path}", file=sys.stderr)
    df = pd.read_parquet(input_path)
    print(f"  rows={len(df)}", file=sys.stderr)
    if EXTRA_INFO_FIELD not in df.columns:
        print(f"[ERROR] '{EXTRA_INFO_FIELD}' column not found.", file=sys.stderr)
        sys.exit(2)

    new_col: list[dict] = []
    before_total = 0
    after_total = 0
    rows_with_pii_after = 0

    for ei in tqdm(df[EXTRA_INFO_FIELD].tolist(), desc="Cleaning entities"):
        d = to_mutable_dict(ei)
        ents = d.get(ENTITIES_KEY)
        try:
            before_total += 0 if ents is None else len(list(ents))
        except Exception:
            pass
        kept = filter_entities(ents)
        after_total += len(kept)
        if kept:
            rows_with_pii_after += 1
        d[ENTITIES_KEY] = kept
        new_col.append(d)

    df[EXTRA_INFO_FIELD] = new_col

    print(
        f"Done. entities before={before_total}, after={after_total}, "
        f"dropped={before_total - after_total}; "
        f"rows_with_pii_after={rows_with_pii_after}/{len(df)}",
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
