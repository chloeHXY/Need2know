"""
按 `ability` 字段分组统计 priv_query 隐私泄漏率与 ea 保留率。

输入：包含 priv_query / question_pii_entities / extra_info / ability 列的 parquet。
逻辑与 ``0_eval.py`` 保持一致（同一套 jaccard coverage + BERTScore 阈值），
区别是最终的聚合指标按 ``ability`` 分组分别统计，并在最后给出 overall 汇总。

输出：
1. stdout 打印每个 ability 分组的指标 + 全量汇总；
2. parquet（每行一条样本，含 ability 与各项标记，可用于二次分析）；
3. csv（每个 ability 一行的汇总指标表）。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from typing import Any

import pandas as pd
from tqdm import tqdm

# Reuse all primitives from the existing eval script so leak-detection
# semantics are identical.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(
    0,
    "/group/40047/eiraxyhuang/workspace/fc/DataG/z_eval/eval_privacy",
)
from com_privacy_score import (  # noqa: E402
    _bert_p_rescaled,
    _to_str_list,
    _get_bert_scorer,
)
# Import shared helpers from the sibling script.
import importlib.util as _ilu  # noqa: E402

_spec = _ilu.spec_from_file_location(
    "_eval0_mod", os.path.join(_HERE, "0_eval.py")
)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_get = _mod._get
_normalize_pii_items = _mod._normalize_pii_items
_build_filter_haystack = _mod._build_filter_haystack
_filter_items_by_haystack = _mod._filter_items_by_haystack
_detect_leaks = _mod._detect_leaks
_detect_hits = _mod._detect_hits
_key_spans_to_strs = _mod._key_spans_to_strs

PRIV_QUERY_COL = _mod.PRIV_QUERY_COL
EXTRA_INFO_COL = _mod.EXTRA_INFO_COL
PII_ENTITIES_COL = _mod.PII_ENTITIES_COL
COV_THRESHOLD = _mod.COV_THRESHOLD
BERT_THRESHOLD = _mod.BERT_THRESHOLD
EA_COV_THRESHOLD = _mod.EA_COV_THRESHOLD
EA_BERT_THRESHOLD = _mod.EA_BERT_THRESHOLD

ABILITY_COL = "ability"
DEFAULT_ABILITY_FALLBACK = "<unknown>"


# ---------------------------------------------------------------------------
# Local enhancements (only used by this script; do not modify 0_eval.py):
#   1) case-insensitive haystack filter: a pii/ne item already mentioned in
#      ea / key_spans should not be counted as leakage even if its casing
#      differs (e.g. ea has "Britt Lindqvist ... young student" but the pii
#      item "britt" is lower-cased).
#   2) order-preserving dedup of pii/ne items so the same surface form
#      (after light normalization: lowercased + whitespace-collapsed) is
#      counted at most once per row.
# ---------------------------------------------------------------------------
_WS_RE = re.compile(r"\s+")


def _norm_key(s: str) -> str:
    """Normalization key for case-insensitive equality / substring tests."""
    if s is None:
        return ""
    return _WS_RE.sub(" ", str(s).strip().lower())


def _filter_items_by_haystack_ci(
    items: list[str], haystack: str
) -> tuple[list[str], list[str]]:
    """Case-insensitive variant of ``_filter_items_by_haystack``.

    An item is dropped (treated as already-known context, not a leak) if
    its normalized form is a substring of the normalized haystack.
    """
    if not items or not haystack:
        return list(items), []
    hay_norm = _norm_key(haystack)
    kept: list[str] = []
    dropped: list[str] = []
    for it in items:
        s_norm = _norm_key(it)
        if s_norm and s_norm in hay_norm:
            dropped.append(it)
        else:
            kept.append(it)
    return kept, dropped


def _dedupe_items_preserve_order(items: list[str]) -> tuple[list[str], list[str]]:
    """De-duplicate items by their normalized form, keeping the first
    occurrence verbatim. Returns ``(unique_items, removed_duplicates)``.
    """
    if not items:
        return [], []
    seen: set[str] = set()
    unique: list[str] = []
    removed: list[str] = []
    for it in items:
        k = _norm_key(it)
        if not k:
            continue
        if k in seen:
            removed.append(it)
            continue
        seen.add(k)
        unique.append(it)
    return unique, removed

DEFAULT_INPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/4_.parquet"
)
DEFAULT_OUTPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/4_eval_ability_.parquet"
)
DEFAULT_SUMMARY_CSV = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/4_sum.csv"
)


# ---------------------------------------------------------------------------
# Aggregator: one bucket per ability label.
# ---------------------------------------------------------------------------
class _Bucket:
    __slots__ = (
        "n", "sample_with_any_item", "sample_leaked",
        "pii_total", "pii_leaked",
        "ne_total", "ne_leaked",
        "ea_total", "ea_hit",
    )

    def __init__(self) -> None:
        self.n = 0
        self.sample_with_any_item = 0
        self.sample_leaked = 0
        self.pii_total = 0
        self.pii_leaked = 0
        self.ne_total = 0
        self.ne_leaked = 0
        self.ea_total = 0
        self.ea_hit = 0

    def update(
        self,
        n_pii: int, n_pii_leak: int,
        n_ne: int, n_ne_leak: int,
        n_ea: int, n_ea_hit: int,
        sample_leak: bool,
    ) -> None:
        self.n += 1
        self.pii_total += n_pii
        self.pii_leaked += n_pii_leak
        self.ne_total += n_ne
        self.ne_leaked += n_ne_leak
        self.ea_total += n_ea
        self.ea_hit += n_ea_hit
        if (n_pii + n_ne) > 0:
            self.sample_with_any_item += 1
            if sample_leak:
                self.sample_leaked += 1

    def as_summary_row(self, ability: str) -> dict[str, Any]:
        sample_rate_full = self.sample_leaked / self.n if self.n else 0.0
        sample_rate_eligible = (
            self.sample_leaked / self.sample_with_any_item
            if self.sample_with_any_item else 0.0
        )
        pii_rate = (
            self.pii_leaked / self.pii_total if self.pii_total else 0.0
        )
        ne_rate = self.ne_leaked / self.ne_total if self.ne_total else 0.0
        ea_retention = self.ea_hit / self.ea_total if self.ea_total else 0.0
        return {
            "ability": ability,
            "n_samples": self.n,
            "n_samples_with_item": self.sample_with_any_item,
            "n_samples_leaked": self.sample_leaked,
            "sample_leak_rate_full": sample_rate_full,
            "sample_leak_rate_eligible": sample_rate_eligible,
            "pii_total": self.pii_total,
            "pii_leaked": self.pii_leaked,
            "pii_leak_rate": pii_rate,
            "ne_total": self.ne_total,
            "ne_leaked": self.ne_leaked,
            "ne_leak_rate": ne_rate,
            "ea_total": self.ea_total,
            "ea_hit": self.ea_hit,
            "ea_retention_rate": ea_retention,
        }


def _print_bucket(ability: str, b: _Bucket) -> None:
    s = b.as_summary_row(ability)
    print(f"\n--- ability = {ability!r} ---")
    print(f"  total samples                : {s['n_samples']}")
    print(f"  samples with >=1 pii/ne item : {s['n_samples_with_item']}")
    print(f"  leaked samples               : {s['n_samples_leaked']}")
    print(
        f"  sample-level leak rate (full)    : {s['sample_leak_rate_full']:.4f}"
        f"  ({s['n_samples_leaked']}/{s['n_samples']})"
    )
    print(
        f"  sample-level leak rate (eligible): {s['sample_leak_rate_eligible']:.4f}"
        f"  ({s['n_samples_leaked']}/{s['n_samples_with_item']})"
    )
    print(
        f"  pii item leak rate           : {s['pii_leak_rate']:.4f}"
        f"  ({s['pii_leaked']}/{s['pii_total']})"
    )
    print(
        f"  ne  item leak rate           : {s['ne_leak_rate']:.4f}"
        f"  ({s['ne_leaked']}/{s['ne_total']})"
    )
    print(
        f"  ea  item retention rate      : {s['ea_retention_rate']:.4f}"
        f"  ({s['ea_hit']}/{s['ea_total']})"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate priv_query leakage rate (pii + ne + ea retention) "
            "grouped by the `ability` column."
        )
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--summary_csv", default=DEFAULT_SUMMARY_CSV)
    parser.add_argument(
        "--no_bert", action="store_true",
        help="Disable BERTScore (only Jaccard-based leak).",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Only score the first N rows (0 = all).",
    )
    parser.add_argument(
        "--priv_query_col", default=PRIV_QUERY_COL,
        help=(
            "Name of the column holding the rewriter output. Default "
            "matches 0_eval.py (priv_query)."
        ),
    )
    args = parser.parse_args()

    print(f"[load] reading parquet: {args.input}")
    df = pd.read_parquet(args.input)
    print(f"[load] rows={len(df)} cols={df.columns.tolist()}")

    priv_col = args.priv_query_col
    for col in (priv_col, EXTRA_INFO_COL, PII_ENTITIES_COL):
        if col not in df.columns:
            raise KeyError(f"input parquet missing required column: {col}")
    if ABILITY_COL not in df.columns:
        raise KeyError(
            f"input parquet missing required column: {ABILITY_COL}. "
            "This script groups metrics by `ability`."
        )

    n = len(df)
    if args.limit and args.limit < n:
        df = df.iloc[: args.limit].copy()
        n = len(df)
    print(f"[plan] scoring {n} rows; priv_query_col={priv_col!r}")

    # Warm BERTScorer once.
    use_bert = not args.no_bert
    if use_bert:
        scorer = _get_bert_scorer()
        if scorer is None:
            print("[warn] BERTScorer unavailable -> falling back to Jaccard only")
            use_bert = False

    rows: list[dict[str, Any]] = []
    overall = _Bucket()
    by_ability: dict[str, _Bucket] = defaultdict(_Bucket)

    for i in tqdm(range(n), desc="scoring"):
        r = df.iloc[i]
        priv_q = r[priv_col] if isinstance(r[priv_col], str) else ""
        ei = r[EXTRA_INFO_COL]
        ability_raw = r[ABILITY_COL]
        ability = (
            str(ability_raw)
            if ability_raw is not None and str(ability_raw).strip()
            else DEFAULT_ABILITY_FALLBACK
        )
        question = _get(ei, "question", "") or ""
        ne_list_raw = _to_str_list(_get(ei, "ne"))
        pii_list_raw = _normalize_pii_items(r[PII_ENTITIES_COL])

        haystack = _build_filter_haystack(ei)
        # 1) Case-insensitive haystack filter: a pii/ne already mentioned
        #    in ea / key_spans (regardless of casing) is not a leak.
        pii_list, pii_dropped = _filter_items_by_haystack_ci(
            pii_list_raw, haystack
        )
        ne_list, ne_dropped = _filter_items_by_haystack_ci(
            ne_list_raw, haystack
        )
        # 2) Dedup repeated pii/ne items so e.g. "Britt" appearing 6 times
        #    in question_pii_entities is counted at most once.
        pii_list, pii_dup_removed = _dedupe_items_preserve_order(pii_list)
        ne_list, ne_dup_removed = _dedupe_items_preserve_order(ne_list)
        # Record the duplicates we removed alongside the haystack-dropped
        # ones for downstream auditability.
        if pii_dup_removed:
            pii_dropped = list(pii_dropped) + pii_dup_removed
        if ne_dup_removed:
            ne_dropped = list(ne_dropped) + ne_dup_removed

        pii_flags, pii_cov, pii_bert = _detect_leaks(pii_list, priv_q, use_bert)
        ne_flags, ne_cov, ne_bert = _detect_leaks(ne_list, priv_q, use_bert)

        # Build the ea candidate set used for retention scoring.
        # `key_spans` (only present for ability=med) carries the medically
        # essential content that must be kept in priv_query, so we treat it
        # as additional ea items. Items are deduped (case/whitespace-insensitive)
        # while preserving the first-seen surface form.
        ea_raw = _to_str_list(_get(ei, "ea"))
        key_spans_raw = _key_spans_to_strs(_get(ei, "key_spans"))
        ea_list, _ea_dup_removed = _dedupe_items_preserve_order(
            list(ea_raw) + list(key_spans_raw)
        )
        ea_flags, ea_cov, ea_bert = _detect_hits(ea_list, priv_q, use_bert)

        n_pii = len(pii_list)
        n_ne = len(ne_list)
        n_ea = len(ea_list)
        n_pii_leak = sum(pii_flags)
        n_ne_leak = sum(ne_flags)
        n_ea_hit = sum(ea_flags)
        sample_leak = (n_pii_leak > 0) or (n_ne_leak > 0)

        overall.update(
            n_pii, n_pii_leak, n_ne, n_ne_leak, n_ea, n_ea_hit, sample_leak,
        )
        by_ability[ability].update(
            n_pii, n_pii_leak, n_ne, n_ne_leak, n_ea, n_ea_hit, sample_leak,
        )

        rows.append({
            "index": int(_get(ei, "index", i) or i),
            "ability": ability,
            "question": question,
            "priv_query": priv_q,
            "pii_items": pii_list,
            "pii_dropped_by_keyspans_ea": pii_dropped,
            "pii_leak_flags": pii_flags,
            "pii_coverage": pii_cov,
            "pii_bert_p": pii_bert,
            "n_pii": n_pii,
            "n_pii_leak": n_pii_leak,
            "ne_items": ne_list,
            "ne_dropped_by_keyspans_ea": ne_dropped,
            "ne_leak_flags": ne_flags,
            "ne_coverage": ne_cov,
            "ne_bert_p": ne_bert,
            "n_ne": n_ne,
            "n_ne_leak": n_ne_leak,
            "ea_items": ea_list,
            "ea_hit_flags": ea_flags,
            "ea_coverage": ea_cov,
            "ea_bert_p": ea_bert,
            "n_ea": n_ea,
            "n_ea_hit": n_ea_hit,
            "sample_leak": sample_leak,
        })

    # ------------------------- print summary -------------------------
    print("\n=== Privacy leakage evaluation grouped by `ability` ===")
    print(f"  leak thresholds              : cov>={COV_THRESHOLD}, bertP>{BERT_THRESHOLD}")
    print(f"  ea retention thresholds      : cov>={EA_COV_THRESHOLD}, bertP>{EA_BERT_THRESHOLD}")
    print(f"  bertscore enabled            : {use_bert}")

    # Sort abilities for stable, readable output.
    summary_rows: list[dict[str, Any]] = []
    for ability in sorted(by_ability.keys()):
        bucket = by_ability[ability]
        _print_bucket(ability, bucket)
        summary_rows.append(bucket.as_summary_row(ability))

    _print_bucket("__overall__", overall)
    summary_rows.append(overall.as_summary_row("__overall__"))

    # ------------------------------ persist ------------------------------
    out_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    out_df.to_parquet(args.output, index=False)
    print(f"\n[save] per-row results -> {args.output}")

    summary_df = pd.DataFrame(summary_rows)
    os.makedirs(os.path.dirname(args.summary_csv), exist_ok=True)
    summary_df.to_csv(args.summary_csv, index=False)
    print(f"[save] per-ability summary -> {args.summary_csv}")
    # Also echo summary as a markdown-ish table for quick eyeballing.
    print("\n[summary table]")
    cols = [
        "ability", "n_samples", "n_samples_with_item", "n_samples_leaked",
        "sample_leak_rate_full", "sample_leak_rate_eligible",
        "pii_leaked", "pii_total", "pii_leak_rate",
        "ne_leaked", "ne_total", "ne_leak_rate",
        "ea_hit", "ea_total", "ea_retention_rate",
    ]
    with pd.option_context(
        "display.max_columns", None,
        "display.width", 200,
        "display.float_format", lambda x: f"{x:.4f}",
    ):
        print(summary_df[cols].to_string(index=False))


if __name__ == "__main__":
    main()
