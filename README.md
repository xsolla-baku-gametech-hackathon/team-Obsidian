# Indie Launch Intelligence

**Don’t guess when to launch your game. Launch when the market gives you the best opportunity.**

A decision-support platform helping indie developers understand Steam release
competition before choosing a launch window. Planned views include a genre saturation
heatmap, competitor timeline, and explainable launch recommendations using real market
data with a cached offline fallback. It provides market context, not success predictions.

## Repository status

The React frontend accepts a Steam link and displays a generated report with catalog
competitors, live Steam price comparisons, and recommendation evidence. The paywall
is temporarily disabled. Checkout and deployment remain pending.

Run the frontend with `cd apps/web && npm install && npm run dev`. See the
[frontend guide](apps/web/README.md) for build commands and integration boundaries.
The first backend slice is implemented: a FastAPI REST endpoint accepts a Steam Store
game link and returns normalized metadata, up to 100 recent reviews, review totals, and
the current concurrent-player count. The CSV-to-SQLite importer and Steam-link report
flow are also implemented. The explainable recommendation baseline supports
competitor matching, release-window ranking with coverage checks, and comparable
price recommendations through `POST /api/v1/recommendations`. A CLI collects selected
Steam apps and runs offline inference; exhaustive upcoming discovery is still pending.
The downloaded catalog contains no future releases, so reports explain that live
upcoming discovery is needed before recommending a launch date. See the
[model card and usage guide](ml/MODEL_CARD.md).

See the [API guide](apps/api/README.md) for setup, request examples, and tests.

## Start here

- [Architecture and target file tree](docs/ARCHITECTURE.md): boundaries, data flow, model integration, offline design, and growth path.
- [Integration contracts](contracts/README.md): proposed API, shared records, and snapshot format.
- [Team workflow](docs/TEAM_WORKFLOW.md): ownership, implementation order, and validation.
- [Data policy](data/README.md): provenance, cached exports, and real versus synthetic data.
- [ML workspace](ml/README.md): baseline, experiments, and future model promotion.
- [Hackathon information](docs/HACKATHON.md) and [Code of Conduct](CODE_OF_CONDUCT.md).

## Layout

| Path | Purpose | Primary owner |
| --- | --- | --- |
| `apps/web` | React + TypeScript dashboard | Frontend |
| `apps/api` | Python FastAPI API and future LLM adapters | Backend |
| `pipelines` | Steam collection, normalization, publication | Backend + ML |
| `packages/core` | Shared domain, analytics, scoring, storage interfaces | Backend + ML |
| `contracts` | API and offline snapshot handoff | All three roles |
| `ml` | Experiments and evaluation, outside serving code | ML |
| `data` | Local datasets and snapshot staging | Backend + ML |
| `infra`, `scripts`, `tests/e2e` | Deployment, tooling, integration checks | Shared |

The API and pipeline import the same recommendation package. The frontend consumes
versioned results over HTTP or from a validated JSON snapshot. Future LLM integrations
explain those results through the backend.
