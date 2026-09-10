# Shared Python core

`ili_core` is the shared runtime package for the API and pipeline. `domain` contains
canonical records; `analytics` builds weekly features; `recommendation` provides pure
ranking and coverage policy; `storage` owns repository interfaces and SQLite adapters.
Scoring accepts records and has no database, network, or web-framework dependencies.

`domain.launch` implements validated recommendation inputs and results;
`recommendation.launch.recommend` implements competitor matching, coverage-gated
release ranking, and comparable pricing. See the [model card](../../ml/MODEL_CARD.md).
Persistence and the broader dashboard analytics remain planned.
