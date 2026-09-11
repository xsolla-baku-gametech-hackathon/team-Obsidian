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

Requirements:

- Python 3.11+
- Node.js + npm
- Internet access for live Steam metadata and upcoming-release refresh

From a fresh clone:

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

Game developers can:

- generate Steam reports
- view saved report history
- apply for ownership verification from a saved report
- publish a game only after manual approval
- see incoming creator key requests

Game developer subscriptions become active immediately in local development.

### Content Creators

Content creators can:

- browse published verified games
- request review/playtest keys
- track their key requests
- manage YouTube verification state

Content creator subscriptions start as `pending_youtube_verification`. The local
development endpoint marks YouTube as verified without real Google OAuth. Production
should replace it with Google OAuth and YouTube channel validation.

## Manual Game Ownership Verification

Developers cannot publish games directly after creating a report. They must submit an
ownership application first.

The application requires:

- saved report ID
- studio name
- applicant name
- applicant role/title
- business email
- company website, official contact/press page, or Steamworks proof link
- optional extra proof URL
- verification notes

The backend rejects weak applications with no strong proof link. It also rejects common
personal email domains such as Gmail, Outlook, Hotmail, and Yahoo for the business email.

Platform owners review applications manually. To enable owner review routes, set:

```text
ILI_ADMIN_TOKEN=your-secret-token
```

Admin requests use:

```text
X-Admin-Token: your-secret-token
```

Relevant endpoints:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/v1/marketplace/ownership/applications` | Developer submits ownership proof |
| `GET /api/v1/marketplace/ownership/applications` | Developer lists their applications |
| `GET /api/v1/marketplace/admin/ownership/applications` | Platform owner lists applications |
| `POST /api/v1/marketplace/admin/ownership/applications/{id}` | Platform owner approves/rejects |
| `POST /api/v1/marketplace/games` | Developer publishes approved game |
| `GET /api/v1/marketplace/games` | List published games |
| `POST /api/v1/marketplace/games/{id}/key-requests` | Creator requests a key |
| `GET /api/v1/marketplace/key-requests/mine` | Creator lists their requests |
| `GET /api/v1/marketplace/key-requests/incoming` | Developer lists incoming requests |

## Game Key Workflow

The current implementation stores key requests, not actual Steam keys.

Recommended production flow:

1. Creator requests a key.
2. Developer reviews the creator profile.
3. Developer approves or rejects the request.
4. The system assigns one unused encrypted key.
5. Creator sees the claimed key.

Future database objects should include key batches and encrypted individual keys with
statuses such as `available`, `reserved`, `claimed`, and `revoked`.

## Data Files

Large data files are not committed to git.

Expected historical Steam catalog CSV path:

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

The importer creates:

```text
data/processed/steam-catalog.sqlite
```

Reports still work partially without the historical CSV. Live Steam metadata and
upcoming release timing can work, but historical price comparisons and similarity
matches will be limited.

Upcoming release timing uses:

```text
data/processed/upcoming.json
```

Refresh manually:

```powershell
.venv/Scripts/python -m ili_pipeline.upcoming
```

On macOS/Linux:

```bash
PYTHONPATH=packages/core/src:pipelines/src .venv/bin/python -m ili_pipeline.upcoming
```

## Environment Variables

Copy `.env.example` to `.env` for local overrides.

| Variable | Purpose |
| --- | --- |
| `ILI_STEAM_TIMEOUT_SECONDS` | Timeout for Steam requests |
| `ILI_STEAM_CACHE_TTL_SECONDS` | In-memory Steam cache TTL |
| `ILI_STEAM_USER_AGENT` | User agent sent to Steam |
| `ILI_CORS_ORIGINS` | Allowed frontend origins |
| `ILI_CATALOG_PATH` | Optional historical catalog SQLite path |
| `ILI_USER_DB_PATH` | Optional user/report/marketplace SQLite path |
| `ILI_SESSION_TTL_HOURS` | Bearer session lifetime |
| `ILI_ADMIN_TOKEN` | Enables platform-owner manual approval routes |
| `ILI_UPCOMING_PATH` | Optional upcoming-release JSON path |
| `ILI_MAJOR_RELEASES_PATH` | Optional editorial major-release config path |
| `ILI_UPCOMING_AUTO_REFRESH` | Enable/disable API background upcoming refresh |

## API Summary

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
