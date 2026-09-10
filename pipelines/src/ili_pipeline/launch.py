"""Collect Steam comparison data and run the launch advisor from the command line."""

import argparse
import asyncio
import os
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from ili_core.domain.launch import (
    Competitor,
    Coverage,
    GameProfile,
    LaunchRequest,
    MarketDataset,
)
from ili_core.domain.steam import SteamGameInspection
from ili_core.recommendation.launch import recommend

from ili_pipeline.sources.steam import (
    SteamClient,
    SteamGameNotFound,
    SteamUpstreamError,
    extract_app_id,
)


def exact_release_date(raw: str | None) -> date | None:
    """Parse only exact English calendar dates; never invent a day for a quarter."""
    if raw:
        for pattern in ("%b %d, %Y", "%d %b, %Y", "%B %d, %Y", "%d %B, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw.strip(), pattern).date()
            except ValueError:
                pass
    return None


def observation(inspection: SteamGameInspection, region: str) -> Competitor:
    game = inspection.metadata
    release = exact_release_date(game.release_date.raw)
    return Competitor(
        app_id=game.app_id,
        name=game.name,
        genres=[genre.name for genre in game.genres],
        description=game.short_description or "",
        business_model="free" if game.is_free else "premium",
        source=game.store_url,
        observed_at=inspection.fetched_at,
        release_date=release,
        release_date_raw=game.release_date.raw,
        date_precision="day" if release else "unknown",
        coming_soon=game.release_date.coming_soon,
        regular_price_minor=game.price.initial_minor if game.price else None,
        currency=game.price.currency if game.price else "USD",
        region=region,
    )


def write_atomic(path: Path, content: str) -> None:
    """Leave the previous valid result intact if collection or serialization fails."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, encoding="utf-8", delete=False
        ) as handle:
            temporary = handle.name
            handle.write(content + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


async def collect(
    client: SteamClient,
    *,
    app_ids: list[int],
    target_app_id: int,
    earliest: date,
    latest: date,
    region: str,
) -> LaunchRequest:
    ids = sorted(set(app_ids) | {target_app_id})
    if not ids or len(ids) > 200 or any(not 0 < app_id <= 4_294_967_295 for app_id in ids):
        raise ValueError("Provide at most 200 positive Steam app IDs (including the target)")
    games = []
    target = None
    for index, app_id in enumerate(ids):
        inspection = await client.fetch_game(app_id, country_code=region, review_count=1)
        if inspection.metadata.app_type != "game":
            if app_id == target_app_id:
                raise ValueError("Target must be a Steam game, not a DLC, demo, or tool")
            continue
        record = observation(inspection, region)
        if app_id == target_app_id:
            target = GameProfile.model_validate(
                {field: getattr(record, field) for field in GameProfile.model_fields}
            )
        else:
            games.append(record)
        if index < len(ids) - 1:
            await asyncio.sleep(0.35)
    if target is None:
        raise ValueError("Target Steam game could not be collected")
    return LaunchRequest(
        game=target,
        earliest_date=earliest,
        latest_date=latest,
        region=region,
        currency=next((game.currency for game in games if game.regular_price_minor), "USD"),
        dataset=MarketDataset(
            dataset_id=f"steam-{uuid4()}",
            collected_at=datetime.now(UTC),
            games=games,
            coverage=Coverage(
                horizon_start=earliest,
                horizon_end=latest + timedelta(days=1),
                discovery_complete=False,
                discovery_method="explicit_steam_app_ids",
                notes="User-selected competitor sample. No exhaustive upcoming discovery was "
                "performed; release advice must abstain. Tags and followers are unavailable "
                "from this adapter. Prices and metadata were retrieved directly from Steam.",
            ),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collection = commands.add_parser("collect", help="Collect an explicitly sampled Steam dataset")
    collection.add_argument("--steam-url", required=True)
    collection.add_argument("--app-ids", type=int, nargs="+", required=True)
    collection.add_argument("--earliest", type=date.fromisoformat, required=True)
    collection.add_argument("--latest", type=date.fromisoformat, required=True)
    collection.add_argument("--region", default="US")
    collection.add_argument("--output", type=Path, required=True)
    inference = commands.add_parser("recommend", help="Run offline inference on a request JSON")
    inference.add_argument("--request", type=Path, required=True)
    inference.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "recommend":
            request = LaunchRequest.model_validate_json(args.request.read_text(encoding="utf-8"))
            result = recommend(request)
        else:
            # Validate dates and locale before contacting the upstream service.
            if not 6 <= (args.latest - args.earliest).days <= 365:
                raise ValueError("Release horizon must span 7 to 366 calendar days")
            region = args.region.upper()
            if len(region) != 2 or not region.isascii() or not region.isalpha():
                raise ValueError("Region must be a two-letter country code")
            app_id = extract_app_id(args.steam_url)

            async def run() -> LaunchRequest:
                async with httpx.AsyncClient(
                    timeout=20,
                    headers={
                        "User-Agent": "IndieLaunchIntelligence/0.1",
                        "Accept": "application/json",
                    },
                ) as http:
                    return await collect(
                        SteamClient(http),
                        app_ids=args.app_ids,
                        target_app_id=app_id,
                        earliest=args.earliest,
                        latest=args.latest,
                        region=region,
                    )

            result = asyncio.run(run())
        write_atomic(args.output, result.model_dump_json(indent=2))
    except (ValueError, OSError, SteamGameNotFound, SteamUpstreamError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
