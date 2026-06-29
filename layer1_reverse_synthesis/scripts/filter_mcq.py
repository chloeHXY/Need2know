"""Filter multiple-choice questions from medical_o1_sft.json.

A question is considered multiple choice when its `Question` text contains
options labeled A, B, C, and D (at minimum). Options may appear inline or on
separate lines, e.g. "A. ...", "A) ...", or "(A) ...".
"""

import json
import re
from pathlib import Path


INPUT_PATH = Path(__file__).resolve().parent.parent / "medical_o1_sft.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "medical_o1_sft_mcq.json"


# Match an option marker like "A.", "A)", or "(A)" that appears at the start
# of a line OR after whitespace. Require A, B, C, D all to be present.
OPTION_PATTERNS = {
    letter: re.compile(
        rf"(?:(?<=\n)|(?<=\s)|^)\(?{letter}\)?[\.\):]\s",
    )
    for letter in ("A", "B", "C", "D")
}


def is_multiple_choice(question: str) -> bool:
    if not question:
        return False
    return all(pattern.search(question) for pattern in OPTION_PATTERNS.values())


def main() -> None:
    with INPUT_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    total = len(data)
    mcq_items = [item for item in data if is_multiple_choice(item.get("Question", ""))]

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(mcq_items, f, ensure_ascii=False, indent=4)

    print(f"Total items:        {total}")
    print(f"Multiple-choice:    {len(mcq_items)}")
    print(f"Saved to:           {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
