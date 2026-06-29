"""Minimal OpenAI-compatible async client with retry + multi-provider routing.

Avoids hard-pinning to the openai SDK; uses raw httpx so any vLLM / Ollama /
DeepSeek / OpenAI / Together / Groq endpoint that exposes ``/v1/chat/completions``
works out of the box.

Also supports the in-house **Venus LLM proxy** used in the company production
environment (see ``examples/formal.py``):

* ``base_url`` is the *full* chat-completions URL (no ``/chat/completions``
  suffix is appended);
* the API key read from the env var is automatically suffixed with the proxy
  routing tag (``@5325`` by default) before being sent as a Bearer token.

Enable it by setting ``provider: "venus"`` on the endpoint (or in YAML).

Also tracks **token usage and USD cost** per endpoint so that a single
``run_synth`` run can print how much it spent. Prices are per 1M tokens and
can be overridden per-endpoint in YAML via ``price_per_mtok_input`` /
``price_per_mtok_output``; otherwise they are looked up in ``DEFAULT_PRICES``
below by the request-body ``model`` name.
"""

from __future__ import annotations

import asyncio
import os
import random
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import httpx


# Default routing tag appended to the Venus proxy API token. See
# ``examples/formal.py``: ``token = ENV_VENUS_OPENAPI_SECRET_ID + "@5325"``.
VENUS_DEFAULT_TOKEN_SUFFIX = "@5325"


# ---------------------------------------------------------------------------
# Price table (USD per 1M tokens).
#
# Keys are matched against ``ModelEndpoint.model`` (the id sent in the
# request body). Prefix-match is used, so e.g. ``gpt-4o-2024-08-06`` will
# pick up the ``gpt-4o`` entry. If you want a different price for a specific
# snapshot, set ``price_per_mtok_input`` / ``price_per_mtok_output`` on the
# endpoint in YAML.
#
# Sources: OpenAI & Anthropic public pricing pages (as of 2025).
# ---------------------------------------------------------------------------
DEFAULT_PRICES: Dict[str, Dict[str, float]] = {
    # OpenAI
    "gpt-4o-mini":        {"input": 0.15,  "output": 0.60},
    "gpt-4o":             {"input": 5.00,  "output": 15.00},
    "gpt-4-turbo":        {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo":      {"input": 0.50,  "output": 1.50},
    # Anthropic (user-provided table)
    "claude-sonnet-4-6":  {"input": 3.00,  "output": 15.00},
    "claude-3-5-sonnet":  {"input": 3.00,  "output": 15.00},
    "claude-3-opus":      {"input": 15.00, "output": 75.00},
    "claude-3-haiku":     {"input": 0.25,  "output": 1.25},
    # DeepSeek
    "deepseek-chat":      {"input": 0.27,  "output": 1.10},
    "deepseek-reasoner":  {"input": 0.55,  "output": 2.19},
}


def _lookup_price(model: str) -> Dict[str, float]:
    """Look up default price for a model id; prefix match, else zero."""
    if model in DEFAULT_PRICES:
        return DEFAULT_PRICES[model]
    # Longest-prefix match (so ``gpt-4o-2024-08-06`` prefers ``gpt-4o``
    # over ``gpt-4``).
    best_key = ""
    for key in DEFAULT_PRICES:
        if model.startswith(key) and len(key) > len(best_key):
            best_key = key
    if best_key:
        return DEFAULT_PRICES[best_key]
    return {"input": 0.0, "output": 0.0}


@dataclass
class ModelEndpoint:
    """A single chat-completions endpoint.

    Parameters
    ----------
    provider:
        ``"openai"`` (default) for any OpenAI-compatible endpoint where the
        ``base_url`` ends at ``/v1`` and ``/chat/completions`` is appended by
        this client.
        ``"venus"`` for the in-house Venus LLM proxy where ``base_url`` is
        already the full chat-completions URL and the API token needs a
        routing-tag suffix.
    token_suffix:
        String appended to the value read from ``api_key_env`` before it is
        used as the Bearer token. Defaults to ``"@5325"`` for ``venus`` and
        empty otherwise. Set to ``""`` to disable.
    price_per_mtok_input / price_per_mtok_output:
        USD per 1M tokens. If ``None``, the default price for ``model`` from
        ``DEFAULT_PRICES`` is used.
    """

    name: str                         # logical id, used in metadata
    model: str                        # the model id sent in the request body
    base_url: str                     # ``https://api.openai.com/v1`` or full venus URL
    api_key_env: str                  # env var holding the api key
    temperature: float = 0.9
    max_tokens: int = 1024
    weight: float = 1.0               # for routing
    extra_headers: Dict[str, str] = field(default_factory=dict)
    extra_body: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 120.0
    provider: str = "openai"          # "openai" | "venus"
    token_suffix: Optional[str] = None  # None => pick default per provider
    price_per_mtok_input: Optional[float] = None   # USD / 1M tokens
    price_per_mtok_output: Optional[float] = None  # USD / 1M tokens

    def __post_init__(self) -> None:
        if self.token_suffix is None:
            self.token_suffix = (
                VENUS_DEFAULT_TOKEN_SUFFIX if self.provider == "venus" else ""
            )
        if self.price_per_mtok_input is None or self.price_per_mtok_output is None:
            fallback = _lookup_price(self.model)
            if self.price_per_mtok_input is None:
                self.price_per_mtok_input = fallback["input"]
            if self.price_per_mtok_output is None:
                self.price_per_mtok_output = fallback["output"]

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise RuntimeError(
                f"env var {self.api_key_env} is not set (needed for {self.name})"
            )
        return key + (self.token_suffix or "")

    @property
    def chat_url(self) -> str:
        """Return the full chat-completions URL for this endpoint."""
        if self.provider == "venus":
            # base_url is already the full endpoint (e.g.
            # http://v2.open.venus.oa.com/llmproxy/chat/completions)
            return self.base_url
        return self.base_url.rstrip("/") + "/chat/completions"

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Compute USD cost for a single call's token usage."""
        return (
            prompt_tokens * (self.price_per_mtok_input or 0.0)
            + completion_tokens * (self.price_per_mtok_output or 0.0)
        ) / 1_000_000.0


class LLMClient:
    """Async client over a list of endpoints, with weighted routing + retries.

    Usage::

        client = LLMClient([ep1, ep2])
        out = await client.chat([
            {"role": "system", "content": "..."},
            {"role": "user",   "content": "..."},
        ])
        # ...
        print(client.usage_summary())  # prints per-endpoint tokens + $
    """

    def __init__(
        self,
        endpoints: List[ModelEndpoint],
        max_retries: int = 5,
        retry_base_delay: float = 1.0,
        rng: Optional[random.Random] = None,
    ) -> None:
        if not endpoints:
            raise ValueError("LLMClient needs at least one endpoint")
        self.endpoints = endpoints
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.rng = rng or random.Random()
        # Venus proxy (plain HTTP) does not support HTTP/2; disable to keep a
        # single client compatible with both OpenAI-style and Venus endpoints.
        self._client = httpx.AsyncClient(http2=False)
        # Per-endpoint usage counters. Populated lazily on first success.
        # shape: {endpoint_name: {"model", "prompt_tokens", "completion_tokens",
        #                         "requests", "cost_usd"}}
        self.usage: Dict[str, Dict[str, Any]] = {}
        self._usage_lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._client.aclose()

    # ---- routing -----------------------------------------------------------
    def _route(self, prefer: Optional[str] = None) -> ModelEndpoint:
        if prefer:
            for ep in self.endpoints:
                if ep.name == prefer:
                    return ep
            raise KeyError(f"endpoint with name={prefer!r} not found")
        weights = [ep.weight for ep in self.endpoints]
        return self.rng.choices(self.endpoints, weights=weights, k=1)[0]

    # ---- usage accounting --------------------------------------------------
    async def _record_usage(
        self, ep: ModelEndpoint, data: Dict[str, Any]
    ) -> None:
        u = data.get("usage") or {}
        pt = int(u.get("prompt_tokens", 0) or 0)
        ct = int(u.get("completion_tokens", 0) or 0)
        cost = ep.cost(pt, ct)
        async with self._usage_lock:
            slot = self.usage.setdefault(
                ep.name,
                {
                    "model": ep.model,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "requests": 0,
                    "cost_usd": 0.0,
                    "price_in": ep.price_per_mtok_input or 0.0,
                    "price_out": ep.price_per_mtok_output or 0.0,
                },
            )
            slot["prompt_tokens"] += pt
            slot["completion_tokens"] += ct
            slot["requests"] += 1
            slot["cost_usd"] += cost

    def usage_summary(self) -> Dict[str, Dict[str, Any]]:
        """Return a deep-ish copy of the per-endpoint usage table."""
        return {k: dict(v) for k, v in self.usage.items()}

    # ---- chat --------------------------------------------------------------
    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        prefer_endpoint: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run a single chat completion. Returns ``{"text", "endpoint", "raw", "usage"}``.

        Re-routes among compatible endpoints on transient errors.
        """
        last_err: Optional[BaseException] = None
        attempts = 0
        while attempts < self.max_retries:
            ep = self._route(prefer_endpoint)
            payload = {
                "model": ep.model,
                "messages": messages,
                "temperature": temperature if temperature is not None else ep.temperature,
                "max_tokens": max_tokens if max_tokens is not None else ep.max_tokens, #max_completion_tokens gpt5.1need ; max_tokens gpt4need
                **ep.extra_body,
            }
            if response_format is not None:
                payload["response_format"] = response_format
            headers = {
                "Authorization": f"Bearer {ep.api_key}",
                "Content-Type": "application/json",
                **ep.extra_headers,
            }
            url = ep.chat_url
            try:
                r = await self._client.post(
                    url, json=payload, headers=headers, timeout=ep.timeout
                )
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"transient {r.status_code}: {r.text[:200]}",
                        request=r.request,
                        response=r,
                    )
                r.raise_for_status()
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                await self._record_usage(ep, data)
                return {
                    "text": content,
                    "endpoint": ep.name,
                    "raw": data,
                    "usage": data.get("usage") or {},
                }
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_err = exc
                attempts += 1
                if attempts >= self.max_retries:
                    break
                delay = self.retry_base_delay * (2 ** (attempts - 1))
                # add jitter to avoid thundering-herd on rate limits
                delay *= (0.7 + 0.6 * self.rng.random())
                await asyncio.sleep(delay)
        raise RuntimeError(
            f"chat failed after {self.max_retries} retries: {last_err!r}"
        )


# ---------------------------------------------------------------------------
# Multi-client usage aggregation helpers (used by run_synth at end-of-run).
# ---------------------------------------------------------------------------

def merge_usage_summaries(
    labeled_clients: Iterable[tuple],
) -> Dict[str, Dict[str, Any]]:
    """Merge usage from multiple clients, keyed by ``"{label}::{endpoint}"``.

    ``labeled_clients`` is an iterable of ``(label, LLMClient)`` tuples,
    e.g. ``[("generator", gen), ("judge", judge)]``.
    """
    merged: Dict[str, Dict[str, Any]] = {}
    for label, client in labeled_clients:
        for name, slot in client.usage_summary().items():
            merged[f"{label}::{name}"] = dict(slot)
    return merged


def format_usage_table(usage: Dict[str, Dict[str, Any]]) -> str:
    """Pretty-print a usage dict as a fixed-width table + total line."""
    if not usage:
        return "(no LLM usage recorded)"

    headers = [
        "stage::endpoint", "model", "req",
        "prompt_tok", "compl_tok", "in$/Mtok", "out$/Mtok", "cost_usd",
    ]
    rows: List[List[str]] = []
    tot_pt = tot_ct = tot_req = 0
    tot_cost = 0.0
    for key, slot in sorted(usage.items()):
        pt = int(slot.get("prompt_tokens", 0))
        ct = int(slot.get("completion_tokens", 0))
        req = int(slot.get("requests", 0))
        cost = float(slot.get("cost_usd", 0.0))
        tot_pt += pt
        tot_ct += ct
        tot_req += req
        tot_cost += cost
        rows.append([
            key,
            str(slot.get("model", "")),
            str(req),
            f"{pt:,}",
            f"{ct:,}",
            f"{float(slot.get('price_in', 0.0)):.2f}",
            f"{float(slot.get('price_out', 0.0)):.2f}",
            f"${cost:,.4f}",
        ])
    rows.append([
        "TOTAL", "", str(tot_req),
        f"{tot_pt:,}", f"{tot_ct:,}", "", "", f"${tot_cost:,.4f}",
    ])

    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]

    def fmt_row(cells: List[str]) -> str:
        return "  ".join(c.ljust(widths[i]) for i, c in enumerate(cells))

    sep = "  ".join("-" * w for w in widths)
    lines = [fmt_row(headers), sep]
    for r in rows[:-1]:
        lines.append(fmt_row(r))
    lines.append(sep)
    lines.append(fmt_row(rows[-1]))
    return "\n".join(lines)


def build_client_from_config(cfg: Dict[str, Any]) -> LLMClient:
    """Build an LLMClient from a config dict::

        models:
          - name: gpt4o-mini
            model: gpt-4o-mini
            provider: venus          # or "openai" (default)
            base_url: http://v2.open.venus.oa.com/llmproxy/chat/completions
            api_key_env: ENV_VENUS_OPENAPI_SECRET_ID
            token_suffix: "@5325"    # optional; defaults to "@5325" for venus
            temperature: 0.9
            weight: 1.0
            # Optional: override the default price table (USD / 1M tokens).
            price_per_mtok_input: 0.15
            price_per_mtok_output: 0.60
    """
    eps = []
    for m in cfg.get("models", []):
        eps.append(
            ModelEndpoint(
                name=m["name"],
                model=m["model"],
                base_url=m["base_url"],
                api_key_env=m["api_key_env"],
                temperature=m.get("temperature", 0.9),
                max_tokens=m.get("max_tokens", 1024),
                weight=m.get("weight", 1.0),
                extra_headers=m.get("extra_headers", {}) or {},
                extra_body=m.get("extra_body", {}) or {},
                timeout=m.get("timeout", 120.0),
                provider=m.get("provider", "openai"),
                token_suffix=m.get("token_suffix", None),
                price_per_mtok_input=m.get("price_per_mtok_input", None),
                price_per_mtok_output=m.get("price_per_mtok_output", None),
            )
        )
    return LLMClient(
        eps,
        max_retries=cfg.get("max_retries", 5),
        retry_base_delay=cfg.get("retry_base_delay", 1.0),
    )


# ---------------------------------------------------------------------------
# Embedding client (used by the judge consistency checker as a semantic
# fallback when token-overlap matching fails). Optional -- if not configured,
# the matcher just skips the embedding stage.
# ---------------------------------------------------------------------------


class EmbeddingClient:
    """Minimal async OpenAI-compatible embedding client.

    Single endpoint (multi-provider not needed -- one embedding model is
    enough). Returns float vectors. All methods are coroutine-safe.
    """

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key_env: str,
        timeout: float = 60.0,
        max_retries: int = 5,
        retry_base_delay: float = 1.0,
        batch_size: int = 64,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.batch_size = batch_size
        self._client = httpx.AsyncClient(http2=True)

    async def aclose(self) -> None:
        await self._client.aclose()

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise RuntimeError(
                f"env var {self.api_key_env} is not set "
                f"(needed for embedding model {self.model})"
            )
        return key

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of strings. Empty / whitespace-only entries get a
        zero-vector placeholder of the correct dimension."""
        if not texts:
            return []

        out: List[Optional[List[float]]] = [None] * len(texts)
        # Batch only the non-empty entries; keep the placeholders empty.
        non_empty = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
        for chunk_start in range(0, len(non_empty), self.batch_size):
            chunk = non_empty[chunk_start:chunk_start + self.batch_size]
            idxs = [c[0] for c in chunk]
            inputs = [c[1] for c in chunk]
            vecs = await self._embed_batch(inputs)
            for i, v in zip(idxs, vecs):
                out[i] = v

        # Fill placeholders with a zero vector of matching dim (use the dim of
        # the first non-empty result; if all empty, return all-empty lists).
        dim = next((len(v) for v in out if v), 0)
        return [v if v is not None else [0.0] * dim for v in out]

    async def _embed_batch(self, inputs: List[str]) -> List[List[float]]:
        url = self.base_url + "/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "input": inputs}
        last_err: Optional[BaseException] = None
        for attempt in range(self.max_retries):
            try:
                r = await self._client.post(
                    url, json=payload, headers=headers, timeout=self.timeout
                )
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"transient {r.status_code}: {r.text[:200]}",
                        request=r.request,
                        response=r,
                    )
                r.raise_for_status()
                data = r.json()
                # Sort by index to be safe.
                items = sorted(data["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in items]
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_err = exc
                delay = self.retry_base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
        raise RuntimeError(
            f"embedding call failed after {self.max_retries} retries: {last_err!r}"
        )


def build_embedding_client_from_config(
    cfg: Optional[Dict[str, Any]],
) -> Optional[EmbeddingClient]:
    """Build an EmbeddingClient from cfg, or return None if cfg is missing /
    disabled."""
    if not cfg or not cfg.get("enabled", True) is True:
        return None
    if "model" not in cfg or "base_url" not in cfg:
        return None
    return EmbeddingClient(
        model=cfg["model"],
        base_url=cfg["base_url"],
        api_key_env=cfg.get("api_key_env", "OPENAI_API_KEY"),
        timeout=cfg.get("timeout", 60.0),
        max_retries=cfg.get("max_retries", 5),
        retry_base_delay=cfg.get("retry_base_delay", 1.0),
        batch_size=cfg.get("batch_size", 64),
    )
