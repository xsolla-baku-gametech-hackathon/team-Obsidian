# ML workspace

Use `experiments/` for exploratory analysis and `evaluation/` for reproducible evaluation
scripts and reports. Serving code belongs in `packages/core/src/ili_core`, not notebooks.
Local `artifacts/` and `runs/` are ignored; use artifact storage when model files grow.

The first main model is an explainable observed-release-count baseline with a documented
coverage gate and deterministic ties. Add learned ranking only after defining a measurable
target and time-respecting evaluation. Never train old launch decisions using reviews or
player counts observed after those decisions.

Each promoted artifact needs model/feature versions, dataset IDs, training cutoff,
metrics, dependency versions, checksum, and compatible core interface. Keep baseline
fallback behavior. LLM integrations belong in `apps/api/src/ili_api/llm`; their role is to
explain supplied evidence without changing canonical rankings.
