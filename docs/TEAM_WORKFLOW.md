# Team workflow

## Ownership and handoffs

| Team | First deliverable | Handoff |
| --- | --- | --- |
| Backend | Canonical game/dataset records, one source adapter, repository, read API | Validated real dataset + generated OpenAPI |
| ML engineer | Segment mapping, weekly bucketing, coverage policy, count baseline | Pure core functions + versioned scoring examples |
| Frontend | Three feature views, shared filter state, API/snapshot adapters | UI wired to the agreed response envelopes |

Backend and ML jointly review `packages/core/domain`, repository inputs, and contracts.
Keep HTTP request schemas in API and reusable domain types in core. Frontend can use
clearly labeled synthetic test fixtures while collection is built; the final demo must
show provenance for actual records. Experiments must not change production behavior
until their model/policy versions are explicitly promoted.

## Implementation sequence

1. **Contract first:** create Python/Node manifests and lockfiles, implement canonical
   records, agree on segment taxonomy/date handling, and build one vertical slice from
   one real source record to a visible competitor. Add actual run commands to README.
2. **Parallel build:** backend expands ingestion and read routes; ML implements weekly
   aggregation and baseline/abstention; frontend builds three views against the contract.
3. **Integrate:** export OpenAPI/client, use shared scoring in API and snapshot exporter,
   join dashboard filters, and verify all views reference the same dataset ID.
4. **Demo hardening:** collect a bounded real sample, publish a validated fallback,
   verify freshness/coverage labels, run without external internet, and rehearse.
5. **After MVP:** improve discovery coverage and evaluate the baseline before adding
   trained ranking, LLM explanations, saved projects, or extra platforms.

For the 26-hour sprint, prioritize the first four steps. Authentication, model training,
vector databases, distributed queues, and public refresh controls are outside that MVP.

## Validation to implement with the code

- Core: Monday/year boundaries, multiple tags without duplicate app counts, unknown
  dates, null versus zero, tied/all-zero weeks, coverage abstention, deterministic ranking.
- Pipeline: saved source-response fixtures, malformed inputs, deduplication, bounded
  retries, failed refresh preserving the previous dataset, and atomic snapshot publication.
- API: validation/error envelope, consistent dataset IDs, missing-data behavior, and
  parity between API recommendations and exports for identical inputs.
- Frontend: genre filters update all views, unknown coverage renders distinctly from
  an observed zero, and unsupported snapshot filters are disabled.
- End to end: real-data vertical slice, API failure switches the whole dashboard to a
  snapshot, and local assets still load with external internet disconnected.
- Later LLM: invented evidence rejection, prompt injection fixtures, timeout fallback,
  and invariant canonical scores with the provider disabled or failing.

Use deterministic fixtures for routine CI; keep real upstream smoke checks manual or
scheduled so source availability does not block every PR. Once manifests exist, CI runs
Python lint/tests, TypeScript checking, frontend build, and contract drift checks. Add
an end-to-end smoke job once the integrated application is runnable.

## Collaboration conventions

Use short branches such as `feat/steam-ingestion`, `feat/heatmap`, or `feat/ranking-baseline`.
Keep pull requests focused; describe behavior, contract changes, and validation. Commit
migrations alongside storage changes. Coordinate root manifests and generated contracts
with affected teammates; avoid concurrent hand edits to generated clients.

Commit no API keys, local databases, downloaded raw responses, or binary model artifacts.
A curated real fallback JSON may be committed under `apps/web/public/data/` after
checking provenance and source reuse conditions. `.env.example` will document settings
when runtime configuration exists; only public API URLs belong in browser configuration.
