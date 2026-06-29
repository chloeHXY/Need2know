"""
Variant of ``0_eval_by_ability.py`` with a *compensation* rule for the
``wild`` ability bucket:

  When aggregating metrics, drop the top-50 high-leak ``wild`` samples
  listed in ``wild_pii_leak_sorted.json`` (sorted by ``n_pii``).
  Specifically, only rows whose ability == ``wild`` AND that match one of
  those top-50 entries are skipped from aggregation. All other rows are
  processed exactly the same as in ``0_eval_by_ability.py``.

Matching is done robustly via multiple keys (any of the following is
sufficient for a match):
  * ``row_index`` of the JSON entry == positional index of the parquet row,
  * ``(question, priv_query)`` text pair equality (after normalization),
  * ``question`` text equality (fallback) when the priv_query in the JSON
    differs from the new run's priv_query (e.g. priv_query was regenerated).

The output parquet still keeps every row (with an additional
``excluded_from_stats`` flag for transparency); only the aggregated
metrics drop the matched rows.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from typing import Any

import pandas as pd
from tqdm import tqdm

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(
    0,
    "/group/40047/eiraxyhuang/workspace/fc/DataG/z_eval/eval_privacy",
)
from com_privacy_score import (  # noqa: E402
    _bert_p_rescaled,  # noqa: F401  (kept for parity with sibling script)
    _to_str_list,
    _get_bert_scorer,
)

# Load shared helpers from the 0_eval.py module that lives under
# inference/0_privacy/. There is no sibling 0_eval.py in this directory.
import importlib.util as _ilu  # noqa: E402

_EVAL0_PATH = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/0_privacy/0_eval.py"
)
_spec = _ilu.spec_from_file_location("_eval0_mod", _EVAL0_PATH)
_mod = _ilu.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_get = _mod._get
_normalize_pii_items = _mod._normalize_pii_items
_build_filter_haystack = _mod._build_filter_haystack
_filter_items_by_haystack = _mod._filter_items_by_haystack  # noqa: F401
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
WILD_ABILITY = "wild"


# ---------------------------------------------------------------------------
# Local helpers (case-insensitive haystack filter + dedup), copied from
# 0_eval_by_ability.py to avoid cross-script coupling.
# ---------------------------------------------------------------------------
_WS_RE = re.compile(r"\s+")


def _norm_key(s: str) -> str:
    if s is None:
        return ""
    return _WS_RE.sub(" ", str(s).strip().lower())


def _filter_items_by_haystack_ci(
    items: list[str], haystack: str
) -> tuple[list[str], list[str]]:
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


def _dedupe_items_preserve_order(
    items: list[str],
) -> tuple[list[str], list[str]]:
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


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_INPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/5_.parquet"
)
DEFAULT_OUTPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/5_eval.parquet"
)
DEFAULT_SUMMARY_CSV = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/prediax/5_eval.csv"
)
DEFAULT_EXCLUDE_JSON = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/"
    "wild_pii_leak_sorted.json"
)
DEFAULT_TOP_K = 50


# ---------------------------------------------------------------------------
# Exclusion list loader
# ---------------------------------------------------------------------------
def _load_exclude_set(
    json_path: str, top_k: int
) -> tuple[set[int], set[str], set[tuple[str, str]]]:
    """Load the top-K wild rows to drop.

    Returns three lookup sets:
      * row indices
      * normalized question texts
      * normalized (question, priv_query) pairs
    """
    if not json_path or not os.path.exists(json_path):
        print(
            f"[excl] WARNING: exclusion json not found at {json_path}; "
            "no rows will be dropped."
        )
        return set(), set(), set()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(
            f"expected top-level list in {json_path}, got {type(data)}"
        )

    take = data[: max(0, int(top_k))]
    idx_set: set[int] = set()
    q_set: set[str] = set()
    qp_set: set[tuple[str, str]] = set()
    for entry in take:
        ri = entry.get("row_index")
        if isinstance(ri, int):
            idx_set.add(ri)
        q = _norm_key(entry.get("question", ""))
        p = _norm_key(entry.get("priv_query", ""))
        if q:
            q_set.add(q)
        if q and p:
            qp_set.add((q, p))
    print(
        f"[excl] loaded {len(take)} entries from {json_path}: "
        f"{len(idx_set)} row_index keys, {len(q_set)} question keys."
    )
    return idx_set, q_set, qp_set


def _is_excluded(
    ability: str,
    row_pos: int,
    question: str,
    priv_query: str,
    idx_set: set[int],
    q_set: set[str],
    qp_set: set[tuple[str, str]],
) -> tuple[bool, str]:
    """Return (excluded?, reason). Only ability==wild can be excluded."""
    if ability != WILD_ABILITY:
        return False, ""
    qn = _norm_key(question)
    pn = _norm_key(priv_query)
    if (qn, pn) in qp_set:
        return True, "match:question+priv_query"
    if qn and qn in q_set:
        return True, "match:question"
    if row_pos in idx_set:
        return True, "match:row_index"
    return False, ""


# ---------------------------------------------------------------------------
# Aggregator (same as sibling script)
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
        # Sample-level leak rate is now computed over NE-only:
        # eligible denominator = samples with >=1 ne item;
        # numerator           = samples with >=1 ne leak.
        if n_ne > 0:
            self.sample_with_any_item += 1
            if sample_leak:
                self.sample_leaked += 1

    def as_summary_row(self, ability: str) -> dict[str, Any]:
        # `sample_leaked` here counts only NE-leaked samples (see `update`).
        # `sample_with_any_item` here counts only samples with >=1 NE item.
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
    print(f"  samples with >=1 ne item     : {s['n_samples_with_item']}")
    print(f"  ne-leaked samples            : {s['n_samples_leaked']}")
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
            "Evaluate priv_query leakage grouped by `ability`, but drop the "
            "top-K high-leak `wild` rows (per wild_pii_leak_sorted.json) "
            "before aggregating metrics."
        )
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--summary_csv", default=DEFAULT_SUMMARY_CSV)
    parser.add_argument(
        "--exclude_json", default=DEFAULT_EXCLUDE_JSON,
        help="Path to wild_pii_leak_sorted.json (sorted desc by n_pii).",
    )
    parser.add_argument(
        "--top_k", type=int, default=DEFAULT_TOP_K,
        help="Drop the first K entries from the exclude json (default 50).",
    )
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

    # Load top-K exclusion set.
    idx_set, q_set, qp_set = _load_exclude_set(args.exclude_json, args.top_k)

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

    n_excluded = 0
    n_excluded_by_reason: dict[str, int] = defaultdict(int)

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
        pii_list, pii_dropped = _filter_items_by_haystack_ci(
            pii_list_raw, haystack
        )
        ne_list, ne_dropped = _filter_items_by_haystack_ci(
            ne_list_raw, haystack
        )
        pii_list, pii_dup_removed = _dedupe_items_preserve_order(pii_list)
        ne_list, ne_dup_removed = _dedupe_items_preserve_order(ne_list)
        if pii_dup_removed:
            pii_dropped = list(pii_dropped) + pii_dup_removed
        if ne_dup_removed:
            ne_dropped = list(ne_dropped) + ne_dup_removed

        pii_flags, pii_cov, pii_bert = _detect_leaks(pii_list, priv_q, use_bert)
        ne_flags, ne_cov, ne_bert = _detect_leaks(ne_list, priv_q, use_bert)

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
        # Per request, sample-level leak is defined by NE leakage only.
        sample_leak = n_ne_leak > 0

        # Decide whether to skip this row from aggregation.
        excluded, reason = _is_excluded(
            ability, i, question, priv_q, idx_set, q_set, qp_set,
        )
        if excluded:
            n_excluded += 1
            n_excluded_by_reason[reason] += 1
        else:
            overall.update(
                n_pii, n_pii_leak, n_ne, n_ne_leak, n_ea, n_ea_hit,
                sample_leak,
            )
            by_ability[ability].update(
                n_pii, n_pii_leak, n_ne, n_ne_leak, n_ea, n_ea_hit,
                sample_leak,
            )

        rows.append({
            "index": int(_get(ei, "index", i) or i),
            "row_pos": i,
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
            "excluded_from_stats": excluded,
            "exclude_reason": reason,
        })

    # ------------------------- print summary -------------------------
    print("\n=== Privacy leakage evaluation grouped by `ability` "
          "(wild top-K dropped) ===")
    print(f"  leak thresholds              : cov>={COV_THRESHOLD}, bertP>{BERT_THRESHOLD}")
    print(f"  ea retention thresholds      : cov>={EA_COV_THRESHOLD}, bertP>{EA_BERT_THRESHOLD}")
    print(f"  bertscore enabled            : {use_bert}")
    print(f"  exclude_json                 : {args.exclude_json}")
    print(f"  top_k dropped from `wild`    : {args.top_k}")
    print(f"  rows actually excluded       : {n_excluded}")
    if n_excluded:
        for reason, cnt in sorted(n_excluded_by_reason.items()):
            print(f"    - {reason}: {cnt}")

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
