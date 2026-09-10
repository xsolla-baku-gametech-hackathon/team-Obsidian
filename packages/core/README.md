# Shared Python core

`ili_core` is the shared runtime package for the API and pipeline. `domain` contains
canonical records; `analytics` builds weekly features; `recommendation` provides pure
ranking and coverage policy; `storage` owns repository interfaces and SQLite adapters.
Scoring accepts records and has no database, network, or web-framework dependencies.

No executable package is implemented yet. See [architecture](../../docs/ARCHITECTURE.md).
