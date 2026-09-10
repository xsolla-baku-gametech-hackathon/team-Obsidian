import json
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
for source_root in ("apps/api/src", "pipelines/src", "packages/core/src"):
    sys.path.insert(0, os.fspath(REPOSITORY_ROOT / source_root))

from ili_api.main import app  # noqa: E402


def main() -> None:
    destination = REPOSITORY_ROOT / "contracts/openapi.json"
    destination.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {destination.relative_to(REPOSITORY_ROOT)}")


if __name__ == "__main__":
    main()
