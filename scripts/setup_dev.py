from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
VENV_DIR = REPO_DIR / ".venv"


def npm_executable() -> str:
    """Return the npm launcher that subprocess can execute on this platform."""
    return "npm.cmd" if os.name == "nt" else "npm"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f"$ {' '.join(command)}")
    subprocess.run(command, cwd=REPO_DIR, env=env, check=True)


def ensure_command(command: str, install_hint: str) -> None:
    if shutil.which(command) is None:
        raise SystemExit(f"{command} is required. {install_hint}") from None


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a local development environment.")
    parser.add_argument(
        "--skip-upcoming",
        action="store_true",
        help="Skip the Steam upcoming calendar refresh. The API can refresh it later.",
    )
    args = parser.parse_args()

    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11+ is required.")

    npm = npm_executable()
    ensure_command(npm, "Install Node.js from https://nodejs.org/")

    if not venv_python().exists():
        run([sys.executable, "-m", "venv", str(VENV_DIR)])

    python = str(venv_python())
    run([python, "-m", "pip", "install", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "-e", "packages/core", "-e", "pipelines", "-e", "apps/api[dev]"])

    (REPO_DIR / "data" / "raw" / "steam").mkdir(parents=True, exist_ok=True)
    (REPO_DIR / "data" / "processed").mkdir(parents=True, exist_ok=True)

    catalog_csv = REPO_DIR / "data" / "raw" / "steam" / "steam_games.csv"
    if catalog_csv.exists():
        run([python, "-m", "ili_pipeline.catalog"])
    else:
        print(
            "\nHistorical catalog not imported because data/raw/steam/steam_games.csv is missing.\n"
            "Download the Steam Games Dataset from Kaggle and place steam_games.csv there,\n"
            "then run: .venv\\Scripts\\python -m ili_pipeline.catalog on Windows or\n"
            ".venv/bin/python -m ili_pipeline.catalog on macOS/Linux.\n"
        )

    if args.skip_upcoming:
        print("Skipped upcoming calendar refresh.")
    else:
        env = os.environ.copy()
        paths = [REPO_DIR / "packages/core/src", REPO_DIR / "pipelines/src"]
        env["PYTHONPATH"] = os.pathsep.join(str(path) for path in paths)
        run([python, "-m", "ili_pipeline.upcoming"], env=env)

    run([npm, "install", "--prefix", "apps/web"])

    print(
        "\nSetup finished.\n\n"
        "Start the full app with:\n"
        "python scripts/dev.py\n\n"
        "Frontend: http://localhost:5173\n"
        "API docs:  http://127.0.0.1:8000/docs"
    )


if __name__ == "__main__":
    main()
