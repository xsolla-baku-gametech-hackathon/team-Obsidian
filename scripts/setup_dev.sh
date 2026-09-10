#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_dir}"

python_bin="${PYTHON:-python3}"

if ! command -v "${python_bin}" >/dev/null 2>&1; then
  echo "Python 3.11+ is required. Install Python, then run this script again." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js and npm are required. Install Node.js, then run this script again." >&2
  exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
  "${python_bin}" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e packages/core -e pipelines -e 'apps/api[dev]'

mkdir -p data/raw/steam data/processed

if [[ -f "data/raw/steam/steam_games.csv" ]]; then
  .venv/bin/python -m ili_pipeline.catalog
else
  cat <<'MSG'
Historical catalog not imported because data/raw/steam/steam_games.csv is missing.
Download the Steam Games Dataset from Kaggle:
https://www.kaggle.com/datasets/hubertsidorowicz/steam-games-dataset-daily-updates

Place steam_games.csv at data/raw/steam/steam_games.csv, then run:
.venv/bin/python -m ili_pipeline.catalog
MSG
fi

if [[ "${SKIP_UPCOMING:-0}" != "1" ]]; then
  PYTHONPATH=packages/core/src:pipelines/src .venv/bin/python -m ili_pipeline.upcoming
else
  echo "Skipped upcoming calendar refresh because SKIP_UPCOMING=1."
fi

npm install --prefix apps/web

cat <<'MSG'

Setup finished.

Run the whole app from the repository root:
./scripts/dev.sh

Frontend: http://localhost:5173
API docs:  http://127.0.0.1:8000/docs
MSG
