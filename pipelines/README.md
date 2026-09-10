# Data pipeline

`python -m ili_pipeline.catalog` imports `data/raw/steam/steam_games.csv` into the
indexed SQLite catalog at `data/processed/steam-catalog.sqlite`. It handles both
string-list and object-list genre formats and tag-vote dictionaries, records the
source SHA-256 and validation counts, and preserves the previous catalog on failure.
The catalog supports the website's automatic competitor matching. The CSV's source
observation time is unknown; import time does not make its prices fresh.

Planned `ili_pipeline` job: collect, normalize, validate, store, analyze, export.
Source adapters handle bounded retries/timeouts. Refresh orchestration owns the single
writer lock and preserves the last valid dataset on failure. Import analytics and
recommendations from `ili_core`; do not duplicate API or model logic.

`python -m ili_pipeline.launch collect` collects selected Steam app IDs into a
validated recommendation request. `python -m ili_pipeline.launch recommend` runs
offline inference and writes an atomic JSON report. See the
[model card](../ml/MODEL_CARD.md) for commands and coverage limitations.
Bulk upcoming discovery and publication of complete dashboard snapshots remain pending.
