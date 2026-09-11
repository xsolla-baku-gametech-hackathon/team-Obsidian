# Indie Launch Intelligence

**Don't guess when to launch your game. Launch when the market gives you the best opportunity.**

Indie Launch Intelligence is a decision-support platform for indie game teams. It
analyzes Steam data, upcoming release pressure, historical comparables, pricing context,
and creator-marketplace activity so developers can choose better launch windows and
connect with content creators before release.

The goal is not to predict whether a game will succeed. The product gives developers
market context before making launch decisions.

## What The App Does

- Generates Steam game reports from a Steam store link.
- Compares the target game against historical Steam catalog data.
- Scores upcoming release windows using upcoming Steam releases.
- Stores report history per user.
- Supports paid-role onboarding for game developers and content creators.
- Lets game developers apply for manual ownership verification.
- Blocks game publishing until platform owners approve ownership.
- Lets content creators browse verified published games.
- Lets content creators request review/playtest keys.
- Lets game developers view incoming key requests.

## Tech Stack

| Area | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite, lucide-react |
| Backend | Python, FastAPI REST API |
| Storage | SQLite for local users, reports, marketplace, processed catalog |
| Data pipeline | Python collectors/importers for Steam catalog and upcoming releases |
| ML/recommendation | Shared Python core package with explainable baseline scoring |
| Data files | CSV, JSON, SQLite |

## Run The Full Project

From a fresh clone, with Python 3.11+ and Node.js installed:

```powershell
cd team-Obsidian
python scripts/setup_dev.py
python scripts/dev.py
```

Then open:

- Frontend: `http://localhost:5173`
- API docs: `http://127.0.0.1:8000/docs`

`scripts/setup_dev.py` creates `.venv`, installs backend/core/pipeline packages,
installs frontend dependencies, imports the local Steam catalog when available, and
refreshes the upcoming Steam calendar. The upcoming Steam scan can take several minutes.

For a faster first setup:

```powershell
python scripts/setup_dev.py --skip-upcoming
python scripts/dev.py
```

The API will try to refresh missing or stale upcoming data in the background.

macOS/Linux convenience wrappers also exist:

```bash
./scripts/setup_dev.sh
./scripts/dev.sh
```

The Python scripts are the recommended cross-platform commands for Windows, macOS, and
Linux.

## Demo Database

Use the demo database when presenting the role-based marketplace flow to reviewers.

Create or reset demo data:

```powershell
python scripts/seed_demo_data.py --reset
```

Run the app with the demo user database:

```powershell
$env:ILI_USER_DB_PATH="data/processed/demo-users.sqlite"
python scripts/dev.py
```

On macOS/Linux:

```bash
ILI_USER_DB_PATH=data/processed/demo-users.sqlite python scripts/dev.py
```

Demo accounts:

| Role | Email | Password |
| --- | --- | --- |
| Game developer | `gamedev@demo.studio` | `Demo-password1` |
| Content creator | `creator@demo.channel` | `Demo-password1` |

The demo seed includes:

- 3 saved reports
- 3 ownership applications: approved, pending, rejected
- 1 published game
- 1 creator key request
- active developer and creator subscriptions
- verified demo YouTube state for the creator

Generated SQLite files are ignored by git. The script is committed; the database is
recreated locally.

## User Roles

Users sign up or log in normally first. They do not choose a role during signup.
After login, they choose a subscription plan and workspace role.

### Game Developers

### Fast setup

To get the app running without waiting for the upcoming Steam calendar scan, use:

```powershell
cd team-Obsidian
python scripts/setup_dev.py --skip-upcoming
python scripts/dev.py
```

This installs all frontend and backend dependencies, but skips only the initial
upcoming-release refresh. The API refreshes missing or stale upcoming data in the
background after it starts.

The large Steam catalog is not committed to git. To unlock historical competitor and
price comparisons, download the Steam Games Dataset CSV and place it here before or
after setup:

```text
data/raw/steam/steam_games.csv
```

Dataset source:

```text
https://www.kaggle.com/datasets/hubertsidorowicz/steam-games-dataset-daily-updates
```

After placing the CSV, import it:

```powershell
.venv/Scripts/python -m ili_pipeline.catalog
```

On macOS/Linux:

```bash
.venv/bin/python -m ili_pipeline.catalog
```

Reports can still use live Steam metadata and the upcoming release calendar without
the historical CSV, but price comparisons and historical similarity matches will be
limited.

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/auth/signup` | Create account and bearer session |
| `POST /api/v1/auth/login` | Create bearer session |
| `POST /api/v1/auth/logout` | Delete current session |
| `GET /api/v1/auth/me` | Get current user |
| `POST /api/v1/auth/subscription` | Choose plan and role |
| `POST /api/v1/auth/youtube/dev-verify` | Local creator YouTube verification placeholder |
| `POST /api/v1/steam/games/inspect` | Fetch Steam metadata/reviews/player signals |
| `POST /api/v1/steam/games/analyze` | Generate and save full report |
| `GET /api/v1/reports` | List saved reports |
| `GET /api/v1/reports/{id}` | Open saved report |
| `POST /api/v1/recommendations` | Run recommendation model with supplied snapshot |

Most report, recommendation, and marketplace routes require:

```text
Authorization: Bearer <token>
```

## Validation

Run backend tests and lint:

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/ruff check scripts apps/api packages/core pipelines
```

On macOS/Linux:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check scripts apps/api packages/core pipelines
```

Run frontend build:

```powershell
npm run build --prefix apps/web
```

## Repository Layout

| Path | Purpose | Primary owner |
| --- | --- | --- |
| `apps/web` | React + TypeScript dashboard | Frontend |
| `apps/api` | FastAPI API and future LLM adapters | Backend |
| `pipelines` | Steam collection, normalization, publication | Backend + ML |
| `packages/core` | Shared domain models, scoring, storage | Backend + ML |
| `contracts` | API and snapshot contracts | All |
| `ml` | Experiments and model promotion notes | ML |
| `data` | Local raw/processed/snapshot data workspace | Backend + ML |
| `scripts` | Setup, dev runner, demo seeding, tooling | All |
| `infra` | Deployment notes | Shared |

## More Documentation

- [Backend API guide](apps/api/README.md)
- [Frontend guide](apps/web/README.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Integration contracts](contracts/README.md)
- [Team workflow](docs/TEAM_WORKFLOW.md)
- [Data policy](data/README.md)
- [ML workspace](ml/README.md)
- [Hackathon notes](docs/HACKATHON.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
