# ML workspace

The launch advisor baseline is implemented in `ili_core.recommendation.launch` and
served by `POST /api/v1/recommendations`. It matches competitors, ranks release
windows when coverage passes, and estimates comparable price ranges. See the
[model card and run instructions](MODEL_CARD.md) for contracts, formulas, Steam
collection, evidence requirements, and limitations. It is not a trained model.

Use `experiments/` for exploratory analysis and `evaluation/` for reproducible evaluation
scripts and reports. Serving code belongs in `packages/core/src/ili_core`, not notebooks.
Local `artifacts/` and `runs/` are ignored; use artifact storage when model files grow.

`experiments/models/model.py` is aligned with the current Steam inspection contract.
It trains from the Kaggle catalog, but `build_features_from_inspection()` accepts the
current nested API response for both released and upcoming Steam pages. Reviews,
current players, and review summaries are target-building signals for historical
released games only; they are not required for scoring upcoming games.

```bash
python ml/experiments/models/model.py --csv /path/to/steam_games.csv
python ml/experiments/models/model.py --predict-json /path/to/inspection-response.json
```

The first main model is an explainable observed-release-count baseline with a documented
coverage gate and deterministic ties. Add learned ranking only after defining a measurable
target and time-respecting evaluation. Never train old launch decisions using reviews or
player counts observed after those decisions.

Each promoted artifact needs model/feature versions, dataset IDs, training cutoff,
metrics, dependency versions, checksum, and compatible core interface. Keep baseline
fallback behavior. LLM integrations belong in `apps/api/src/ili_api/llm`; their role is to
explain supplied evidence without changing canonical rankings.
