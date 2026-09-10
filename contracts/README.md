# Integration contracts — proposal v1

The health, Steam inspection, and snapshot-input recommendation routes are implemented;
the dataset-backed GET routes remain design specifications. Generate `openapi.json`
from API schemas and commit the export; generate frontend types from that export. CI
should detect stale generated files. Generate the snapshot schema from canonical models.
Use FastAPI/Pydantic wire models at the API boundary and core domain records internally.

## Read API

All market endpoints use `/api/v1`. Dashboard requests share one explicit dataset ID
obtained from `/datasets/current`, preventing a refresh from mixing versions.

| Method and route | Input | Output |
| --- | --- | --- |
| `GET /health` | None | Process liveness; no upstream source calls |
| `POST /api/v1/auth/signup` (implemented) | Email, password, optional display name | Bearer session and inactive account |
| `POST /api/v1/auth/login` (implemented) | Email and password | Bearer session |
| `GET /api/v1/auth/me` (implemented) | Bearer token | Current account |
| `POST /api/v1/auth/logout` (implemented) | Bearer token | Deletes session |
| `POST /api/v1/auth/subscription` (implemented) | Bearer token, plan, premium role | Updated account |
| `POST /api/v1/auth/youtube/dev-verify` (implemented) | Bearer token, channel and Google subject | Active content creator account |
| `POST /api/v1/steam/games/inspect` | Active premium bearer token, Steam Store URL, locale and review options | Live normalized metadata, recent reviews, player count, cache metadata |
| `POST /api/v1/steam/games/analyze` (implemented) | Active premium bearer token, Steam URL, optional country and date range | Game profile, catalog matches, refreshed prices and model report |
| `POST /api/v1/recommendations` (implemented) | Active premium bearer token, game profile, dataset, dates, currency and region | Direct `LaunchReport`: competitors, release advice, price advice and warnings |
| `GET /api/v1/datasets/current` | None | Active dataset metadata; 503 if no usable dataset |
| `GET /api/v1/segments` | `dataset_id` | Supported segment IDs, labels, mapping version |
| `GET /api/v1/saturation` | `dataset_id`, `start_week`, `weeks` | Weekly cells for supported segments |
| `GET /api/v1/competitors` | `dataset_id`, `segment_id`, `start_week`, `weeks`, `limit`, `cursor` | Paginated dated competitors |
| `GET /api/v1/recommendations` | `dataset_id`, `segment_id`, `start_week`, `weeks` | Ranked windows or insufficient-evidence result |

MVP supports eight weeks. `start_week` is an ISO `YYYY-MM-DD` Monday; reject rather
than silently move other dates. These GET dashboard conventions do not apply to the
implemented snapshot-input POST endpoint; see the [model card](../ml/MODEL_CARD.md).
Dashboard weeks are half-open Monday-to-Monday intervals.
Game release dates remain source calendar dates; observation timestamps are UTC ISO
8601. A game belongs to a week only when its date precision is `day`.

Validate `weeks` in 1–8, `limit` in 1–100, known segments, and supported dataset dates.
Unknown dataset/segment: 404; invalid query: 422; no usable dataset: 503.
A valid query with insufficient evidence returns 200 with an explicit abstention status.
Competitor ordering is `(release_date, app_id)`; the opaque cursor is scoped to the
same dataset and filters. Undated/approximate-date counts are reported separately.
The API normalizes errors to `{error: {code, message, request_id}}`, including validation
errors. Retain datasets used by active requests; if a version expires, refetch the
current version and reload all views together.

## Canonical records

| Record | Required fields and meaning |
| --- | --- |
| Dataset | `dataset_id`, `schema_version`, `collected_at`, `published_at`, `source_names`, `sample_size`, `coverage_status`, `coverage_notes`, `mapping_version`, `horizon_start`, `horizon_end` (exclusive) |
| Game observation | `dataset_id`, `app_id`, `name`, `source`, `observed_at`, `release_date` (nullable), `release_date_raw`, `date_precision` (`day/month/quarter/year/unknown`), `segment_ids`, nullable `price_minor`, `currency`, `price_region`, `current_players`, `review_count`, `positive_review_ratio` |
| Weekly cell | `segment_id`, `week_start`, `observed_release_count`, nullable `competition_score`, `quality_flags` |
| Ranked window | `week_start`, `rank`, nullable `competition_score`, `observed_release_count`, `components`, `evidence_app_ids`, `reason_codes`, `quality_flags` |
| Recommendation result | `status` (`ranked/insufficient_evidence`), `model_version`, `policy_version`, `windows`, nullable `best_week`, `explanation` |

Report `undated_release_count` once in response metadata for the selected segment
and horizon, rather than duplicating ambiguous records into weekly cells. Null metrics mean unavailable, never zero. Ratios range from 0 to 1.
For baseline v1, `competition_score` equals observed release count; lower means less
observed competition, not a normalized success probability. A later score formula gets
its own model version and explicit scale. Abstained results have `best_week: null` and
no ranked windows, while heatmap observations remain visible.

Planned GET market responses use `{data, meta}`. `meta` includes dataset metadata,
`generated_at`, and `delivery_mode` (`api/snapshot`); scoring responses also identify
model/policy versions. Freshness is derived from `collected_at` and configured policy,
not from delivery mode. No fictional example games are included in this scaffold.

## Offline snapshot

Export a single validated envelope:

```text
schema_version
meta: Dataset metadata + generated_at + model_version + policy_version
data:
  segments: Segment[]
  saturation: WeeklyCell[]
  competitors: GameObservation[]
  recommendations: [{segment_id, start_week, weeks, result}]
```

Include complete competitors for the bounded export horizon, not one API page.
Recommendations are precomputed for explicitly supported filter combinations. The
frontend snapshot adapter returns the same response shapes as the HTTP adapter and
sets `delivery_mode: snapshot`. Do not recompute rankings in JavaScript.
Validate schema and required fields before use; unknown major versions are rejected.
If both API and snapshot fail, show a data-unavailable state. Do not mask this with mock
recommendations. If a filter combination was not exported, disable it in snapshot mode.

The backend and ML engineer own schema changes together; frontend reviews wire changes.
Additive optional fields may evolve in v1. Breaking changes require a new schema/API
version and regenerated clients/fixtures. Never duplicate model math in contract files.
