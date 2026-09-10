# Dataset workspace

- `raw/`: source responses with retrieval timestamps; local and ignored.
- `processed/`: canonical SQLite database and derived CSV; local and ignored.
- `snapshots/`: candidate and historical validated JSON exports; local and ignored.

No game data is included yet. Store source name, retrieval time, selection filters,
dataset ID, and quality counts for each real collection. Preserve release-date precision
and distinguish unavailable metrics from observed zeros. Do not relabel synthetic test
fixtures as real Steam data.

Publish a bounded validated real-data snapshot to `apps/web/public/data/snapshot.json`
when ready. Include provenance, horizon, taxonomy, schema and model versions, and sampled
coverage. Both the API and exporter must use the same core analytics and scoring code.
A failed refresh must preserve the last usable database version and snapshot. See the
[architecture](../docs/ARCHITECTURE.md) and [snapshot contract](../contracts/README.md).
