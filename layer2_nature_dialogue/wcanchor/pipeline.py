"""End-to-end orchestrator for the natural-anchor pipeline.

Stages run sequentially, each writes its own jsonl checkpoint under
``cfg.pipeline.stage_dir`` so any stage can be re-run in isolation.

Stage outputs (default paths)::

    data/stages/00_loaded.jsonl       S0
    data/stages/01_struct.jsonl       S1 (main)
    data/stages/01_struct_anchor.jsonl S1 (redacted anchor pool)
    data/stages/02_screen.jsonl        S2+S3
    data/stages/03_screen_passed.jsonl S2+S3 filtered
    data/stages/04_judge_a.jsonl       S4
    data/stages/05_judge_b.jsonl       S5 -- both judges populated
    data/stages/06_concord.jsonl       S5 -- with concord field
    data/stages/07_unified.jsonl       S6
    data/stages/08_reformulated.jsonl  S7
    data/final/wildchat_anchor.eval.jsonl     all PASS rows (eval-only)
    data/final/wildchat_anchor.public.jsonl   sanitized version (S9)
    data/final/report.md                       S10
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml

from . import (
    LLMClient,
    build_client_from_config,
    build_embedding_client_from_config,
)
from ._jsonio import read_jsonl, write_jsonl
from .annotate_ci import AnnotateConfig, annotate
from .concord import ConcordConfig, all_concord_strings, compute_concord
from .ethical import EthicalConfig, sanitize_all
from .filter_struct import StructFilterConfig, filter_records
from . import load as load_mod
from .reformulate import ReformulateConfig, reformulate
from .screen import ScreenConfig, screen_records
from .stats import annotate_distribution, funnel, render_markdown
from .unify import unify_all


# ---------------------------------------------------------------------------
# Config glue
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    stage_dir: str = "nature_data_syn/data/stages"
    final_dir: str = "nature_data_syn/data/final"
    concurrency: int = 16
    stop_after: str = ""           # "" | "load" | "struct" | "screen" | "judge_a" | ...
    final_status_keep: Tuple[str, ...] = ("PASS",)
    sanitizer_salt: str = ""


def _load_yaml(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _stage_path(cfg: PipelineConfig, name: str) -> str:
    return os.path.join(cfg.stage_dir, name)


def _load_or_run(path: str) -> List[Dict[str, Any]]:
    return list(read_jsonl(path))


# ---------------------------------------------------------------------------
# Async per-stage drivers
# ---------------------------------------------------------------------------

async def _run_screen(records, full_cfg, pcfg):
    client = build_client_from_config(full_cfg.get("screen", {}))
    try:
        scfg = ScreenConfig(
            keep_content_types=tuple(full_cfg.get("screen", {}).get(
                "keep_content_types",
                ["first_person_task", "third_party_about", "mixed"])),
            require_ci_concern=full_cfg.get("screen", {}).get("require_ci_concern", True),
            use_json_mode=full_cfg.get("screen", {}).get("use_json_mode", True),
            concurrency=pcfg.concurrency,
        )
        return await screen_records(client, records, scfg)
    finally:
        await client.aclose()


async def _run_annotate(records, full_cfg, pcfg, *, judge_key: str, field_name: str):
    client = build_client_from_config(full_cfg.get(judge_key, {}))
    try:
        acfg = AnnotateConfig(
            use_json_mode=full_cfg.get(judge_key, {}).get("use_json_mode", True),
            concurrency=pcfg.concurrency,
            field_name=field_name,
        )
        return await annotate(client, records, acfg)
    finally:
        await client.aclose()


async def _run_concord(records, full_cfg, pcfg):
    cc_cfg_raw = full_cfg.get("concord", {})
    cc_cfg = ConcordConfig(
        pass_ne_iou=cc_cfg_raw.get("pass_ne_iou", 0.6),
        pass_e_iou=cc_cfg_raw.get("pass_e_iou", 0.6),
        pass_require_domain_match=cc_cfg_raw.get("pass_require_domain_match", True),
        soft_ne_iou=cc_cfg_raw.get("soft_ne_iou", 0.4),
        soft_e_iou=cc_cfg_raw.get("soft_e_iou", 0.4),
        matcher_token_threshold=cc_cfg_raw.get("matcher_token_threshold", 0.5),
        matcher_cosine_threshold=cc_cfg_raw.get("matcher_cosine_threshold", 0.65),
    )
    emb_cli = build_embedding_client_from_config(full_cfg.get("embeddings"))
    embeddings: Optional[Dict[str, list]] = None
    try:
        if emb_cli is not None:
            uniq: List[str] = []
            seen = set()
            for rec in records:
                for s in all_concord_strings(rec):
                    if s not in seen:
                        seen.add(s)
                        uniq.append(s)
            if uniq:
                vecs = await emb_cli.embed(uniq)
                embeddings = dict(zip(uniq, vecs))
    finally:
        if emb_cli is not None:
            await emb_cli.aclose()

    out = []
    for rec in records:
        rec = dict(rec)
        rec["concord"] = compute_concord(rec, cc_cfg, embeddings=embeddings)
        out.append(rec)
    return out


async def _run_reformulate(records, full_cfg, pcfg):
    client = build_client_from_config(full_cfg.get("reformulator", {}))
    try:
        rcfg = ReformulateConfig(concurrency=pcfg.concurrency, skip_hard=True)
        return await reformulate(client, records, rcfg)
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------

@dataclass
class StagePaths:
    loaded: str
    struct: str
    struct_anchor: str
    screen_all: str
    screen_passed: str
    judge_a: str
    judge_b: str
    concord: str
    unified: str
    reformulated: str
    final_eval: str
    final_public: str
    report: str


def _build_paths(cfg: PipelineConfig) -> StagePaths:
    sd = cfg.stage_dir
    fd = cfg.final_dir
    return StagePaths(
        loaded=os.path.join(sd, "00_loaded.jsonl"),
        struct=os.path.join(sd, "01_struct.jsonl"),
        struct_anchor=os.path.join(sd, "01_struct_anchor.jsonl"),
        screen_all=os.path.join(sd, "02_screen.jsonl"),
        screen_passed=os.path.join(sd, "03_screen_passed.jsonl"),
        judge_a=os.path.join(sd, "04_judge_a.jsonl"),
        judge_b=os.path.join(sd, "05_judge_b.jsonl"),
        concord=os.path.join(sd, "06_concord.jsonl"),
        unified=os.path.join(sd, "07_unified.jsonl"),
        reformulated=os.path.join(sd, "08_reformulated.jsonl"),
        final_eval=os.path.join(fd, "wildchat_anchor.eval.jsonl"),
        final_public=os.path.join(fd, "wildchat_anchor.public.jsonl"),
        report=os.path.join(fd, "report.md"),
    )


async def run(yaml_path: str, *, limit: Optional[int] = None) -> Dict[str, Any]:
    full = _load_yaml(yaml_path)
    pipe_cfg_raw = full.get("pipeline", {})
    pcfg = PipelineConfig(
        stage_dir=pipe_cfg_raw.get("stage_dir", "nature_data_syn/data/stages"),
        final_dir=pipe_cfg_raw.get("final_dir", "nature_data_syn/data/final"),
        concurrency=pipe_cfg_raw.get("concurrency", 16),
        stop_after=pipe_cfg_raw.get("stop_after", ""),
        final_status_keep=tuple(pipe_cfg_raw.get("final_status_keep", ["PASS"])),
        sanitizer_salt=pipe_cfg_raw.get("sanitizer_salt", ""),
    )
    paths = _build_paths(pcfg)

    # ---- S0 load -------------------------------------------------------
    src = full.get("source", {})
    # Accept either ``parquet_path`` (single path, original) or
    # ``parquet_paths`` (list, for multi-shard runs). When both are given,
    # ``parquet_paths`` wins.
    parquet_paths = src.get("parquet_paths")
    if parquet_paths:
        if isinstance(parquet_paths, str):
            parquet_paths = [parquet_paths]
        parquet_arg = list(parquet_paths)
    else:
        parquet_arg = src.get("parquet_path")
    if not os.path.exists(paths.loaded):
        n = load_mod.run(parquet_arg, paths.loaded)
        print(f"[S0] loaded {n} rows -> {paths.loaded}")
    if pcfg.stop_after == "load":
        return {"paths": paths.__dict__}

    # ---- S1 structural filter -----------------------------------------
    if not os.path.exists(paths.struct):
        sfg = StructFilterConfig(
            word_min=full.get("struct_filter", {}).get("word_min", 25),
            word_max=full.get("struct_filter", {}).get("word_max", 2500),
            single_turn_only=full.get("struct_filter", {}).get("single_turn_only", True),
            drop_toxic=full.get("struct_filter", {}).get("drop_toxic", True),
            languages=tuple(src.get("languages", ["English"])),
            redacted_route=full.get("struct_filter", {}).get("redacted_route", "anchor_pool"),
        )
        records = list(read_jsonl(paths.loaded))
        kept, anchors = filter_records(records, sfg)
        write_jsonl(kept, paths.struct)
        write_jsonl(anchors, paths.struct_anchor)
        print(f"[S1] structural filter: kept {len(kept)} (+{len(anchors)} anchors)")
    if pcfg.stop_after == "struct":
        return {"paths": paths.__dict__}

    # ---- S2+S3 screen --------------------------------------------------
    if not os.path.exists(paths.screen_passed):
        records = list(read_jsonl(paths.struct))
        if limit:
            records = records[:limit]
        records = await _run_screen(records, full, pcfg)
        write_jsonl(records, paths.screen_all)
        passed = [r for r in records if r["screen"].get("passed")]
        write_jsonl(passed, paths.screen_passed)
        print(f"[S2+S3] screen: {len(passed)}/{len(records)} passed")
    if pcfg.stop_after == "screen":
        return {"paths": paths.__dict__}

    # ---- S4 judge_a ----------------------------------------------------
    if not os.path.exists(paths.judge_a):
        records = list(read_jsonl(paths.screen_passed))
        records = await _run_annotate(
            records, full, pcfg,
            judge_key="annotate_judge_a", field_name="judge_a",
        )
        write_jsonl(records, paths.judge_a)
        print(f"[S4] judge_a annotated: {len(records)}")
    if pcfg.stop_after == "judge_a":
        return {"paths": paths.__dict__}

    # ---- S5 judge_b + concord -----------------------------------------
    if not os.path.exists(paths.judge_b):
        records = list(read_jsonl(paths.judge_a))
        records = await _run_annotate(
            records, full, pcfg,
            judge_key="annotate_judge_b", field_name="judge_b",
        )
        write_jsonl(records, paths.judge_b)
        print(f"[S5a] judge_b annotated: {len(records)}")
    if not os.path.exists(paths.concord):
        records = list(read_jsonl(paths.judge_b))
        records = await _run_concord(records, full, pcfg)
        write_jsonl(records, paths.concord)
        from collections import Counter
        c = Counter((r.get("concord") or {}).get("status") for r in records)
        print(f"[S5b] concord: {dict(c)}")
    if pcfg.stop_after == "concord":
        return {"paths": paths.__dict__}

    # ---- S6 unify ------------------------------------------------------
    if not os.path.exists(paths.unified):
        records = list(read_jsonl(paths.concord))
        unified = unify_all(records)
        write_jsonl(unified, paths.unified)
        print(f"[S6] unified rows: {len(unified)}")
    if pcfg.stop_after == "unify":
        return {"paths": paths.__dict__}

    # ---- S7 reformulate -----------------------------------------------
    if not os.path.exists(paths.reformulated):
        records = list(read_jsonl(paths.unified))
        # Reformulate operates on unified rows; use `raw_prompt`. We need the
        # consensus, which we re-fetch from the concord checkpoint.
        concord_by_id = {
            ("l2-" + r["id"]): r.get("concord")
            for r in read_jsonl(paths.concord)
        }
        # Augment unified rows with the original concord field so the
        # reformulator can read the consensus span lists.
        augmented = []
        for r in records:
            r = dict(r)
            r["first_user"] = r["raw_prompt"]
            r["concord"] = concord_by_id.get(r["id"])
            augmented.append(r)
        augmented = await _run_reformulate(augmented, full, pcfg)
        # Strip helper fields and merge back into unified rows.
        out = []
        for r in augmented:
            r = dict(r)
            r.pop("first_user", None)
            r.pop("concord", None)
            out.append(r)
        write_jsonl(out, paths.reformulated)
        print(f"[S7] reformulated: {len(out)}")
    if pcfg.stop_after == "reformulate":
        return {"paths": paths.__dict__}

    # ---- final: status filter + sanitize ------------------------------
    final_records = list(read_jsonl(paths.reformulated))
    final_keep = [
        r for r in final_records
        if (r.get("consistency") or {}).get("status") in pcfg.final_status_keep
    ]
    write_jsonl(final_keep, paths.final_eval)
    print(f"[final] eval-only set: {len(final_keep)}")

    eth_cfg_raw = full.get("ethical", {})
    eth = EthicalConfig(
        faker_locale=eth_cfg_raw.get("faker_locale", "en_US"),
        replace_attributes=tuple(eth_cfg_raw.get("replace_attributes",
            ["name", "email", "phone_number", "address", "ssn", "driver_license"])),
        drop_high_reidentification=eth_cfg_raw.get("drop_high_reidentification", True),
    )
    public, dropped = sanitize_all(final_keep, eth, salt=pcfg.sanitizer_salt)
    write_jsonl(public, paths.final_public)
    print(f"[final] public set after sanitize: {len(public)} (dropped {dropped} for high re-id risk)")

    # ---- S10 report ---------------------------------------------------
    rows = funnel({
        "S0 loaded":        paths.loaded,
        "S1 struct":        paths.struct,
        "S1 anchor pool":   paths.struct_anchor,
        "S2+3 screen pass": paths.screen_passed,
        "S4 judge_a":       paths.judge_a,
        "S5 judge_b":       paths.judge_b,
        "S5 concord":       paths.concord,
        "S6 unified":       paths.unified,
        "S7 reformulated":  paths.reformulated,
        "Final eval":       paths.final_eval,
        "Final public":     paths.final_public,
    })
    dist = annotate_distribution(paths.unified) if os.path.exists(paths.unified) else None
    md = render_markdown(rows, dist)
    os.makedirs(os.path.dirname(paths.report), exist_ok=True)
    with open(paths.report, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[S10] report -> {paths.report}")
    return {"paths": paths.__dict__, "report": paths.report}


def main(yaml_path: str, *, limit: Optional[int] = None) -> Dict[str, Any]:
    return asyncio.run(run(yaml_path, limit=limit))
