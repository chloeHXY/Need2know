# -*- coding: utf-8 -*-
"""
Find over-abstracted priv_query examples in step1_priv_query.parquet.

Definition of "over-abstracted":
  The original user question (extra_info['question']) carries a *concrete*
  payload -- e.g. a specific text to translate / summarize, a specific
  document, code snippet, dataset, numbers, named entities, or a very
  specific personal goal -- but the rewritten priv_query (q') has stripped
  almost all of that concreteness and turned the request into a generic
  "discuss / explore / provide an overview of <topic>" style prompt.

We score each privacy-ability row with several heuristic signals and rank
them. No model call is needed; this is a quick offline filter.

Usage:
    python find_over_abstract.py            # show top 20
    python find_over_abstract.py --topk 30 --out abstract.jsonl

用于短暂的case study
原始指令：在/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step1_priv_query.parquet中筛出一些ability为priv，
priv_query 相较于原问题extra_info['question'] ，明显过度抽象的例子
"""

import argparse
import json
import os
import re
import sys

import pandas as pd


INPUT_PATH = "/group/40047/eiraxyhuang/workspace/fc/DataG/papillon/step1_priv_query.parquet"


# ---------------------------------------------------------------------------
# Heuristic vocabularies
# ---------------------------------------------------------------------------

# Phrases that strongly suggest the rewritten query has been turned into a
# generic "give me an overview / framework" request.
ABSTRACT_PHRASES = [
    "general guidance",
    "general overview",
    "an overview of",
    "overview of the",
    "framework for",
    "a framework",
    "best practices",
    "key considerations",
    "factors to consider",
    "things to consider",
    "potential strategies",
    "various approaches",
    "different approaches",
    "common approaches",
    "typical approach",
    "explore the concept",
    "explore potential",
    "discuss the importance",
    "discuss the role",
    "discuss the concept",
    "discuss the various",
    "considerations for",
    "guidance on",
    "advice on",
    "tips for",
    "tips on",
    "high-level",
    "in general terms",
    "broadly speaking",
    "generally speaking",
    "comprehensive overview",
    "comprehensive guide",
    "ideal response should",
    "the response should",
    "should provide information on",
    "potential applications",
    "principles of",
    "fundamentals of",
]

# Phrases that signal the original query has a *concrete* payload that the
# privatised query is supposed to preserve.
CONCRETE_TASK_PATTERNS = [
    r"\btranslate\b",
    r"\bsummari[sz]e\b",
    r"\brewrite\b",
    r"\bproofread\b",
    r"\bedit (this|the following|my)\b",
    r"\bfix (this|the|my)\b",
    r"\bdebug\b",
    r"\bexplain (this|the following|my) code\b",
    r"\bwrite (a|an|the) (email|reply|response|message|letter|cover letter|essay)\b",
    r"\breply to\b",
    r"\brespond to\b",
    r"\bdraft (a|an|the)\b",
    r"\bcalculate\b",
    r"\bcompute\b",
    r"\bsolve\b",
    r"\bconvert\b",
    r"\bclassify\b",
    r"\bextract\b",
    r"\bparse\b",
    r"\bformat\b",
    r"\bhere'?s? (the|my|a)\b",
    r"\bhere is (the|my|a)\b",
    r"\bthis (paragraph|sentence|text|passage|email|message|code|snippet|document|article|paper|story|poem|essay|letter|recipe|prompt)\b",
    r"\bthe following (paragraph|sentence|text|passage|email|message|code|snippet|document|article|paper|story|poem|essay|letter|recipe|prompt)\b",
]

# Quick way to detect that the original query contains a quoted/embedded
# concrete artefact (a piece of text, code, numbers, etc.).
QUOTED_RE = re.compile(r"[\"'“”‘’][^\"'“”‘’]{12,}[\"'“”‘’]")
CODEBLOCK_RE = re.compile(r"```.+?```", re.DOTALL)
URL_RE = re.compile(r"https?://\S+")
NUMBER_RE = re.compile(r"\b\d{2,}\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _tokens(s: str):
    return re.findall(r"[a-zA-Z][a-zA-Z\-']+", s.lower())


def _content_tokens(s: str):
    """Tokens that are likely to carry information (>=4 chars, not a stopword)."""
    stop = {
        "the","a","an","and","or","but","of","to","for","with","on","in","at",
        "by","is","are","was","were","be","been","being","this","that","these",
        "those","it","its","as","from","into","about","like","such","also",
        "would","could","should","can","may","might","will","just","really",
        "very","more","most","some","any","all","one","two","three","there",
        "their","they","them","then","than","what","which","who","whom","whose",
        "how","why","when","where","while","because","so","if","not","no",
        "do","does","did","done","doing","have","has","had","having","get",
        "got","getting","make","made","making","want","need","know","think",
        "thinking","going","go","goes","went","said","say","says","told","tell",
        "telling","help","please","thanks","thank","hi","hey","hello","lol",
        "honestly","actually","like","stuff","things","thing","kind","sort",
        "rn","kinda","gonna","wanna","etc","etcetera","you","your","yours",
        "yourself","my","mine","me","i","im","ive","id","ill","weve","were",
        "we","our","ours","us",
    }
    return [t for t in _tokens(s) if len(t) >= 4 and t not in stop]


def score_row(question: str, priv: str) -> dict:
    """Return a dict of features + an overall over-abstraction score."""
    q_norm = _norm(question)
    p_norm = _norm(priv)

    feats = {
        "len_q": len(question or ""),
        "len_p": len(priv or ""),
        "abstract_phrase_hits": 0,
        "abstract_phrases": [],
        "concrete_task_hits": 0,
        "concrete_tasks": [],
        "q_has_quoted": bool(QUOTED_RE.search(question or "")),
        "q_has_code": bool(CODEBLOCK_RE.search(question or "")),
        "q_has_url": bool(URL_RE.search(question or "")),
        "q_has_email": bool(EMAIL_RE.search(question or "")),
        "q_has_phone": bool(PHONE_RE.search(question or "")),
        "q_numbers": len(NUMBER_RE.findall(question or "")),
        "p_has_quoted": bool(QUOTED_RE.search(priv or "")),
        "content_overlap": 0.0,
        "len_ratio": 0.0,
        "score": 0.0,
    }

    for ph in ABSTRACT_PHRASES:
        if ph in p_norm:
            feats["abstract_phrase_hits"] += 1
            feats["abstract_phrases"].append(ph)

    for pat in CONCRETE_TASK_PATTERNS:
        if re.search(pat, q_norm):
            feats["concrete_task_hits"] += 1
            feats["concrete_tasks"].append(pat)

    q_tokens = set(_content_tokens(question or ""))
    p_tokens = set(_content_tokens(priv or ""))
    if q_tokens:
        feats["content_overlap"] = len(q_tokens & p_tokens) / len(q_tokens)
    if feats["len_q"]:
        feats["len_ratio"] = feats["len_p"] / feats["len_q"]

    # ---------- aggregate score ----------
    score = 0.0
    # 1. Generic / overview phrasing in priv_query.
    score += 2.0 * feats["abstract_phrase_hits"]
    # 2. Concrete task in original (translate/summarize/fix/...).
    if feats["concrete_task_hits"] > 0:
        score += 2.0
    # 3. Original carried a concrete artefact that priv_query dropped.
    if feats["q_has_quoted"] and not feats["p_has_quoted"]:
        score += 3.0
    if feats["q_has_code"] and "code" not in p_norm:
        score += 2.0
    if feats["q_has_url"] and not URL_RE.search(priv or ""):
        score += 1.0
    if feats["q_has_email"] and not EMAIL_RE.search(priv or ""):
        score += 1.0
    if feats["q_has_phone"] and not PHONE_RE.search(priv or ""):
        score += 1.0
    if feats["q_numbers"] >= 2 and not NUMBER_RE.search(priv or ""):
        score += 1.0
    # 4. Heavy content loss (low overlap of informative tokens).
    if feats["content_overlap"] < 0.15:
        score += 2.0
    elif feats["content_overlap"] < 0.25:
        score += 1.0
    # 5. Length collapse on a long original.
    if feats["len_q"] >= 400 and feats["len_ratio"] < 0.35:
        score += 1.5
    elif feats["len_q"] >= 250 and feats["len_ratio"] < 0.4:
        score += 0.5

    feats["score"] = round(score, 2)
    return feats


def get_question(extra_info) -> str:
    if isinstance(extra_info, dict):
        return extra_info.get("question", "") or ""
    try:
        return extra_info["question"] or ""
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=INPUT_PATH)
    ap.add_argument("--ability", default="privacy",
                    help="ability value to filter on (default: privacy)")
    ap.add_argument("--topk", type=int, default=20)
    ap.add_argument("--min-score", type=float, default=4.0,
                    help="only print rows with score >= this")
    ap.add_argument("--out", default="",
                    help="optional jsonl path to dump the selected examples")
    args = ap.parse_args()

    df = pd.read_parquet(args.input)
    if "ability" not in df.columns:
        print("[err] missing ability column", file=sys.stderr)
        sys.exit(1)

    sub = df[df["ability"] == args.ability].reset_index(drop=True)
    print(f"[info] total rows: {len(df)}, ability=={args.ability}: {len(sub)}")
    if sub.empty:
        return

    rows = []
    for i, r in sub.iterrows():
        q = get_question(r.get("extra_info"))
        p = r.get("priv_query") or ""
        if not isinstance(p, str) or p.startswith("[ERROR]"):
            continue
        if not q.strip() or not p.strip():
            continue
        feats = score_row(q, p)
        rows.append({
            "row_index_in_subset": int(i),
            "question": q,
            "priv_query": p,
            **feats,
        })

    rows.sort(key=lambda x: x["score"], reverse=True)

    selected = [r for r in rows if r["score"] >= args.min_score][: args.topk]
    print(f"[info] candidates with score>={args.min_score}: "
          f"{sum(1 for r in rows if r['score'] >= args.min_score)} "
          f"(showing top {len(selected)})")
    print()

    for rank, r in enumerate(selected, 1):
        print("=" * 90)
        print(f"#{rank}  score={r['score']}  "
              f"len_q={r['len_q']} len_p={r['len_p']} "
              f"len_ratio={r['len_ratio']:.2f} "
              f"overlap={r['content_overlap']:.2f}  "
              f"abstract_hits={r['abstract_phrase_hits']} "
              f"concrete_task={r['concrete_task_hits']} "
              f"q_quoted={r['q_has_quoted']} q_code={r['q_has_code']} "
              f"q_email={r['q_has_email']} q_phone={r['q_has_phone']}")
        if r["abstract_phrases"]:
            print(f"  abstract phrases : {r['abstract_phrases']}")
        if r["concrete_tasks"]:
            print(f"  concrete patterns: {r['concrete_tasks']}")
        print("--- ORIGINAL question ---")
        print(r["question"])
        print("--- priv_query ---")
        print(r["priv_query"])
        print()

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            for r in selected:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[save] wrote {len(selected)} examples -> {args.out}")


if __name__ == "__main__":
    main()
