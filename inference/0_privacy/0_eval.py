"""
输入文件/group/40047/eiraxyhuang/workspace/fc/DataG/inference/0_privacy/test_with_priv_query_with_pii.parquet
目标：衡量priv_query字段相对于extra_info中的question字段的泄漏率
辅助判断的数据：
- question_pii_entities: question的pii打标列表，衡量priv_query是否泄漏了question中的pii信息
 （注意，question_pii_entities中存在一些噪声没有清理，比如遇到这种选项字符串则跳过： A.xxx B.xxx C.xxx D.xxx E.xxx，不视作pii）
- extra_info['ne']: question的non-essential打标列表，衡量priv_query是否泄漏了question中的任务无关信息
最终需要统计：
一旦一个样本出现了上面任意一种pii/ne泄露，则认为该样本隐私泄露
如何评估泄露：我们会联合jacarrd和bertscore，参考脚本：/group/40047/eiraxyhuang/workspace/fc/DataG/z_eval/eval_privacy/com_privacy_score.py

可以参考:
Sample level rate: 总样本中有几个样本出现了隐私泄露
pii leak rate: pii item 泄露数/总pii item数
ne leak rate: ne item 泄露数/总ne item数
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any, Iterable

import pandas as pd
from tqdm import tqdm

# Reuse the exact reward-side primitives so leak detection is aligned with
# training-time reward (com_privacy_score.compute_score).
sys.path.insert(
    0,
    "/group/40047/eiraxyhuang/workspace/fc/DataG/z_eval/eval_privacy",
)
from com_privacy_score import (  # noqa: E402
    coverage,
    _bert_p_rescaled,
    _to_str_list,
    _get_bert_scorer,
)


# ---------------------------------------------------------------------------
# Defaults / thresholds
# ---------------------------------------------------------------------------
DEFAULT_INPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/4_.parquet"
)
DEFAULT_OUTPUT = (
    "/group/40047/eiraxyhuang/workspace/fc/DataG/inference/mix_data/4_eval_results.parquet"
)

# Same thresholds as com_privacy_score.compute_score / training-time reward.
COV_THRESHOLD = 1.0     # >= 1.0 -> literal/lexical leak
BERT_THRESHOLD = 0.3    # >  0.3 -> semantic leak

# Thresholds for `ea` retention check (utility-side, mirrors
# com_privacy_score.compute_score's utility branch):
#   an ea item counts as "retained" iff coverage(ea, priv_query) >= 0.5
#   OR BERTScore P_rescaled(ea, priv_query) > 0.3.
EA_COV_THRESHOLD = 0.5
EA_BERT_THRESHOLD = 0.3

PRIV_QUERY_COL = "priv_query"
EXTRA_INFO_COL = "extra_info"
PII_ENTITIES_COL = "question_pii_entities"


# ---------------------------------------------------------------------------
# extra_info / pii-entity helpers
# ---------------------------------------------------------------------------
def _get(extra_info: Any, key: str, default: Any = None) -> Any:
    if extra_info is None:
        return default
    if isinstance(extra_info, dict):
        return extra_info.get(key, default)
    try:
        return extra_info[key]
    except Exception:
        return default


# Multiple-choice option string, e.g. "A.foo B.bar C.baz D.qux E.quux".
# Such strings are noise from upstream PII annotation and must NOT be
# treated as real PII. We require at least 3 letter-prefixed segments to
# be confident we caught an MCQ list (and not a normal sentence).
_MCQ_OPTION_RE = re.compile(
    r"(?:^|\s)[A-Ea-e]\s*[\.:\)]\s*\S",
)


def _looks_like_mcq_options(text: str) -> bool:
    """Heuristic: a string is an MCQ option list if it contains >=3 of
    'A.xxx', 'B.xxx', 'C.xxx', ... segments."""
    if not text:
        return False
    hits = _MCQ_OPTION_RE.findall(text)
    return len(hits) >= 3


def _key_spans_to_strs(raw_key_spans: Any) -> list[str]:
    """Flatten ``extra_info['key_spans']`` to a list[str].

    The field can be either ``list[str]`` (new schema) or
    ``list[{"span": str, "reason": str}]`` (legacy schema). Anything else
    is coerced via ``str``. Empty values are dropped.
    """
    if raw_key_spans is None:
        return []
    if isinstance(raw_key_spans, str):
        return [raw_key_spans] if raw_key_spans else []
    if not isinstance(raw_key_spans, Iterable):
        return [str(raw_key_spans)]
    out: list[str] = []
    for item in raw_key_spans:
        if item is None:
            continue
        if isinstance(item, dict):
            v = item.get("span", "")
            s = str(v).strip() if v is not None else ""
        else:
            s = str(item).strip()
        if s:
            out.append(s)
    return out


def _build_filter_haystack(extra_info: Any) -> str:
    """Concatenate ``extra_info['key_spans']`` and ``extra_info['ea']`` into
    a single haystack string. A pii/ne item that appears as a substring of
    this haystack is treated as already-known (non-private) information
    and will be excluded from leak detection.
    """
    parts: list[str] = []
    parts.extend(_key_spans_to_strs(_get(extra_info, "key_spans")))
    parts.extend(_to_str_list(_get(extra_info, "ea")))
    # Use a separator that is unlikely to appear inside any item so two
    # adjacent items can't accidentally form a substring match.
    return "\n\u2029\n".join(parts)


def _filter_items_by_haystack(
    items: list[str], haystack: str
) -> tuple[list[str], list[str]]:
    """Split ``items`` into (kept, dropped) by checking substring membership
    in ``haystack``. An item is dropped (i.e. NOT considered private) if
    its stripped, non-empty form is a substring of ``haystack``.
    """
    if not items or not haystack:
        return list(items), []
    kept: list[str] = []
    dropped: list[str] = []
    for it in items:
        s = it.strip()
        if s and s in haystack:
            dropped.append(it)
        else:
            kept.append(it)
    return kept, dropped


def _normalize_pii_items(raw_entities: Any) -> list[str]:
    """Normalize the raw `question_pii_entities` cell to list[str].

    The annotation pipeline stores it as a list of strings (each one is
    the original text span), but be tolerant if it's a list[dict] with a
    `text` field (older format).
    """
    if raw_entities is None:
        return []
    if isinstance(raw_entities, str):
        items = [raw_entities]
    elif isinstance(raw_entities, Iterable):
        items = []
        for it in raw_entities:
            if it is None:
                continue
            if isinstance(it, dict):
                v = it.get("text", "")
                if v:
                    items.append(str(v))
            else:
                s = str(it).strip()
                if s:
                    items.append(s)
    else:
        items = [str(raw_entities)]

    cleaned: list[str] = []
    for s in items:
        s = s.strip()
        if not s:
            continue
        if _looks_like_mcq_options(s):
            continue
        cleaned.append(s)
    return cleaned


# ---------------------------------------------------------------------------
# Leak detection: jaccard coverage + BERTScore rescaled precision
# ---------------------------------------------------------------------------
def _detect_leaks(
    items: list[str],
    priv_query: str,
    use_bert: bool,
) -> tuple[list[bool], list[float], list[float | None]]:
    """For each item C in `items`, decide whether C is leaked into priv_query.

    Returns
    -------
    leak_flags : list[bool]  -- True if leaked (cov>=1.0 OR bert P>0.3)
    cov_list   : list[float] -- coverage(priv_query, C) for each item
    bert_list  : list[float|None] -- BERTScore P_rescaled or None
    """
    n = len(items)
    if n == 0 or not priv_query:
        return [False] * n, [0.0] * n, [None] * n

    cov_list = [coverage(priv_query, c) for c in items]
    cov_flags = [c >= COV_THRESHOLD for c in cov_list]

    bert_list: list[float | None] = [None] * n
    bert_flags = [False] * n
    if use_bert:
        scores = _bert_p_rescaled(items, priv_query)
        if scores is not None:
            bert_list = [float(s) for s in scores]
            bert_flags = [s > BERT_THRESHOLD for s in scores]

    leak_flags = [a or b for a, b in zip(cov_flags, bert_flags)]
    return leak_flags, cov_list, bert_list


def _detect_hits(
    items: list[str],
    priv_query: str,
    use_bert: bool,
) -> tuple[list[bool], list[float], list[float | None]]:
    """For each item E in ``items`` (essential / `ea` content), decide
    whether E is *retained* in ``priv_query``.

    Mirrors the utility branch of ``com_privacy_score.compute_score``:
        hit iff coverage(priv_query, E) >= 0.5 OR BERTScore P_rs > 0.3.
    """
    n = len(items)
    if n == 0 or not priv_query:
        return [False] * n, [0.0] * n, [None] * n

    cov_list = [coverage(priv_query, e) for e in items]
    cov_flags = [c >= EA_COV_THRESHOLD for c in cov_list]

    bert_list: list[float | None] = [None] * n
    bert_flags = [False] * n
    if use_bert:
        scores = _bert_p_rescaled(items, priv_query)
        if scores is not None:
            bert_list = [float(s) for s in scores]
            bert_flags = [s > EA_BERT_THRESHOLD for s in scores]

    hit_flags = [a or b for a, b in zip(cov_flags, bert_flags)]
    return hit_flags, cov_list, bert_list


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate priv_query leakage rate (pii + ne) on a parquet."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--no_bert", action="store_true",
        help="Disable BERTScore (only Jaccard-based leak).",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Only score the first N rows (0 = all).",
    )
    args = parser.parse_args()

    print(f"[load] reading parquet: {args.input}")
    df = pd.read_parquet(args.input)
    print(f"[load] rows={len(df)} cols={df.columns.tolist()}")

    for col in (PRIV_QUERY_COL, EXTRA_INFO_COL, PII_ENTITIES_COL):
        if col not in df.columns:
            raise KeyError(f"input parquet missing required column: {col}")

    n = len(df)
    if args.limit and args.limit < n:
        df = df.iloc[: args.limit].copy()
        n = len(df)
    print(f"[plan] scoring {n} rows")

    # Warm up BERTScorer once so per-row calls are cheap and we fail loud
    # early if it's unavailable.
    use_bert = not args.no_bert
    if use_bert:
        scorer = _get_bert_scorer()
        if scorer is None:
            print("[warn] BERTScorer unavailable -> falling back to Jaccard only")
            use_bert = False

    rows: list[dict[str, Any]] = []

    # Aggregates across the whole dataset.
    pii_total = 0
    pii_leaked = 0
    ne_total = 0
    ne_leaked = 0
    ea_total = 0
    ea_hit = 0
    sample_leaked = 0
    sample_with_any_item = 0  # samples that have at least 1 pii or ne item

    for i in tqdm(range(n), desc="scoring"):
        r = df.iloc[i]
        priv_q = r[PRIV_QUERY_COL] if isinstance(r[PRIV_QUERY_COL], str) else ""
        ei = r[EXTRA_INFO_COL]
        question = _get(ei, "question", "") or ""
        ne_list_raw = _to_str_list(_get(ei, "ne"))
        pii_list_raw = _normalize_pii_items(r[PII_ENTITIES_COL])

        # Items that appear inside extra_info['key_spans'] or
        # extra_info['ea'] are essential / already-known context and must
        # NOT be counted as private leakage targets.
        haystack = _build_filter_haystack(ei)
        pii_list, pii_dropped = _filter_items_by_haystack(
            pii_list_raw, haystack
        )
        ne_list, ne_dropped = _filter_items_by_haystack(
            ne_list_raw, haystack
        )

        pii_flags, pii_cov, pii_bert = _detect_leaks(pii_list, priv_q, use_bert)
        ne_flags, ne_cov, ne_bert = _detect_leaks(ne_list, priv_q, use_bert)

        # `ea` items are essential context that the rewriter is *expected*
        # to keep. Measure how many of them are still retained in priv_query.
        ea_list = _to_str_list(_get(ei, "ea"))
        ea_flags, ea_cov, ea_bert = _detect_hits(ea_list, priv_q, use_bert)

        n_pii = len(pii_list)
        n_ne = len(ne_list)
        n_ea = len(ea_list)
        n_pii_leak = sum(pii_flags)
        n_ne_leak = sum(ne_flags)
        n_ea_hit = sum(ea_flags)

        sample_leak = (n_pii_leak > 0) or (n_ne_leak > 0)

        pii_total += n_pii
        pii_leaked += n_pii_leak
        ne_total += n_ne
        ne_leaked += n_ne_leak
        ea_total += n_ea
        ea_hit += n_ea_hit
        if (n_pii + n_ne) > 0:
            sample_with_any_item += 1
            if sample_leak:
                sample_leaked += 1

        rows.append({
            "index": int(_get(ei, "index", i) or i),
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

    # ------------------------- aggregate metrics -------------------------
    # Sample-level leak rate is reported over the full dataset and also
    # over samples that have at least one pii/ne item (more meaningful).
    sample_rate_full = sample_leaked / n if n else 0.0
    sample_rate_eligible = (
        sample_leaked / sample_with_any_item if sample_with_any_item else 0.0
    )
    pii_rate = pii_leaked / pii_total if pii_total else 0.0
    ne_rate = ne_leaked / ne_total if ne_total else 0.0
    ea_retention = ea_hit / ea_total if ea_total else 0.0

    print("\n=== Privacy leakage evaluation ===")
    print(f"  total samples                : {n}")
    print(f"  samples with >=1 pii/ne item : {sample_with_any_item}")
    print(f"  leaked samples               : {sample_leaked}")
    print(
        f"  sample-level leak rate (full)    : {sample_rate_full:.4f}"
        f"  ({sample_leaked}/{n})"
    )
    print(
        f"  sample-level leak rate (eligible): {sample_rate_eligible:.4f}"
        f"  ({sample_leaked}/{sample_with_any_item})"
    )
    print(
        f"  pii item leak rate           : {pii_rate:.4f}"
        f"  ({pii_leaked}/{pii_total})"
    )
    print(
        f"  ne  item leak rate           : {ne_rate:.4f}"
        f"  ({ne_leaked}/{ne_total})"
    )
    print(
        f"  ea  item retention rate      : {ea_retention:.4f}"
        f"  ({ea_hit}/{ea_total})"
    )
    print(f"  leak thresholds              : cov>={COV_THRESHOLD}, bertP>{BERT_THRESHOLD}")
    print(f"  ea retention thresholds      : cov>={EA_COV_THRESHOLD}, bertP>{EA_BERT_THRESHOLD}")
    print(f"  bertscore enabled            : {use_bert}")

    # ------------------------------ persist ------------------------------
    out_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    out_df.to_parquet(args.output, index=False)
    print(f"\n[save] per-row results -> {args.output}")


if __name__ == "__main__":
    main()
