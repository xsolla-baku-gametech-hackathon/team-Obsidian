# Data pipeline

Planned `ili_pipeline` job: collect, normalize, validate, store, analyze, export.
Source adapters handle bounded retries/timeouts. Refresh orchestration owns the single
writer lock and preserves the last valid dataset on failure. Import analytics and
recommendations from `ili_core`; do not duplicate API or model logic.

No scraper or CLI is implemented yet. See [architecture](../docs/ARCHITECTURE.md).
