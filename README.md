# Indie Launch Intelligence

**Don’t guess when to launch your game. Launch when the market gives you the best opportunity.**

A decision-support platform helping indie developers understand Steam release
competition before choosing a launch window. Planned views include a genre saturation
heatmap, competitor timeline, and explainable launch recommendations using real market
data with a cached offline fallback. It provides market context, not success predictions.

## Repository status

This repository contains the architecture and tracked directory scaffold. The scraper,
API, model, dashboard, datasets, dependency manifests, and deployment are not implemented
yet. There are no installation or application launch commands at this stage.

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
