# Launch advisor v1

Model `launch-baseline-v1`, policy `launch-policy-v1` is an explainable recommendation
baseline, not a trained sales predictor. No API key, GPU, weights, or LLM are needed.
Inference is offline and deterministic for a fixed request and evaluation time.

## Run it

For the website flow, import the downloaded CSV with
`python -m ili_pipeline.catalog`, start the API, and run the frontend. Submit a Steam
link in the UI; `POST /api/v1/steam/games/analyze` orchestrates lookup, indexed catalog
matching, live regular-price refresh, and the model below. The supplied download
yielded 140,411 usable records, 17 rejected records, and no future release dates.
Thus the UI can recommend a comparable price but explicitly abstains on release
timing until an upcoming discovery source is added. Matching preselects up to 600
neighbors by tag/genre overlap from both the full catalog and recent releases,
then applies the shared similarity score. Catalog review/player counts are displayed
as historical context, without being used as prelaunch strength signals.

After installing the dependencies described in `apps/api/README.md`, from the root:

```bash
# Replace these example inputs with your target, selected competitors, and dates.
python -m ili_pipeline.launch collect \
  --steam-url https://store.steampowered.com/app/413150/ \
  --app-ids 1158160 1432860 2142790 2521600 1536090 \
  --earliest 2026-10-01 --latest 2026-11-30 \
  --region US --output data/processed/launch-request.json

python -m ili_pipeline.launch recommend \
  --request data/processed/launch-request.json \
  --output data/processed/launch-report.json

# Alternatively submit that request to the running API.
curl -X POST http://127.0.0.1:8000/api/v1/recommendations \
  -H 'Content-Type: application/json' \
  --data-binary @data/processed/launch-request.json
```

The example IDs are collection inputs, not a validated competitor set or a promise
of sufficient pricing evidence. The collector fetches at most 200 unique apps,
preserves source URLs and timestamps, skips non-game comparables, and atomically
writes only after collection and validation succeed. It uses the existing Steam
adapter, including its undocumented Store metadata dependency, without scraping
SteamDB. It does not use review/player counts as prelaunch popularity features.

**This collector gathers a selected sample, not the entire upcoming market.** It
sets `coverage.discovery_complete=false`. Pricing can work with enough comparable
games, but release ranking intentionally abstains. Automatic upcoming discovery is
not implemented. Tags and followers also require a separate dataset producer.

To enable release ranking, supply a dataset from a discovery process that actually
enumerated its declared upcoming market scope. Include that scope and process in
`coverage.discovery_method` and `notes`, an inclusive `horizon_start`, exclusive
`horizon_end`, and `discovery_complete=true`. Do not toggle this flag to force a
recommendation. Completeness is a producer assertion the model cannot verify.

## Interface

`ili_core.recommendation.launch.recommend(request, now=...)` accepts `LaunchRequest`:
a game profile, market dataset, inclusive feasible date range, currency, and region.
You may construct it directly using the models in `ili_core.domain.launch`, without
a Steam page for the target. The game profile includes name, genres, gameplay tags,
description, premium/free business model, and optional expected playtime.

Output: up to 20 matched competitors, up to three nonoverlapping seven-day release
windows, price advice, evidence app IDs, warnings, qualitative confidence, versions,
and dataset ID. Prices are integer minor units: USD 1999 means USD 19.99.

`POST /api/v1/recommendations` accepts the same JSON and returns `LaunchReport`
directly. This snapshot-input endpoint is separate from the planned dataset-backed
GET dashboard endpoints and their envelopes. `/docs` and generated OpenAPI describe
every field. The snapshot-input recommendation route makes no network calls. The
Steam-link analysis route performs bounded live enrichment before calling this model.

## Competitor matching

Use case/whitespace-normalized weighted Jaccard overlap: tags 0.45, genres 0.35,
description words 0.20. Renormalize over features present in the target; missing
competitor fields contribute no overlap. Match at similarity >= 0.15; order by
similarity descending, then app ID. Exclude the target itself. Business model does
not exclude audience competitors, but pricing only compares paid games.
Lexical overlap does not recognize semantic synonyms. Generic genres alone provide
weak matching; add gameplay tags when available.

## Release score and coverage gate

Evaluate every complete seven-day window within the requested range. Default score
is the count of matching announced releases in the window. If every dated matching
competitor in the horizon has a follower count, use:

```text
strength_i = log(1 + followers_i) / max_j(log(1 + followers_j))
competition(window) = sum(similarity_i * (1 + strength_i))
```

When every follower count is zero, strength is zero. Missing followers disable the
strength component for the entire horizon. Lower is less observed competition, not
higher predicted sales. Equal scores share rank, with earliest starts as tie-breaks.
Return up to three distinct, nonoverlapping alternatives retaining ranks from the
full candidate set. `best_date` is the start of a recommended window; no weekday
sales effect has been learned.

Abstain for incomplete discovery, insufficient date coverage, a dataset or matching
upcoming observation older than seven days, future observations, a past start date,
any matching upcoming game with an unknown/approximate date, or no dated matching
competitors in the horizon. An empty calendar is not evidence of opportunity.
Unknown dates are counted separately and never assigned invented days. This is
conservative: an undated matching game blocks ranking even if it might fall outside
the horizon.

The model does not capture attention spillover outside a window, existing live-service
games, franchise recognition, Steam events, or marketing. Confidence is a qualitative
data-quality label capped at medium, not a calibrated probability.

## Pricing

Require five matching paid games released within the last 730 days, each with a
positive regular price in the exact requested currency/region observed within seven
days. Exclude future releases, free games, missing prices, unknown dates, and older
releases. If both playtimes are known, require the comparable to be within half to
twice the target's expected playtime. Unknown playtime is allowed, limiting precision.

Recommend the similarity-weighted median and 25th–75th percentile range. Use observed
regular price points; never use discounted prices or mix currencies. Current regular
prices are not historical launch prices. This is market positioning, not evidence of
a revenue-maximizing price. Free targets return zero upfront price, without in-game
monetization advice.

## Validation and future ML training

Core, API, and pipeline tests cover evidence gates, dates, stale/future observations,
pricing exclusions, ties, input ordering, popularity fallback, self-exclusion, and
collection failures. They verify implementation behavior, not commercial effectiveness.
No live-data predictive accuracy or revenue performance is claimed.

For a trained successor, collect immutable observations at decision time and define
an outcome window (such as authorized first-30-day sales). Split by launch time,
hold out later releases, prevent post-decision reviews/players entering features,
and compare against this baseline. Demand optimization requires evidence about
sales at different prices; reproducing historical prices alone is not enough.
Record dataset IDs, cutoff, feature version, metrics, and artifact checksum before
promotion. `experiments/models/model.py` remains an exploratory success-score script
and is not imported or served by this engine.
