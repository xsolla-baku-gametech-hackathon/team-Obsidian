"""Stream the downloaded Kaggle CSV into an indexed SQLite catalog."""

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ili_core.recommendation.launch import labels
from ili_core.storage.catalog import CatalogGame

from ili_pipeline.launch import exact_release_date


def parse_labels(raw: str) -> list[str]:
    value = json.loads(raw) if raw.strip() else []
    if isinstance(value, dict):
        value = list(value)
    if isinstance(value, list):
        value = [
            item.get("description", item.get("name")) if isinstance(item, dict) else item
            for item in value
        ]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("Expected a JSON list of labels or tag dictionary")
    return list(dict.fromkeys(item.strip() for item in value if item.strip()))


def number(raw: str) -> int | None:
    try:
        value = int(float(raw))
        return value if value >= 0 else None
    except (ValueError, OverflowError):
        return None


def import_catalog(source: Path, destination: Path) -> dict:
    csv.field_size_limit(20_000_000)
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(suffix=".sqlite", dir=destination.parent)
    os.close(handle)
    imported = skipped = future = 0
    with source.open("rb") as raw:
        digest = hashlib.file_digest(raw, "sha256").hexdigest()
    try:
        with sqlite3.connect(temporary) as db:
            db.executescript(
                "CREATE TABLE games (app_id INTEGER PRIMARY KEY, release_date TEXT, payload TEXT);"
                "CREATE TABLE features (label TEXT, app_id INTEGER, weight INTEGER, "
                "PRIMARY KEY(label, app_id)); CREATE TABLE metadata (value TEXT);"
            )
            with source.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                required = {"app_id", "name", "release_date", "genres", "tags", "price_status"}
                if not required.issubset(reader.fieldnames or []):
                    raise ValueError(f"CSV missing required fields: {sorted(required)}")
                for row in reader:
                    try:
                        positive, negative = (
                            number(row.get("positive", "")),
                            number(row.get("negative", "")),
                        )
                        game = CatalogGame(
                            app_id=int(row["app_id"]),
                            name=row["name"],
                            genres=parse_labels(row["genres"])[:50],
                            tags=parse_labels(row["tags"])[:100],
                            description=(row.get("short_description") or "")[:10000],
                            business_model="free" if row["price_status"] == "free" else "premium",
                            release_date=exact_release_date(row["release_date"]),
                            release_date_raw=row["release_date"],
                            review_count=positive + negative
                            if positive is not None and negative is not None
                            else None,
                            peak_ccu=number(row.get("peak_ccu", "")),
                        )
                        db.execute(
                            "INSERT INTO games VALUES (?, ?, ?)",
                            (
                                game.app_id,
                                game.release_date.isoformat() if game.release_date else None,
                                game.model_dump_json(),
                            ),
                        )
                    except (ValueError, TypeError, sqlite3.IntegrityError):
                        skipped += 1
                        continue
                    db.executemany(
                        "INSERT INTO features VALUES (?, ?, ?)",
                        [
                            *[(f"tag:{tag}", game.app_id, 3) for tag in labels(game.tags)],
                            *[(f"genre:{genre}", game.app_id, 1) for genre in labels(game.genres)],
                        ],
                    )
                    imported += 1
                    future += bool(
                        game.release_date and game.release_date > datetime.now(UTC).date()
                    )
            if not imported:
                raise ValueError("CSV contains no usable games; previous catalog preserved")
            metadata = {
                "dataset_id": f"kaggle-{digest[:16]}",
                "source_file": source.name,
                "source_sha256": digest,
                "imported_at": datetime.now(UTC).isoformat(),
                "game_count": imported,
                "skipped_count": skipped,
                "future_release_count": future,
                "source_observed_at": None,
                "source_url": "https://www.kaggle.com/datasets/hubertsidorowicz/"
                "steam-games-dataset-daily-updates",
            }
            db.execute("INSERT INTO metadata VALUES (?)", (json.dumps(metadata),))
            db.execute("CREATE INDEX release_dates ON games(release_date)")
        os.replace(temporary, destination)
        return metadata
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/raw/steam/steam_games.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/steam-catalog.sqlite"))
    args = parser.parse_args()
    print(json.dumps(import_catalog(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
