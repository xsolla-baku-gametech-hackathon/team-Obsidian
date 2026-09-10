# Backend API

The website uses `POST /api/v1/steam/games/analyze` with just
`{"steam_url":"https://store.steampowered.com/app/413150/"}`. This route reads the
indexed catalog, looks up the game on Steam, matches similar titles, refreshes up to
20 competitor records, and runs the model. It returns catalog provenance, matched
games, regular prices, price advice, release advice, and explicit data limitations.
Optional inputs: uppercase `country_code` (default US), `earliest_date` and
`latest_date` (both required if overriding the default next 90 days).

After installing dependencies, import the supplied CSV once:

```bash
.venv/bin/python -m ili_pipeline.catalog
./scripts/run_api.sh
```

The default input is `data/raw/steam/steam_games.csv`; the output is
`data/processed/steam-catalog.sqlite`. Import is streaming and publication is atomic.
Set `ILI_CATALOG_PATH` to override the API's default catalog location. Missing catalog
returns 503 with instructions; a failed upstream lookup falls back to catalog details
when present. Reports cache for five minutes. Prices are only taken from successful
live Steam refreshes, never assigned a new timestamp from CSV import time.

`POST /api/v1/recommendations` accepts a game profile and validated market snapshot
and returns competitor matches, release advice, comparable pricing, and explanations.
See the [model card](../../ml/MODEL_CARD.md) for collection and request instructions.
This endpoint uses local inference without Steam or LLM network calls.

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
