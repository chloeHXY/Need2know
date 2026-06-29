#!/usr/bin/env python
"""End-to-end driver for the WildChat natural-anchor pipeline.

Usage::

    # full run (incremental: skips stages whose output file already exists)
    python nature_data_syn/scripts/run_full.py \
        --config nature_data_syn/config/default.yaml

    # smoke run on first 20 rows from S1, then stop after screen
    python nature_data_syn/scripts/run_full.py \
        --config nature_data_syn/config/default.yaml \
        --limit 20 --stop-after screen

    # force re-run a specific stage by deleting its checkpoint first
    rm nature_data_syn/data/stages/04_judge_a.jsonl
    python nature_data_syn/scripts/run_full.py --config ...
"""

from __future__ import annotations

import argparse
import os
import sys


def _ensure_pkg_on_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    pkg_root = os.path.abspath(os.path.join(here, ".."))
    parent = os.path.abspath(os.path.join(pkg_root, ".."))
    if parent not in sys.path:
        sys.path.insert(0, parent)


def main() -> int:
    _ensure_pkg_on_path()
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--limit", type=int, default=None,
                   help="Limit number of records entering S2 (for smoke tests).")
    p.add_argument("--stop-after", default=None,
                   help="Override pipeline.stop_after in the yaml. "
                        "One of: load|struct|screen|judge_a|concord|unify|reformulate")
    args = p.parse_args()

    from layer2_nature_dialogue.wcanchor.pipeline import main as pipeline_main
    if args.stop_after is not None:
        # Inject the override by patching the yaml on the fly.
        import yaml
        with open(args.config, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        cfg.setdefault("pipeline", {})["stop_after"] = args.stop_after
        tmp = args.config + ".override.yaml"
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f)
        try:
            pipeline_main(tmp, limit=args.limit)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
    else:
        pipeline_main(args.config, limit=args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
