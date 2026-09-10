# Developer tooling

Reserved for repeatable setup, contract generation, snapshot publication, and demo
commands. Wrappers call application/package entry points; business logic stays in
core or pipeline modules. Add documented commands only when implemented.

## Local setup

Use this from the repository root after cloning:

```powershell
python scripts/setup_dev.py
python scripts/dev.py
```

`setup_dev.py` installs Python and frontend dependencies, imports
`data/raw/steam/steam_games.csv` when present, and refreshes the upcoming Steam
calendar. Use `python scripts/setup_dev.py --skip-upcoming` to skip the calendar scan
during quick frontend work.

`dev.py` starts the FastAPI backend on `http://127.0.0.1:8000` and then starts the
Vite frontend on `http://localhost:5173`.

The `.sh` files are convenience wrappers for macOS/Linux. The Python scripts are the
cross-platform commands for Windows, macOS, and Linux.
