"""
计算每条样本中 extra_info["key_spans"] 在 extra_info["query_gt"] 上的命中率。

输入  : /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_answer_label.parquet
输出  : /group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_hit_rate.parquet
       同时在 stdout 打印整体统计。

判定逻辑（与 命中.py 中的 utility 检查一致）：
  令 A = extra_info["query_gt"]
  对 key_spans 中的每个 span（已知是 str ndarray）：
      coverage = |tokens(A) ∩ tokens(span)| / |tokens(span)|
      p_rescaled = BERTScore P (cand=span, ref=A)，rescale_with_baseline=True
      hit = (coverage >= 0.5) or (p_rescaled >= 0.3)
  row_hit_rate = #hit / #spans
  miss 既未通过 Jaccard (Coverage < 0.5) 又未通过 BERTScore (P_rescaled < 0.3)。
"""

from __future__ import annotations

import os
import re
import copy
import argparse
from typing import Iterable, Any

import numpy as np
import pandas as pd
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Tokenizer / Coverage（与 命中.py 完全一致）
# ---------------------------------------------------------------------------
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "while", "is", "are", "was", "were",
    "be", "been", "being", "to", "of", "in", "on", "at", "for", "with", "by", "from",
    "as", "that", "this", "these", "those", "it", "its", "i", "me", "my", "we", "our",
    "you", "your", "he", "she", "they", "them", "his", "her", "their",
    "do", "does", "did", "have", "has", "had", "can", "could", "would", "should",
    "will", "shall", "may", "might", "not", "no", "so", "than", "then", "there",
    "some", "any", "all", "more", "most", "much", "many",
}


def _tokenize(text: str) -> list:
    toks = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
    return [t for t in toks if t not in STOPWORDS]


def coverage(a: str, b: str) -> float:
    """|tokens(A) ∩ tokens(B)| / |tokens(B)|: B 中有多少比例的词被 A 覆盖。"""
    sa, sb = set(_tokenize(a)), set(_tokenize(b))
    if not sb:
        return 0.0
    return len(sa & sb) / len(sb)


# ---------------------------------------------------------------------------
# BERTScorer 单例（与 命中.py 一致：roberta-large + rescale_with_baseline=True）
# ---------------------------------------------------------------------------
_BERT_SCORER = None
_BERT_LOAD_ERROR: Exception | None = None

DEFAULT_ROBERTA_LARGE_PATH = os.environ.get(
    "PRIV_BERTSCORE_MODEL_PATH",
    "/group/40047/eiraxyhuang/workspace/fc/DataG/model_hf/roberta-large",
)


def _get_bert_scorer():
    global _BERT_SCORER, _BERT_LOAD_ERROR
    if _BERT_SCORER is not None or _BERT_LOAD_ERROR is not None:
        return _BERT_SCORER
    try:
        import bert_score

        baseline_path = os.path.join(
            os.path.dirname(bert_score.__file__),
            "rescale_baseline",
            "en",
            "roberta-large.tsv",
        )
        _BERT_SCORER = bert_score.BERTScorer(
            model_type=DEFAULT_ROBERTA_LARGE_PATH,
            num_layers=17,
            lang="en",
            rescale_with_baseline=True,
            baseline_path=baseline_path,
        )
        print(f"[load] BERTScorer ready: {DEFAULT_ROBERTA_LARGE_PATH}")
    except Exception as e:
        _BERT_LOAD_ERROR = e
        _BERT_SCORER = None
        print(f"[error] BERTScorer load failed: {e!r}")
    return _BERT_SCORER


def _bert_p_rescaled_batch(cands: list, refs: list) -> list:
    """对成对的 (cand, ref) 计算 BERTScore P_rescaled。

    cands、refs 必须等长。模型加载失败或调用失败时返回 [0.0]*len(cands)。
    """
    assert len(cands) == len(refs)
    if not cands:
        return []
    scorer = _get_bert_scorer()
    if scorer is None:
        return [0.0] * len(cands)
    try:
        P, _, _ = scorer.score(cands=list(cands), refs=list(refs))
        return [float(x) for x in P.tolist()]
    except Exception as e:
        print(f"[error] BERTScore.score failed: {e!r}")
        return [0.0] * len(cands)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _to_str_list(x: Any) -> list:
    """把 list / numpy.ndarray 等统一成 list[str]，过滤空值。"""
    if x is None:
        return []
    if isinstance(x, str):
        return [x] if x.strip() else []
    if isinstance(x, np.ndarray):
        x = x.tolist()
    if isinstance(x, Iterable):
        out = []
        for it in x:
            if it is None:
                continue
            s = str(it).strip()
            if s:
                out.append(s)
        return out
    return [str(x)]


def _to_dict(x):
    if isinstance(x, dict):
        return x
    if x is None:
        return {}
    try:
        return dict(x)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Per-row key_spans hit-rate against query_gt (Jaccard coverage + BERTScore)."
    )
    parser.add_argument(
        "--input",
        default="/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_answer_label.parquet",
    )
    parser.add_argument(
        "--output",
        default="/group/40047/eiraxyhuang/workspace/fc/DataG/med_new/med.anonymized.cleaned.with_hit_rate.parquet",
    )
    parser.add_argument("--cov-threshold", type=float, default=0.5,
                        help="Jaccard coverage threshold (>= passes).")
    parser.add_argument("--bert-threshold", type=float, default=0.3,
                        help="BERTScore P_rescaled threshold (>= passes).")
    parser.add_argument("--bert-batch-size", type=int, default=128,
                        help="Batch size for BERTScore scoring.")
    parser.add_argument("--limit-rows", type=int, default=0,
                        help="Only process the first N rows (0 = all).")
    args = parser.parse_args()

    print(f"Loading parquet: {args.input}")
    df = pd.read_parquet(args.input)
    print(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}")

    if args.limit_rows and args.limit_rows < len(df):
        df = df.iloc[: args.limit_rows].reset_index(drop=True)
        print(f"Truncated to first {len(df)} rows for debug.")

    # 1) 收集所有 (row_idx, span_idx, span, query_gt)
    row_records = []   # list of dict per row
    flat_cands = []    # span 文本
    flat_refs = []     # 对应的 query_gt
    flat_back = []     # (row_idx, span_idx)

    for row_idx, ei in enumerate(df["extra_info"].tolist()):
        d = _to_dict(ei)
        qgt = str(d.get("query_gt", "") or "")
        spans = _to_str_list(d.get("key_spans"))
        row_records.append({
            "query_gt": qgt,
            "spans": spans,
            "covs": [0.0] * len(spans),
            "p_rs": [0.0] * len(spans),
            "hits": [False] * len(spans),
            "skipped": (not qgt) or (len(spans) == 0),
            "skip_reason": (
                "no_query_gt" if not qgt else
                "no_spans" if len(spans) == 0 else ""
            ),
        })
        if not qgt or not spans:
            continue
        for s_idx, sp in enumerate(spans):
            flat_cands.append(sp)
            flat_refs.append(qgt)
            flat_back.append((row_idx, s_idx))

    print(f"Total spans to score: {len(flat_cands)} (across {len(row_records)} rows)")

    # 2) Jaccard coverage（轻量，整体跑）
    for (row_idx, s_idx), sp, ref in zip(flat_back, flat_cands, flat_refs):
        row_records[row_idx]["covs"][s_idx] = coverage(ref, sp)

    # 3) BERTScore P_rescaled（按批次）
    p_rescaled_all = []
    if flat_cands:
        # 触发模型加载
        _get_bert_scorer()
        bs = max(1, args.bert_batch_size)
        for start in tqdm(range(0, len(flat_cands), bs), desc="BERTScore"):
            cands_b = flat_cands[start:start + bs]
            refs_b = flat_refs[start:start + bs]
            p_rescaled_all.extend(_bert_p_rescaled_batch(cands_b, refs_b))

    for (row_idx, s_idx), p in zip(flat_back, p_rescaled_all):
        row_records[row_idx]["p_rs"][s_idx] = p

    # 4) 计算命中
    cov_th = args.cov_threshold
    bert_th = args.bert_threshold

    hit_rates = []          # 每一行（仅限 spans>0 且有 query_gt）的命中率
    miss_counts = []
    total_spans = 0
    total_hits = 0
    total_miss = 0
    rows_all_hit = 0
    rows_all_miss = 0
    rows_considered = 0

    for rec in row_records:
        if rec["skipped"]:
            continue
        rows_considered += 1
        n = len(rec["spans"])
        n_hit = 0
        for i in range(n):
            cov = rec["covs"][i]
            p = rec["p_rs"][i]
            hit = (cov >= cov_th) or (p >= bert_th)
            rec["hits"][i] = hit
            if hit:
                n_hit += 1
        n_miss = n - n_hit
        rec["n_total"] = n
        rec["n_hit"] = n_hit
        rec["n_miss"] = n_miss
        rec["hit_rate"] = n_hit / n if n > 0 else 0.0
        hit_rates.append(rec["hit_rate"])
        miss_counts.append(n_miss)
        total_spans += n
        total_hits += n_hit
        total_miss += n_miss
        if n > 0 and n_hit == n:
            rows_all_hit += 1
        if n > 0 and n_hit == 0:
            rows_all_miss += 1

    # 5) 写回 extra_info
    new_extra_infos = []
    for ei, rec in zip(df["extra_info"].tolist(), row_records):
        new_ei = copy.deepcopy(ei) if isinstance(ei, dict) else _to_dict(ei)
        spans = rec["spans"]
        details = []
        for i in range(len(spans)):
            details.append({
                "span": spans[i],
                "coverage": float(rec["covs"][i]) if not rec["skipped"] else 0.0,
                "p_rescaled": float(rec["p_rs"][i]) if not rec["skipped"] else 0.0,
                "hit": bool(rec["hits"][i]) if not rec["skipped"] else False,
            })
        new_ei["key_spans_hit_check"] = {
            "query_gt_used": rec["query_gt"],
            "cov_threshold": cov_th,
            "bert_threshold": bert_th,
            "n_total": len(spans),
            "n_hit": rec.get("n_hit", 0),
            "n_miss": rec.get("n_miss", 0),
            "hit_rate": rec.get("hit_rate", 0.0),
            "skipped": rec["skipped"],
            "skip_reason": rec["skip_reason"],
            "details": details,
        }
        new_extra_infos.append(new_ei)

    df["extra_info"] = new_extra_infos
    df["key_spans_hit_rate"] = [
        rec.get("hit_rate", float("nan")) if not rec["skipped"] else float("nan")
        for rec in row_records
    ]
    df["key_spans_miss_count"] = [
        rec.get("n_miss", 0) if not rec["skipped"] else 0
        for rec in row_records
    ]

    # 6) 打印总览
    print()
    print("================ Summary ================")
    print(f"rows                         : {len(df)}")
    print(f"rows considered (qgt+spans)  : {rows_considered}")
    print(f"rows skipped                 : {len(df) - rows_considered}")
    print(f"thresholds                   : coverage>={cov_th}, p_rescaled>={bert_th}")
    print(f"total spans                  : {total_spans}")
    print(f"total hits                   : {total_hits}")
    print(f"total miss                   : {total_miss}")
    if total_spans > 0:
        print(f"micro hit-rate (span-level)  : {total_hits/total_spans:.4f}")
    if hit_rates:
        print(f"macro hit-rate (mean per row): {float(np.mean(hit_rates)):.4f}")
        print(f"per-row hit-rate median      : {float(np.median(hit_rates)):.4f}")
        print(f"per-row hit-rate min / max   : {min(hit_rates):.4f} / {max(hit_rates):.4f}")
        # 分桶
        buckets = [0.0, 0.25, 0.5, 0.75, 1.0]
        labels = ["[0.00,0.25)", "[0.25,0.50)", "[0.50,0.75)", "[0.75,1.00)", "==1.00"]
        counts = [0] * 5
        for r in hit_rates:
            if r >= 1.0: counts[4] += 1
            elif r >= 0.75: counts[3] += 1
            elif r >= 0.5:  counts[2] += 1
            elif r >= 0.25: counts[1] += 1
            else:           counts[0] += 1
        print("per-row hit-rate distribution:")
        for lab, c in zip(labels, counts):
            print(f"  {lab:<14}: {c} ({c/len(hit_rates):.2%})")
        print(f"rows fully hit (rate==1.0)   : {rows_all_hit} ({rows_all_hit/rows_considered:.2%})")
        print(f"rows fully miss (rate==0.0)  : {rows_all_miss} ({rows_all_miss/rows_considered:.2%})")

    print()
    print(f"Writing parquet: {args.output}")
    df.to_parquet(args.output, index=False)
    print("Saved.")


if __name__ == "__main__":
    main()
