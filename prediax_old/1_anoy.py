"""
Anonymize the `extra_info["question"]` field in a Parquet file using
Microsoft Presidio.

Input : /group/40047/eiraxyhuang/workspace/fc/DataG/prediax/test_with_priv_query.parquet
Output: /group/40047/eiraxyhuang/workspace/fc/DataG/prediax/test_with_priv_query.anonymized.parquet

For each row, the script adds two new TOP-LEVEL columns (NOT inside extra_info):
    - `question_anonymized`   : the redacted/anonymized question text
    - `question_pii_entities` : list[str] of detected PII original text spans

All original columns (including `extra_info`) are preserved unchanged.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine


DEFAULT_INPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/test_with_priv_query.parquet"
)
DEFAULT_OUTPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/0_.parquet"
)

NEW_TEXT_COLUMN = "question_anonymized"
NEW_ENTITIES_COLUMN = "question_pii_entities"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Anonymize the `extra_info['question']` field in a Parquet file via Presidio."
    )
    parser.add_argument("--input", "-i", default=DEFAULT_INPUT,
                        help="Path to the input Parquet file.")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT,
                        help="Path to the output Parquet file.")
    parser.add_argument("--language", "-l", default="en",
                        help="Language code for the analyzer (default: en).")
    parser.add_argument("--extra-info-field", default="extra_info",
                        help="Name of the column containing the dict-like object (default: extra_info).")
    parser.add_argument("--question-key", default="question",
                        help="Key inside extra_info that holds the question text (default: question).")
    return parser.parse_args()


def build_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    """Initialize Presidio analyzer + anonymizer once and reuse them."""
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()
    return analyzer, anonymizer


def extract_question(extra_info, question_key: str = "question") -> str:
    """Extract the question text from an extra_info object (dict-like)."""
    if extra_info is None:
        return ""
    if isinstance(extra_info, dict):
        return extra_info.get(question_key, "") or ""
    # Some parquet readers may return objects supporting item access
    try:
        val = extra_info[question_key]
        return val or ""
    except Exception:
        return ""


def anonymize_text(
    text: str,
    analyzer: AnalyzerEngine,
    anonymizer: AnonymizerEngine,
    language: str = "en",
) -> tuple[str, list[str]]:
    """Run analyzer + anonymizer on a single piece of text.

    Returns:
        anonymized_text: the redacted/anonymized text
        entities:       list[str] of detected PII original text spans
    """
    if not text:
        return text, []

    results = analyzer.analyze(text=text, language=language)

    entities = [text[r.start:r.end] for r in results]

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

    anonymized_texts: list[str | None] = []
    pii_entities: list[list[str]] = []

    for extra_info in tqdm(df[extra_info_field].tolist(), desc="Anonymizing"):
        question = extract_question(extra_info, question_key=question_key)
        if not question:
            anonymized_texts.append(None)
            pii_entities.append([])
            continue

        anonymized_text, entities = anonymize_text(
            question, analyzer, anonymizer, language=language
        )
        anonymized_texts.append(anonymized_text)
        pii_entities.append(entities)

    # Add new fields as TOP-LEVEL columns (NOT inside extra_info)
    df[NEW_TEXT_COLUMN] = anonymized_texts
    df[NEW_ENTITIES_COLUMN] = pii_entities

    # Sanity stats
    total = len(df)
    with_pii = sum(1 for ents in pii_entities if ents)
    print(f"Done. Total rows: {total}, rows with PII: {with_pii}",
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