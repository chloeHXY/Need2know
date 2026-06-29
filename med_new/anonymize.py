"""
Annotate PII for `extra_info["question"]` of each row in a Parquet file using
Microsoft Presidio. The annotation results are stored back into the
`extra_info` dict (as sub-fields), instead of as new top-level columns.

Sub-fields added under `extra_info`:
    - `question_anonymized`   : the redacted/anonymized question text
    - `question_pii_entities` : list of detected PII entities
                                (entity_type, start, end, score, text)

Usage:
    python anonymize.py \
        --input  /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.parquet \
        --output /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.parquet
"""

import argparse
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine


DEFAULT_INPUT = "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.parquet"
DEFAULT_OUTPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.parquet"
)

ANONYMIZED_KEY = "question_anonymized"
ENTITIES_KEY = "question_pii_entities"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Annotate PII for `extra_info['question']` in a Parquet file via "
            "Presidio, and write results back into the `extra_info` dict."
        )
    )
    parser.add_argument("--input", "-i", default=DEFAULT_INPUT,
                        help="Path to the input Parquet file.")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT,
                        help="Path to the output Parquet file.")
    parser.add_argument("--language", "-l", default="en",
                        help="Language code for the analyzer (default: en).")
    parser.add_argument("--extra-info-field", default="extra_info",
                        help="Name of the column containing the dict-like object "
                             "(default: extra_info).")
    parser.add_argument("--question-key", default="question",
                        help="Key inside extra_info that holds the question text "
                             "(default: question).")
    return parser.parse_args()


def build_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    """Initialize Presidio analyzer + anonymizer once and reuse them."""
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()
    return analyzer, anonymizer


def to_mutable_dict(extra_info) -> dict:
    """Convert an arbitrary extra_info object to a plain mutable dict.

    Parquet readers may return dict, numpy scalar object, or other
    mapping-like objects. We normalize to a regular dict so that we can
    safely add keys.
    """
    if extra_info is None:
        return {}
    if isinstance(extra_info, dict):
        # Make a shallow copy to avoid mutating the original in-place.
        return dict(extra_info)
    # numpy / pandas may wrap dicts inside object arrays.
    if isinstance(extra_info, np.ndarray):
        # Try to interpret as a list of (key, value) pairs.
        try:
            return dict(extra_info.tolist())
        except Exception:
            pass
    # Fall back to attempting to coerce via dict().
    try:
        return dict(extra_info)
    except Exception:
        # As a last resort, wrap original value under a synthetic key.
        return {"_original": copy.deepcopy(extra_info)}


def extract_question(extra_info_dict: dict, question_key: str = "question") -> str:
    """Extract the question text from an extra_info dict."""
    val = extra_info_dict.get(question_key, "")
    if val is None:
        return ""
    return str(val)


def anonymize_text(
    text: str,
    analyzer: AnalyzerEngine,
    anonymizer: AnonymizerEngine,
    language: str = "en",
) -> tuple[str, list[dict]]:
    """Run analyzer + anonymizer on a single piece of text.

    Returns:
        anonymized_text: the redacted/anonymized text
        entities:       list of detected PII entities
    """
    if not text:
        return text, []

    results = analyzer.analyze(text=text, language=language)

    entities = [
        {
            "entity_type": r.entity_type,
            "start": int(r.start),
            "end": int(r.end),
            "score": float(r.score),
            "text": text[r.start:r.end],
        }
        for r in results
    ]

    anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
    return anonymized.text, entities


def process_file(
    input_path: Path,
    output_path: Path,
    extra_info_field: str,
    question_key: str,
    language: str,
) -> None:
    print(f"Loading parquet: {input_path}", file=sys.stderr)
    df = pd.read_parquet(input_path)
    print(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}", file=sys.stderr)

    if extra_info_field not in df.columns:
        print(f"[ERROR] column '{extra_info_field}' not found in parquet.",
              file=sys.stderr)
        sys.exit(2)

    analyzer, anonymizer = build_engines()

    new_extra_info_list: list[dict] = []
    pii_count = 0

    for extra_info in tqdm(df[extra_info_field].tolist(), desc="Annotating PII"):
        info_dict = to_mutable_dict(extra_info)
        question = extract_question(info_dict, question_key=question_key)

        if not question:
            info_dict[ANONYMIZED_KEY] = None
            info_dict[ENTITIES_KEY] = []
        else:
            anonymized_text, entities = anonymize_text(
                question, analyzer, anonymizer, language=language
            )
            info_dict[ANONYMIZED_KEY] = anonymized_text
            info_dict[ENTITIES_KEY] = entities
            if entities:
                pii_count += 1

        new_extra_info_list.append(info_dict)

    df[extra_info_field] = new_extra_info_list

    total = len(df)
    print(f"Done. Total rows: {total}, rows with PII: {pii_count}",
          file=sys.stderr)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing parquet: {output_path}", file=sys.stderr)
    df.to_parquet(output_path, index=False)
    print("Saved.", file=sys.stderr)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.is_file():
        print(f"[ERROR] input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    process_file(
        input_path=input_path,
        output_path=output_path,
        extra_info_field=args.extra_info_field,
        question_key=args.question_key,
        language=args.language,
    )


if __name__ == "__main__":
    main()
