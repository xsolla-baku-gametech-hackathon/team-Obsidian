# Backend API

The website uses `POST /api/v1/steam/games/analyze` after login and active premium
subscription selection. The request requires `Authorization: Bearer <token>` and a
body such as `{"steam_url":"https://store.steampowered.com/app/413150/"}`. This
route reads the indexed catalog, looks up the game on Steam, matches similar titles,
refreshes up to 20 competitor records, and runs the model. It returns catalog
provenance, matched games, regular prices, price advice, release advice, and explicit
data limitations. Optional inputs: uppercase `country_code` (default US),
`earliest_date` and `latest_date` (both required if overriding the default next
90 days).

After installing dependencies, import the supplied CSV once:

```bash
.venv/bin/python -m ili_pipeline.catalog
./scripts/run_api.sh
```

The default input is `data/raw/steam/steam_games.csv`; the output is
`data/processed/steam-catalog.sqlite`. Import is streaming and publication is atomic.
Set `ILI_CATALOG_PATH` to override the API's default catalog location. Missing catalog
falls back to a metadata-only Steam report when live lookup succeeds; a failed upstream
lookup falls back to catalog details when present. Reports cache for five minutes.
Prices are only taken from successful live Steam refreshes, never assigned a new
timestamp from CSV import time.

During development, start both backend and frontend together from the repository root:

```bash
./scripts/dev.sh
```

`POST /api/v1/steam/games/inspect` and `POST /api/v1/recommendations` also require an
active premium bearer token. The recommendations route accepts a game profile and
validated market snapshot and returns competitor matches, release advice, comparable
pricing, and explanations. See the [model card](../../ml/MODEL_CARD.md) for collection
and request instructions. This endpoint uses local inference without Steam or LLM
network calls.

Generated reports are saved automatically to the current user's report history.
`GET /api/v1/reports` returns saved report summaries, and
`GET /api/v1/reports/{report_id}` returns the full stored report payload. Report IDs
are user-scoped; another account receives `404` for a report it does not own.

## Auth and subscriptions

Accounts start without a role. Users sign up or log in normally, then select a paid
plan and premium role through `POST /api/v1/auth/subscription`.

| Route | Purpose |
| --- | --- |
| `POST /api/v1/auth/signup` | Create account and return bearer session |
| `POST /api/v1/auth/login` | Return bearer session |
| `POST /api/v1/auth/logout` | Delete current session |
| `GET /api/v1/auth/me` | Return current account |
| `POST /api/v1/auth/subscription` | Select `starter`, `pro`, or `studio` and role |
| `POST /api/v1/auth/youtube/dev-verify` | Local placeholder for Google/YouTube verification |

Passwords are hashed with Argon2. Session tokens are random bearer tokens; only SHA-256
token hashes are stored in SQLite. User data is stored in `data/processed/users.sqlite`
by default. Game developers become active immediately after plan selection. Content
creators become `pending_youtube_verification` until their YouTube channel is verified
through the Google OAuth flow. The current dev endpoint records that verified state
without implementing the external OAuth exchange.

FastAPI REST API for Indie Launch Intelligence. The first endpoint validates a Steam
Store link, fetches normalized store-page metadata, and returns live review/player
signals when Steam exposes them. Upcoming games are supported: the API returns fields
such as release text, screenshots, trailers, languages, requirements, and content
descriptors while marking reviews and current players as unavailable. Responses are
cached in memory for five minutes.

## Run locally

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e packages/core -e pipelines -e 'apps/api[dev]'
./scripts/run_api.sh
```

Open `http://127.0.0.1:8000/docs` for Swagger UI. Inspect a game with:

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/steam/games/inspect' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{"steam_url":"https://store.steampowered.com/app/413150/Stardew_Valley/"}'
```

Optional request fields are `country_code`, `language`, `review_language`, and
`review_count` (1–100). Price values use the smallest currency unit. `current_players`
is a point-in-time value and is usually unavailable for upcoming games. Recent reviews
are not a statistically balanced sample and usually do not exist before release.

Upcoming-game responses keep `reviews` empty, set `review_summary` and
`current_players` to `null`, and include `live_data.unavailable_reasons` so frontend
and ML code can branch cleanly.

Configuration uses the `ILI_` variables documented in the root `.env.example`.
The Store metadata endpoint used by Steam is publicly reachable but not part of the
documented Steamworks Web API, so the adapter isolates that dependency. The review
endpoint and current-player API are Steam-documented services.

Run checks:

```bash
.venv/bin/ruff check apps/api pipelines packages/core
.venv/bin/pytest
.venv/bin/python scripts/export_openapi.py
```

See the [architecture](../../docs/ARCHITECTURE.md) and
[contracts](../../contracts/README.md) for the larger system.

## Upcoming launch calendar

Launch timing now uses a separate, paginated Steam upcoming-release calendar. Released
catalog games are used only for historical similarity and pricing. The API refreshes
`data/processed/upcoming.json` in the background on startup when missing or older than
24 hours, then checks hourly. First collection can take several minutes; interrupted
or rate-limited scans keep the previous snapshot. Progress is checkpointed separately
and can resume for up to an hour; partial data is never served as a complete calendar. Snapshots older than seven days do
not produce timing recommendations. Run one API worker for this development scheduler;
for multiple workers disable auto-refresh and schedule the collector once externally.

From the repository root, refresh manually:

```bash
PYTHONPATH=packages/core/src:pipelines/src .venv/bin/python -m ili_pipeline.upcoming
```

Configuration: `ILI_UPCOMING_PATH`, `ILI_MAJOR_RELEASES_PATH`, and
`ILI_UPCOMING_AUTO_REFRESH=false` (for externally scheduled collection).

The dashboard accepts an optional earliest/latest launch range. Both omitted means
90 days from today; custom ranges span 7–366 days. The existing analyze endpoint returns:

- `upcoming_catalog`: snapshot freshness, count and discovery coverage.
- `report.competitors`: upcoming titles only, including broad attention risks.
- `report.release.windows`: three non-overlapping lower-pressure alternatives.
- `report.release.high_risk_windows`: up to three higher-pressure windows and evidence IDs.
- `competitors`: legacy field containing historical pricing/similarity comparables.

Every dated upcoming game contributes `0.25 + 2 * similarity` to its overlapping
seven-day window. A sourced attention weight multiplies this pressure and adds
`5 * (attention_weight - 1)` for broad audience attention, with a linear 14-day buffer before/after high-attention releases. Steam's top 20 popular-wishlist
listing receives weight 3 as a visibility proxy, not a forecast of sales. Comparable
follower counts are used only when present for every dated game. These are explicit
baseline policy weights, not trained XGBoost/LightGBM predictions.

Approximate and unknown dates remain unassigned. The UI shows them separately and
labels rankings provisional. Public Steam search is regional and can change during
pagination; it cannot establish coverage of hidden games or other PC storefronts.
Missing calendar data never means zero competition. Saved reports preserve the
snapshot used when they were generated; generate a new report for refreshed dates.

Optional editorial major releases live in `data/config/major_releases.json` as a JSON
array of `Competitor` records. Each needs a Steam app ID, `coming_soon: true`, source,
observation time, exact verified PC date (`date_precision: "day"`), and
`attention_weight` (1–20), `attention_reason`, `attention_source`. No speculative
GTA/console dates are seeded. For existing discovered apps, only editorial attention
fields override discovery; Steam's current date wins. An added observation must be
no later than the snapshot timestamp and becomes stale after seven days.
