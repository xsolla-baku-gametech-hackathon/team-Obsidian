"""Paginated Steam upcoming discovery with an atomic, offline-readable snapshot."""

import argparse
import asyncio
import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from uuid import uuid4

import httpx
from ili_core.domain.launch import Competitor, Coverage, MarketDataset

from ili_pipeline.launch import exact_release_date, write_atomic
from ili_pipeline.sources.steam import SteamClient, SteamUpstreamError

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data/processed/upcoming.json"
MAJOR_PATH = Path(__file__).resolve().parents[3] / "data/config/major_releases.json"
SEARCH = "https://store.steampowered.com/search/results/"
GENRES = {
    "Action",
    "Adventure",
    "Casual",
    "Indie",
    "RPG",
    "Simulation",
    "Strategy",
    "Sports",
    "Racing",
}


class SearchRows(HTMLParser):
    """Read only Steam app rows; do not infer dates or prices from missing fields."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "a" and "search_result_row" in classes:
            raw = attrs.get("data-ds-appid", "")
            if not raw.isdigit():
                return
            self.row = {
                "app_id": int(raw),
                "name": "",
                "raw": "",
                "tags": json.loads(attrs.get("data-ds-tagids", "[]")),
            }
        if self.row is not None:
            if "title" in classes:
                self.capture = "name"
            elif "search_released" in classes:
                self.capture = "raw"

    def handle_data(self, data):
        if self.row is not None and self.capture:
            self.row[self.capture] += data

    def handle_endtag(self, tag):
        if tag in {"span", "div"}:
            self.capture = None
        if tag == "a" and self.row is not None:
            self.row["name"] = self.row["name"].strip()
            self.row["raw"] = self.row["raw"].strip()
            if not self.row["name"]:
                self.row["name"] = f"Steam app {self.row['app_id']} (title unavailable)"
            self.rows.append(self.row)
            self.row = None


async def discover(
    client: SteamClient, *, region="US", max_pages=400, delay=2.0, checkpoint: Path | None = None
) -> MarketDataset:
    tags_payload = await client._get_json(
        "https://store.steampowered.com/actions/ajaxgetstoretags/", {"l": "english"}
    )
    tags = {item["tagid"]: item["name"] for item in tags_payload.get("tags", [])}
    if not tags:
        raise SteamUpstreamError("Steam tag vocabulary unavailable")

    async def page(params):
        for attempt in range(4):
            try:
                return await client._get_json(SEARCH, params)
            except SteamUpstreamError:
                if attempt == 3:
                    raise
                logging.getLogger(__name__).warning(
                    "Steam upcoming page unavailable; backing off %ss", 30 * (attempt + 1)
                )
                await asyncio.sleep(30 * (attempt + 1))
        raise AssertionError("unreachable")

    rows = {}
    start = 0
    complete = False
    previous_page = None
    started_at = datetime.now(UTC).isoformat()
    if checkpoint and checkpoint.exists():
        try:
            saved = json.loads(checkpoint.read_text())
            age = (datetime.now(UTC) - datetime.fromisoformat(saved["started_at"])).total_seconds()
            if 0 <= age < 3600 and saved["region"] == region:
                rows = {row["app_id"]: row for row in saved["rows"]}
                start = saved["start"]
                previous_page = saved.get("previous_page")
                started_at = saved["started_at"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    for _ in range(max_pages):
        payload = await page(
            {
                "filter": "comingsoon",
                "category1": "998",
                "start": start,
                "count": 100,
                "json": 1,
                "infinite": 1,
                "l": "english",
                "cc": region.lower(),
            },
        )
        parser = SearchRows()
        parser.feed(payload.get("results_html", ""))
        total = int(payload.get("total_count", -1))
        if not parser.rows or total < 0:
            raise SteamUpstreamError("Steam upcoming pagination returned an empty or invalid page")
        signature = [row["app_id"] for row in parser.rows]
        if signature == previous_page:
            raise SteamUpstreamError("Steam upcoming pagination repeated a page")
        previous_page = signature
        rows.update({row["app_id"]: row for row in parser.rows})
        # Steam offsets count slots, including rows hidden or removed by filtering.
        start += 100
        if checkpoint:
            write_atomic(
                checkpoint,
                json.dumps(
                    {
                        "started_at": started_at,
                        "region": region,
                        "rows": list(rows.values()),
                        "start": start,
                        "previous_page": previous_page,
                    }
                ),
            )
        if start >= total:
            complete = True
            break
        logging.getLogger(__name__).info("Discovered %s / %s upcoming games", len(rows), total)
        await asyncio.sleep(delay)
    if not complete:
        raise SteamUpstreamError("Upcoming scan incomplete; keeping the previous snapshot")

    # Optional prelaunch visibility signal. Missing rankings never become zero popularity.
    popular = set()
    try:
        payload = await client._get_json(
            SEARCH,
            {
                "filter": "popularwishlist",
                "category1": "998",
                "start": 0,
                "count": 20,
                "json": 1,
                "infinite": 1,
                "l": "english",
                "cc": region.lower(),
            },
        )
        parser = SearchRows()
        parser.feed(payload.get("results_html", ""))
        popular = {row["app_id"] for row in parser.rows[:20]}
    except (SteamUpstreamError, ValueError):
        pass
    now = datetime.now(UTC)
    games = []
    for row in rows.values():
        release = exact_release_date(row["raw"])
        if release and release < now.date():
            continue
        names = [tags[tag] for tag in row["tags"] if tag in tags]
        games.append(
            Competitor(
                app_id=row["app_id"],
                name=row["name"],
                genres=[n for n in names if n in GENRES],
                tags=names,
                source=f"https://store.steampowered.com/app/{row['app_id']}/",
                observed_at=now,
                coming_soon=True,
                release_date=release,
                release_date_raw=row["raw"] or None,
                date_precision="day" if release else "unknown",
                region=region,
                attention_weight=3 if row["app_id"] in popular else 1,
                attention_reason="Steam top-20 popular wishlist listing (visibility proxy)"
                if row["app_id"] in popular
                else None,
                attention_source="https://store.steampowered.com/search/?filter=popularwishlist"
                if row["app_id"] in popular
                else None,
            )
        )
    return MarketDataset(
        dataset_id=f"upcoming-{uuid4()}",
        collected_at=now,
        games=games,
        coverage=Coverage(
            horizon_start=now.date(),
            horizon_end=now.date() + timedelta(days=731),
            discovery_complete=True,
            discovery_method="steam_paginated_comingsoon",
            notes=f"Enumerated {len(rows)} visible Steam upcoming games in {region}. "
            f"Traversed {start} result rows; repeated app IDs were deduplicated. "
            "Listings may move while pagination runs. "
            "Coverage is limited to public regional Steam search, not all PC storefronts. "
            "Unannounced, hidden and approximate release dates remain uncertain.",
        ),
    )


def load_snapshot(path: Path, major_path: Path | None = None) -> MarketDataset | None:
    try:
        dataset = MarketDataset.model_validate_json(path.read_text())
    except (OSError, ValueError):
        return None
    if major_path is not None and major_path.exists():
        # Full validated observations, including a verified PC/Steam date and source.
        additions = [Competitor.model_validate(row) for row in json.loads(major_path.read_text())]
        games = {game.app_id: game for game in dataset.games}
        for game in additions:
            if game.coming_soon and game.attention_source and game.attention_reason:
                existing = games.get(game.app_id)
                # Fresh discovery wins for dates; editorial record supplies impact only.
                if existing:
                    games[game.app_id] = existing.model_copy(
                        update={
                            "attention_weight": game.attention_weight,
                            "attention_reason": game.attention_reason,
                            "attention_source": game.attention_source,
                        }
                    )
                elif game.observed_at <= dataset.collected_at:
                    games[game.app_id] = game
        dataset = dataset.model_copy(update={"games": list(games.values())})
    return dataset


async def refresh(path=DEFAULT_PATH, *, region="US", max_pages=400):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = sqlite3.connect(path.with_suffix(".lock.sqlite"), timeout=0)
    try:
        try:
            lock.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            raise SteamUpstreamError("Another upcoming refresh is already running") from exc
        async with httpx.AsyncClient(
            timeout=20, headers={"User-Agent": "IndieLaunchIntelligence/0.1"}
        ) as http:
            dataset = await discover(
                SteamClient(http, retries=0),
                region=region,
                max_pages=max_pages,
                checkpoint=path.with_suffix(".partial.json"),
            )
        write_atomic(path, dataset.model_dump_json())
        path.with_suffix(".partial.json").unlink(missing_ok=True)
        return dataset
    finally:
        lock.close()


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--region", choices=["US"], default="US")
    parser.add_argument("--max-pages", type=int, default=400)
    args = parser.parse_args()
    try:
        dataset = asyncio.run(refresh(args.output, region=args.region, max_pages=args.max_pages))
    except (OSError, ValueError, SteamUpstreamError) as exc:
        parser.exit(1, f"Upcoming refresh failed: {exc}\n")
    print(f"Saved {len(dataset.games)} upcoming games to {args.output}")


if __name__ == "__main__":
    main()
