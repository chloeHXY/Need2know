#!/usr/bin/env python3
"""PII-tag the nonessential spans of samples in a JSONL file.

For each input record, take the spans listed under
``judge_out.nonessential_attributes`` and ask an LLM to classify EACH span
as either ``PII`` or ``NON_PII`` given the original ``raw_prompt`` as
context. The taxonomy / instructions come straight from ``todo.md``.

Output JSONL fields per line:
    id              : original record id
    raw_prompt      : original raw_prompt
    ne_spans        : list[str], the original nonessential_attributes
    pii             : list[str], spans (or minimal substrings) judged PII
    light_keep      : list[str], spans (or remainders) judged NON_PII
    model_raw       : the raw LLM JSON string (for debugging)
    endpoint        : which model endpoint answered
    error           : present only if the call / parsing failed

Example:
    python scripts/pii_tag.py \
        --config config/default.yaml \
        --input  data/small.jsonl \
        --output data/small.pii.jsonl \
        --n 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make ``synth`` importable when invoking the script directly.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # type: ignore

from synth.llm_client import (
    build_client_from_config,
    format_usage_table,
    merge_usage_summaries,
)


# ---------------------------------------------------------------------------
# Prompt (verbatim from todo.md, with <<<RAW_PROMPT>>> as the only template
# slot). We append the ne-spans list inline so the model knows the exact
# strings it must classify.
# ---------------------------------------------------------------------------
PII_PROMPT_TEMPLATE = """You are a privacy-labeling assistant.

Given a user query, extract:
1. Minimal spans that are PII.
2. A small number of useful NON-PII context spans that should be kept in a light/redacted version.

Do NOT split or label the entire sentence token by token. Only extract meaningful spans.

Definition of PII:
A span is PII if it can, alone or when combined with a few public facts, help re-identify a specific individual.

PII includes:
- Specific person names
- Geographic units finer than country, such as city, street address, ZIP/postal code, neighborhood, or building name
- Specific organizations, such as employer, school, hospital, company, club, or institution names
- Contact information, such as email, phone number, URL, username, social handle, or profile link
- Dates more precise than year, exact ages, or ages >= 90
- Unique identifiers, such as SSN, passport number, account number, license plate, student ID, employee ID, medical record number
- Specific sensitive attributes that can identify or strongly profile a person, including exact diagnosis, specific religion/sect, specific sexual identity label, specific political party affiliation, or precise legal/medical status

NON-PII light_keep includes:
Useful but non-identifying context, such as:
- Generic relationships: my dad, my coworker, my teacher
- Generic occupations or roles: doctor, student, former police officer
- Hobbies, preferences, emotions, or general life context
- Coarse locations: a major city, a small town, another country
- Vague time references: last summer, a few years ago, recently
- General age bands: teenager, in his 70s, elderly
- General health or sensitive categories without specifics: a chronic illness, religious, politically active

Rules:
- Extract the shortest span that contains the PII. Do not include surrounding non-PII words unless necessary.
- If a phrase contains both PII and NON-PII, split it into minimal PII and useful NON-PII context.
  Example:
  Input: "my 74-year-old dad, a former police officer in Chicago"
  PII: ["74-year-old", "Chicago"]
  light_keep: ["my dad", "former police officer"]
- Do not include trivial filler words, punctuation, or duplicated spans.
- Do not over-extract. light_keep should contain only useful context, not every non-PII word.
- Preserve the original wording of extracted spans as much as possible.
- Return strict JSON only. No explanations, no markdown.

User query:
<<<RAW_PROMPT>>>

Output JSON format:
{"pii": [...], "light_keep": [...]}
"""
# PII_PROMPT_TEMPLATE = """You are a privacy-labeling assistant. Given a user query and a list of
# non-essential information spans extracted from it, classify EACH span
# as either PII or NON_PII.

# A span is PII if it can - alone or combined with a few public facts -
# re-identify a specific individual. Use this taxonomy:

# PII (replace in light mode):
# - Specific person names
# - Geographic units finer than country (city, address, ZIP)
# - Specific organizations (employer, school, hospital, company names)
# - Contact info (email, phone, URL, social handle)
# - Dates more precise than year, ages >= 90, or exact ages
# - Unique IDs (SSN, account, license plate, medical record numbers)
# - Specific sensitive attributes per GDPR Art.9: exact diagnosis,
#   specific religion/sect, specific sexual identity label, specific
#   party affiliation

# NON_PII (keep in light mode - these are flavor/context, not identifiers):
# - Generic relations (my dad, my coworker)
# - Generic occupations / hobbies / emotional states
# - Coarse categories (a chronic illness, religious, a major city)
# - Vague time references (last summer, a few years ago)
# - Generic age bands (in his 70s, teenager)

# A span that contains BOTH a PII token and a NON_PII token (e.g.
# "my 74-year-old dad, a former police officer in Chicago") must be
# split into the minimal PII substring(s) and the remainder. Return:
# - "pii":         list of strings that are PII (minimal spans)
# - "light_keep":  list of strings that are non-PII context

# Constraints:
# - Every token from the original ne spans must appear in exactly one
#   of pii / light_keep (modulo trivial whitespace).
# - Return strict JSON, no commentary.

# User query:
# <<<RAW_PROMPT>>>

# Non-essential spans to classify:
# <<<NE_SPANS>>>

# Output JSON:
# {"pii": [...], "light_keep": [...]}
# """


def build_prompt(raw_prompt: str, ne_spans: List[str]) -> str:
    spans_block = json.dumps(ne_spans, ensure_ascii=False, indent=2)
    return (
        PII_PROMPT_TEMPLATE
        .replace("<<<RAW_PROMPT>>>", raw_prompt)
        .replace("<<<NE_SPANS>>>", spans_block)
    )


# ---------------------------------------------------------------------------
# JSON extraction: the model is asked for strict JSON, but be defensive.
# ---------------------------------------------------------------------------
def parse_json_lenient(text: str) -> Dict[str, Any]:
    """Try ``json.loads`` directly; if that fails, slice the outermost {...}."""
    text = text.strip()
    # Strip ```json ... ``` fences if present.
    if text.startswith("```"):
        # remove leading fence
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: -3]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: slice from first '{' to last '}'.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise


# ---------------------------------------------------------------------------
# Per-record worker
# ---------------------------------------------------------------------------
async def tag_one(
    client,
    record: Dict[str, Any],
    *,
    use_json_mode: bool,
    temperature: Optional[float],
) -> Dict[str, Any]:
    rid = record.get("id", "")
    raw_prompt: str = record.get("raw_prompt", "") or ""
    judge_out = record.get("judge_out", {}) or {}
    ne_spans: List[str] = list(judge_out.get("nonessential_attributes", []) or [])

    base_out: Dict[str, Any] = {
        "id": rid,
        "raw_prompt": raw_prompt,
        "ne_spans": ne_spans,
    }

    if not ne_spans:
        # Nothing to tag.
        base_out.update({"pii": [], "light_keep": [], "endpoint": None, "model_raw": ""})
        return base_out

    prompt = build_prompt(raw_prompt, ne_spans)
    messages = [
        {"role": "system", "content": "You are a precise privacy-labeling assistant. Always return strict JSON."},
        {"role": "user", "content": prompt},
    ]
    response_format = {"type": "json_object"} if use_json_mode else None

    try:
        resp = await client.chat(
            messages,
            temperature=temperature,
            response_format=response_format,
        )
    except Exception as exc:  # noqa: BLE001
        base_out.update({"pii": [], "light_keep": [], "error": f"chat_failed: {exc!r}"})
        return base_out

    text = resp.get("text", "") or ""
    base_out["endpoint"] = resp.get("endpoint")
    base_out["model_raw"] = text

    try:
        parsed = parse_json_lenient(text)
    except Exception as exc:  # noqa: BLE001
        base_out.update({"pii": [], "light_keep": [], "error": f"parse_failed: {exc!r}"})
        return base_out

    pii = parsed.get("pii", []) or []
    light_keep = parsed.get("light_keep", []) or []
    # Coerce to list[str].
    base_out["pii"] = [str(x) for x in pii]
    base_out["light_keep"] = [str(x) for x in light_keep]
    return base_out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _read_jsonl(path: str, n: Optional[int]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
            if n is not None and len(out) >= n:
                break
    return out


async def amain() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--input", default="data/small.jsonl")
    ap.add_argument("--output", default="data/small.pii.jsonl")
    ap.add_argument("--n", type=int, default=10, help="number of records to tag")
    ap.add_argument(
        "--client",
        default="judge",
        choices=["judge", "reformulator", "generator"],
        help="which client section in the YAML config to use for the LLM call",
    )
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument(
        "--no-json-mode",
        action="store_true",
        help="disable response_format=json_object (some endpoints don't support it)",
    )
    args = ap.parse_args()

    cfg = _load_yaml(args.config)
    if args.client not in cfg:
        raise SystemExit(f"config has no '{args.client}' section")

    client = build_client_from_config(cfg[args.client])

    records = _read_jsonl(args.input, args.n)
    print(f"[info] loaded {len(records)} records from {args.input}", flush=True)
    print(f"[info] using client section '{args.client}' with concurrency={args.concurrency}", flush=True)

    sem = asyncio.Semaphore(args.concurrency)
    use_json_mode = not args.no_json_mode

    async def _bound(rec):
        async with sem:
            return await tag_one(
                client,
                rec,
                use_json_mode=use_json_mode,
                temperature=args.temperature,
            )

    t0 = time.time()
    results: List[Dict[str, Any]] = []
    try:
        tasks = [asyncio.create_task(_bound(r)) for r in records]
        for i, fut in enumerate(asyncio.as_completed(tasks), 1):
            res = await fut
            results.append(res)
            tag = "ERR" if "error" in res else "OK"
            print(
                f"  [{i}/{len(tasks)}] {tag} id={res.get('id','')} "
                f"pii={len(res.get('pii', []))} keep={len(res.get('light_keep', []))}",
                flush=True,
            )
    finally:
        usage = merge_usage_summaries([(args.client, client)])
        await client.aclose()

    # Preserve input order on output.
    order = {r.get("id", ""): i for i, r in enumerate(records)}
    results.sort(key=lambda x: order.get(x.get("id", ""), 0))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    elapsed = time.time() - t0
    n_err = sum(1 for r in results if "error" in r)
    print()
    print(f"=== PII tagging done in {elapsed:.1f}s ===")
    print(f"  records : {len(results)}")
    print(f"  errors  : {n_err}")
    print(f"  output  : {os.path.abspath(out_path)}")
    print()
    print("=== LLM usage & cost ===")
    print(format_usage_table(usage))


if __name__ == "__main__":
    asyncio.run(amain())
