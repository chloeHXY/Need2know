# `data/`

Default output directory for `scripts/run_synth.py`. JSONL files written here
follow the schema described in the top-level [README §3](../README.md#三数据-schema).

Convention:
- `smoke.jsonl`     small smoke-test runs (≤ 100 rows).
- `layer1_v{N}.jsonl`  versioned full datasets.
- `*.bad.jsonl`     hand-curated failure cases (optional).

python scripts/run_synth.py --config config/default.yaml --n 5 --output data/smoke.jsonl 