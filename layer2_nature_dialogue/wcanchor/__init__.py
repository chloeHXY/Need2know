"""Layer 2 -- WildChat natural-anchor pipeline.

Eight stages turning a raw WildChat parquet slice into Layer-1-compatible
JSONL with two-judge consensus annotations:

    S0  load                 parquet -> records
    S1  filter_struct        single-turn / EN / 25-2500 words / non-toxic
    S2+S3 screen             content_type + has_ci_concern (one LLM call)
    S4  annotate_ci (A)      Appendix E.1 + extended (subject, necessity tier)
    S5  concord (judge B)    independent annotator; soft IoU on span sets
    S6  unify                Layer-1 schema (spec.essential_info, etc.)
    S7  reformulate          gold reformulation (Appendix E.6)
    S9  ethical              Faker-based replacement of explicit PII spans
    S10 stats                funnel report

Each stage writes its own jsonl checkpoint under data/stages/, so you can
re-run a single stage without burning tokens upstream.

This package reuses Layer 1's HTTP client unchanged. We append the Layer 1
project root to sys.path so `from synth.llm_client import ...` works.
"""

from __future__ import annotations

import os
import sys

# wcanchor/__init__.py is at <DataG>/layer2_nature_dialogue/wcanchor/.
# Layer 1's ``synth`` package lives under <DataG>/layer1_reverse_synthesis/.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DATAG_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
_LAYER1_ROOT = os.path.join(_DATAG_ROOT, "layer1_reverse_synthesis")
if _LAYER1_ROOT not in sys.path:
    sys.path.insert(0, _LAYER1_ROOT)
# Also expose <DataG> on sys.path so ``layer2_nature_dialogue.*`` imports work
# when scripts are launched from inside the layer2 dir.
if _DATAG_ROOT not in sys.path:
    sys.path.insert(0, _DATAG_ROOT)

# Re-export the layer-1 client so callers don't need to know the path trick.
from synth.llm_client import (  # noqa: E402,F401
    EmbeddingClient,
    LLMClient,
    ModelEndpoint,
    build_client_from_config,
    build_embedding_client_from_config,
)

SCHEMA_VERSION_L2 = "1.0-l2"
