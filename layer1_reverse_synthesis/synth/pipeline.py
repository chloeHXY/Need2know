"""End-to-end pipeline: spec -> raw_prompt -> judge -> reformulation -> JSONL.

Asynchronous, with bounded concurrency, partial-failure tolerance, and
checkpointed JSONL output (line-buffered, append-on-success).
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Iterable, Optional

from .llm_client import EmbeddingClient, LLMClient
from .prompts import (
    JUDGE_RESPONSE_FORMAT,
    build_generator_messages,
    build_judge_messages,
    build_reformulator_messages,
)
from .sampler import Sampler, Spec
from .judge import (
    MatcherConfig,
    _all_strings_to_embed,
    compute_consistency,
    parse_judge_output,
)


SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Pipeline config
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    concurrency: int = 16
    write_soft_fail: bool = True   # keep SOFT_FAIL rows (RL eval / hard-mining)
    write_hard_fail: bool = True   # keep HARD_FAIL rows (status-flagged)
    judge_use_json_mode: bool = True  # set False for endpoints that don't support it

    pass_threshold: float = 0.8
    soft_fail_threshold: float = 0.5

    # Per-stage retry counts (in addition to LLMClient.max_retries which
    # handles transport errors). These handle "weird" LLM outputs (e.g. the
    # generator returns a JSON blob instead of plain text).
    max_generation_retries: int = 2

    # Per-stage temperature overrides (None = use endpoint default).
    generator_temperature: Optional[float] = None
    reformulator_temperature: Optional[float] = 0.3
    judge_temperature: Optional[float] = 0.0

    # Matcher thresholds.
    matcher_token_threshold: float = 0.5
    matcher_cosine_threshold: float = 0.65


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _spec_to_jsonable(spec: Spec) -> Dict[str, Any]:
    return {
        "domain": spec.domain,
        "task": spec.task,
        "subject": spec.subject,
        "embedding_style": spec.embedding_style,
        "tone": spec.tone,
        "essential_policy": spec.essential_policy,
        "task_brief": spec.task_brief,
        "essential_info": [a.to_dict() for a in spec.essential_info],
        "nonessential_sensitive_info": [
            a.to_dict() for a in spec.nonessential_sensitive_info
        ],
        "confusion_kind": spec.confusion_kind,
        "notes": spec.notes,
    }


def _strip_quotes(s: str) -> str:
    s = s.strip()
    # Remove surrounding triple/single/double quotes if the model wrapped them.
    for q in ('"""', "'''", '"', "'"):
        if s.startswith(q) and s.endswith(q) and len(s) > 2 * len(q):
            s = s[len(q):-len(q)].strip()
    return s


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class Pipeline:
    """End-to-end orchestration. Stateless across samples."""

    def __init__(
        self,
        sampler: Sampler,
        generator: LLMClient,
        reformulator: LLMClient,
        judge: LLMClient,
        config: PipelineConfig,
        embedder: Optional[EmbeddingClient] = None,
    ) -> None:
        self.sampler = sampler
        self.generator = generator
        self.reformulator = reformulator
        self.judge = judge
        self.embedder = embedder
        self.config = config
        self._matcher_cfg = MatcherConfig(
            token_threshold=config.matcher_token_threshold,
            cosine_threshold=config.matcher_cosine_threshold,
        )

    # ---- single-sample stages ---------------------------------------------

    async def _generate_raw_prompt(self, spec: Spec) -> Dict[str, Any]:
        last_text = ""
        last_endpoint = ""
        for attempt in range(self.config.max_generation_retries + 1):
            messages = build_generator_messages(spec)
            out = await self.generator.chat(
                messages,
                temperature=self.config.generator_temperature,
            )
            text = _strip_quotes(out["text"])
            last_text, last_endpoint = text, out["endpoint"]
            if 20 <= len(text) <= 4000 and "{" not in text[:20]:
                # Reasonable: not too short, not a JSON-like wrapper.
                return {"text": text, "endpoint": out["endpoint"]}
        return {"text": last_text, "endpoint": last_endpoint}

    async def _judge_raw_prompt(self, raw_prompt: str) -> Dict[str, Any]:
        messages = build_judge_messages(raw_prompt)
        kwargs: Dict[str, Any] = {"temperature": self.config.judge_temperature}
        if self.config.judge_use_json_mode:
            kwargs["response_format"] = JUDGE_RESPONSE_FORMAT
        try:
            out = await self.judge.chat(messages, **kwargs)
        except Exception:
            # Some endpoints reject response_format; retry without.
            kwargs.pop("response_format", None)
            out = await self.judge.chat(messages, **kwargs)
        parsed = parse_judge_output(out["text"])
        parsed["_endpoint"] = out["endpoint"]
        return parsed

    async def _reformulate(self, raw_prompt: str, spec: Spec) -> Dict[str, Any]:
        messages = build_reformulator_messages(raw_prompt, spec)
        out = await self.reformulator.chat(
            messages, temperature=self.config.reformulator_temperature
        )
        return {"text": _strip_quotes(out["text"]), "endpoint": out["endpoint"]}

    # ---- single-sample top-level ------------------------------------------

    async def _maybe_embed(
        self, spec: Spec, judge_parsed: Dict[str, Any]
    ) -> Optional[Dict[str, list]]:
        if self.embedder is None:
            return None
        strings = _all_strings_to_embed(spec, judge_parsed)
        if not strings:
            return None
        try:
            vectors = await self.embedder.embed(strings)
        except Exception:
            # Embedding errors should not break synthesis; just skip the
            # semantic fallback for this row.
            return None
        return dict(zip(strings, vectors))

    async def synthesize_one(self, idx: int) -> Optional[Dict[str, Any]]:
        spec = self.sampler.sample()

        try:
            gen = await self._generate_raw_prompt(spec)
            raw_prompt = gen["text"]

            judge_parsed = await self._judge_raw_prompt(raw_prompt)
            embeddings = await self._maybe_embed(spec, judge_parsed)
            consistency = compute_consistency(
                spec,
                judge_parsed,
                pass_threshold=self.config.pass_threshold,
                soft_fail_threshold=self.config.soft_fail_threshold,
                embeddings=embeddings,
                matcher_cfg=self._matcher_cfg,
            )

            if consistency.status == "HARD_FAIL" and not self.config.write_hard_fail:
                return None
            if consistency.status == "SOFT_FAIL" and not self.config.write_soft_fail:
                return None

            reform = await self._reformulate(raw_prompt, spec)

            return {
                "id": f"l1-{idx:08d}",
                "spec": {
                    **_spec_to_jsonable(spec),
                    "generator_endpoint": gen["endpoint"],
                },
                "raw_prompt": raw_prompt,
                "judge_out": {
                    "primary_context": judge_parsed["primary_context"],
                    "essential_attributes": judge_parsed["essential_attributes"],
                    "nonessential_attributes": judge_parsed["nonessential_attributes"],
                    "judge_endpoint": judge_parsed.get("_endpoint", ""),
                },
                "consistency": consistency.to_dict(),
                "gold_reformulation": reform["text"],
                "meta": {
                    "created_at": _now_iso(),
                    "schema_version": SCHEMA_VERSION,
                    "reformulator_endpoint": reform["endpoint"],
                    "embeddings_used": embeddings is not None,
                },
            }
        except Exception as exc:
            return {
                "id": f"l1-{idx:08d}",
                "error": f"{type(exc).__name__}: {exc}",
                "spec": _spec_to_jsonable(spec),
                "meta": {"created_at": _now_iso(), "schema_version": SCHEMA_VERSION},
            }

    # ---- batch driver ------------------------------------------------------

    async def run(
        self,
        n: int,
        out_path: str,
        *,
        start_idx: int = 0,
        on_progress: Optional[callable] = None,
    ) -> Dict[str, int]:
        """Generate ``n`` samples with bounded concurrency and stream JSONL."""

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        sem = asyncio.Semaphore(self.config.concurrency)
        f = open(out_path, "a", buffering=1)  # line-buffered
        write_lock = asyncio.Lock()

        counters = {"PASS": 0, "SOFT_FAIL": 0, "HARD_FAIL": 0, "ERROR": 0, "DROPPED": 0}

        async def worker(i: int) -> None:
            async with sem:
                rec = await self.synthesize_one(i)
                if rec is None:
                    counters["DROPPED"] += 1
                    return
                if "error" in rec:
                    counters["ERROR"] += 1
                else:
                    counters[rec["consistency"]["status"]] += 1
                async with write_lock:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if on_progress:
                    on_progress(counters)

        try:
            tasks = [asyncio.create_task(worker(start_idx + i)) for i in range(n)]
            await asyncio.gather(*tasks)
        finally:
            f.close()
        return counters
