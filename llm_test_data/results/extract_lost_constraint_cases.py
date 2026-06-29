"""Extract representative lost_constraint cases from the judged outputs."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
FILES = {
    "Ours":     ROOT / "our_judged.parquet",
    "Papillon": ROOT / "papillon_judged.parquet",
    "Prediax":  ROOT / "prediax_judged.parquet",
}


def parse_json_field(x):
    if isinstance(x, dict):
        return x
    if isinstance(x, str) and x.strip():
        try:
            return json.loads(x)
        except Exception:
            return {}
    return {}


def get_question(row) -> str:
    """The original (un-rewritten) question lives in reward_model.ground_truth
    or extra_info.answer."""
    rm = row.get("reward_model")
    if isinstance(rm, dict) and rm.get("ground_truth"):
        return str(rm["ground_truth"])
    ei = row.get("extra_info")
    if isinstance(ei, dict) and ei.get("answer"):
        return str(ei["answer"])
    # Some columns may be stored as numpy/pandas dict-likes
    try:
        if rm is not None and "ground_truth" in rm:
            return str(rm["ground_truth"])
    except Exception:
        pass
    return ""


def extract(df: pd.DataFrame, system: str) -> list[dict]:
    out = []
    for _, row in df.iterrows():
        parsed = parse_json_field(row.get("judge_parsed"))
        issues = parsed.get("utility_issues") or []
        if not isinstance(issues, list):
            continue
        lost = [i for i in issues
                if isinstance(i, dict) and i.get("type") == "lost_constraint"]
        if not lost:
            continue
        out.append({
            "system":        system,
            "question":      get_question(row),
            "priv_query":    row.get("priv_query", ""),
            "lost_issues":   lost,
            "all_util":      issues,
            "utility_score": row.get("judge_utility_score"),
            "reid_risk":     row.get("judge_reid_risk"),
            "verdict":       row.get("judge_verdict"),
        })
    return out


def show(case: dict, idx: int) -> None:
    print(f"\n========== Case {idx} | system={case['system']} | "
          f"u={case['utility_score']} r={case['reid_risk']} "
          f"verdict={case['verdict']} ==========")
    q = str(case["question"]).replace("\n", " ")
    p = str(case["priv_query"]).replace("\n", " ")
    print(f"[question  ] {q[:500]}")
    print(f"[priv_query] {p[:500]}")
    for j, it in enumerate(case["lost_issues"], 1):
        print(f"  - lost_constraint #{j}")
        print(f"      span:   {str(it.get('span',''))[:200]}")
        print(f"      source: {str(it.get('source',''))[:200]}")
        print(f"      reason: {str(it.get('reason',''))[:300]}")


def main() -> None:
    by_system: dict[str, list[dict]] = {}
    for system, path in FILES.items():
        if not path.exists():
            print(f"missing: {path}")
            continue
        df = pd.read_parquet(path)
        cases = extract(df, system)
        print(f"{system}: {len(cases)} samples carry lost_constraint "
              f"(out of {len(df)})")
        by_system[system] = cases

    # Pick clean examples per system: only one utility issue (= lost_constraint),
    # short-ish, mid utility score.
    picked_idx = 0
    for system, cases in by_system.items():
        sub = [c for c in cases
               if len(c["all_util"]) == 1
               and c["utility_score"] is not None
               and 0.3 <= float(c["utility_score"]) <= 0.7
               and isinstance(c["question"], str) and 40 < len(c["question"]) < 400
               and isinstance(c["priv_query"], str) and 40 < len(c["priv_query"]) < 400
               and c["lost_issues"][0].get("source")
               and c["lost_issues"][0].get("reason")]
        # Prefer those whose `source` is short and concrete (a single attribute)
        sub.sort(key=lambda c: (len(str(c["lost_issues"][0].get("source",""))),
                                -float(c["utility_score"])))
        for c in sub[:3]:
            picked_idx += 1
            show(c, picked_idx)


if __name__ == "__main__":
    main()
