from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
VENV_DIR = REPO_DIR / ".venv"


def venv_executable(name: str) -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / f"{name}.exe"
    return VENV_DIR / "bin" / name


def wait_for_api() -> bool:
    for _ in range(80):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as response:
                if response.status == 200:
                    return True
        except (OSError, urllib.error.URLError):
            time.sleep(0.25)
    return False


def main() -> None:
    uvicorn = venv_executable("uvicorn")
    if not uvicorn.exists():
        raise SystemExit("Missing virtual environment. Run: python scripts/setup_dev.py")

    env = os.environ.copy()
    python_paths = [
        str(REPO_DIR / "apps/api/src"),
        str(REPO_DIR / "pipelines/src"),
        str(REPO_DIR / "packages/core/src"),
    ]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        python_paths.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(python_paths)

    api = subprocess.Popen(
        [str(uvicorn), "ili_api.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
        cwd=REPO_DIR,
        env=env,
    )

    try:
        if not wait_for_api():
            raise SystemExit("API did not start on http://127.0.0.1:8000")

        web = subprocess.Popen(["npm", "run", "dev"], cwd=REPO_DIR / "apps/web")
        try:
            web.wait()
        finally:
            if web.poll() is None:
                web.terminate()
    except KeyboardInterrupt:
        pass
    finally:
        if api.poll() is None:
            if os.name == "nt":
                api.terminate()
            else:
                api.send_signal(signal.SIGTERM)
            try:
                api.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api.kill()

    sys.exit(0)


if __name__ == "__main__":
    main()
