# Developer tooling

Reserved for repeatable setup, contract generation, snapshot publication, and demo
commands. Wrappers call application/package entry points; business logic stays in
core or pipeline modules. Add documented commands only when implemented.

## Local setup

Use this from the repository root after cloning:

```bash
chmod +x scripts/setup_dev.sh scripts/dev.sh scripts/run_api.sh
./scripts/setup_dev.sh
./scripts/dev.sh
```

`setup_dev.sh` installs Python and frontend dependencies, imports
`data/raw/steam/steam_games.csv` when present, and refreshes the upcoming Steam
calendar. Set `SKIP_UPCOMING=1` to skip the calendar scan during quick frontend work.

`dev.sh` starts the FastAPI backend on `http://127.0.0.1:8000` and then starts the
Vite frontend on `http://localhost:5173`.
