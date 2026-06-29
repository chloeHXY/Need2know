"""
对 med.anonymized.cleaned.with_answer_label.parquet 进行处理：
将 extra_info.query_gt 字段填充到 reward_model.ground_truth 字段。

行为：
- 仅修改 reward_model.ground_truth；reward_model 中的其它键（如 style）保持不变。
- 如果 extra_info.query_gt 缺失或为 None/空，则保留原 ground_truth 不变，并打印告警。
- 默认就地覆盖原文件，可通过 --output 指定输出路径。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_INPUT = Path(
    "/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/"
    "med.anonymized.cleaned.with_answer_label.parquet"
)


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output parquet path; defaults to overwrite --input in place",
    )
    args = parser.parse_args()

    in_path: Path = args.input
    out_path: Path = args.output or in_path

    if not in_path.is_file():
        print(f"[ERROR] input not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading parquet: {in_path}", file=sys.stderr)
    df = pd.read_parquet(in_path)
    n = len(df)
    print(f"  rows={n}, columns={df.columns.tolist()}", file=sys.stderr)

    for col in ("extra_info", "reward_model"):
        if col not in df.columns:
            print(f"[ERROR] column '{col}' not found.", file=sys.stderr)
            sys.exit(2)

    new_reward_models: list[dict] = []
    filled = 0
    changed = 0
    missing = 0
    for ei, rm in zip(df["extra_info"].tolist(), df["reward_model"].tolist()):
        ei_d = to_mutable_dict(ei)
        rm_d = to_mutable_dict(rm)

        ans = ei_d.get("query_gt")
        if ans is None or (isinstance(ans, str) and ans == ""):
            missing += 1
            new_reward_models.append(rm_d)
            continue

        old_gt = rm_d.get("ground_truth")
        rm_d["ground_truth"] = ans
        filled += 1
        if old_gt != ans:
            changed += 1
        new_reward_models.append(rm_d)

    df["reward_model"] = new_reward_models

    print(
        f"  filled={filled}, changed={changed}, missing_query_gt={missing}",
        file=sys.stderr,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing parquet: {out_path}", file=sys.stderr)
    df.to_parquet(out_path, index=False)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
