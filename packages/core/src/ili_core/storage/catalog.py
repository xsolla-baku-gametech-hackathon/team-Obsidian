"""Read-only indexed Steam catalog. Import time is not a source observation time."""

import json
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from ili_core.domain.launch import GameProfile
from ili_core.recommendation.launch import labels


class CatalogUnavailable(Exception):
    pass


class CatalogGame(GameProfile):
    release_date: date | None = None
    release_date_raw: str = ""
    review_count: int | None = None
    peak_ccu: int | None = None


class SteamCatalog:
    def __init__(self, path: Path):
        self.path = path.resolve()

    def _connect(self) -> sqlite3.Connection:
        if not self.path.is_file():
            raise CatalogUnavailable("The Steam catalog has not been imported yet.")
        return sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)

    def metadata(self) -> dict:
        try:
            with closing(self._connect()) as db:
                return json.loads(db.execute("SELECT value FROM metadata").fetchone()[0])
        except (sqlite3.Error, TypeError, ValueError) as exc:
            raise CatalogUnavailable("The Steam catalog is invalid; rebuild the import.") from exc

    def get(self, app_id: int) -> CatalogGame | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT payload FROM games WHERE app_id=?", (app_id,)).fetchone()
        return CatalogGame.model_validate_json(row[0]) if row else None

    def candidates(
        self, target: GameProfile, *, released_since: date | None = None
    ) -> list[CatalogGame]:
        features = sorted(
            {f"tag:{tag}" for tag in labels(target.tags)}
            | {f"genre:{genre}" for genre in labels(target.genres)}
        )
        if not features:
            return []
        placeholders = ",".join("?" for _ in features)
        date_filter = "AND g.release_date >= ? AND g.release_date <= ?" if released_since else ""
        params = [*features, target.app_id or 0]
        if released_since:
            params.extend([released_since.isoformat(), date.today().isoformat()])
        with closing(self._connect()) as db:
            rows = db.execute(
                f"SELECT g.payload FROM features f JOIN games g ON g.app_id=f.app_id "
                f"WHERE f.label IN ({placeholders}) AND g.app_id != ? {date_filter} "
                "GROUP BY g.app_id ORDER BY SUM(f.weight) DESC, g.app_id LIMIT 600",
                params,
            ).fetchall()
        return [CatalogGame.model_validate_json(row[0]) for row in rows]
