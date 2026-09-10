import asyncio
from datetime import UTC, date, datetime

import pytest
from ili_core.domain.steam import (
    SteamGameInspection,
    SteamGameMetadata,
    SteamPlatforms,
    SteamPrice,
    SteamReleaseDate,
    SteamReviewSummary,
)
from ili_pipeline.launch import collect, exact_release_date, observation, write_atomic


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Sep 10, 2026", date(2026, 9, 10)),
        ("10 Sep, 2026", date(2026, 9, 10)),
        ("2026-09-10", date(2026, 9, 10)),
        ("September 2026", None),
        ("Q4 2026", None),
        ("Coming soon", None),
        (None, None),
        ("Feb 30, 2026", None),
    ],
)
def test_only_exact_dates(raw, expected):
    assert exact_release_date(raw) == expected


def inspection(app_id=1):
    return SteamGameInspection(
        metadata=SteamGameMetadata(
            app_id=app_id,
            name="Synthetic Steam fixture",
            app_type="game",
            store_url=f"https://store.steampowered.com/app/{app_id}/",
            platforms=SteamPlatforms(),
            release_date=SteamReleaseDate(coming_soon=False, raw="Jan 1, 2026"),
            is_free=False,
            price=SteamPrice(
                currency="USD", initial_minor=1999, final_minor=999, discount_percent=50
            ),
        ),
        reviews=[],
        review_summary=SteamReviewSummary(
            total_positive=0, total_negative=0, total_reviews=0, returned_reviews=0
        ),
        fetched_at=datetime.now(UTC),
    )


def test_observation_uses_regular_price_and_preserves_unknown_signals():
    record = observation(inspection(), "US")
    assert record.regular_price_minor == 1999
    assert record.followers is None
    assert record.tags == []


def test_collection_is_explicitly_sampled_and_failure_preserves_output(tmp_path):
    class Client:
        async def fetch_game(self, app_id, **kwargs):
            return inspection(app_id)

    result = asyncio.run(
        collect(
            Client(),
            app_ids=[2, 2],
            target_app_id=1,
            earliest=date(2026, 9, 10),
            latest=date(2026, 10, 10),
            region="US",
        )
    )
    assert result.game.app_id == 1
    assert [game.app_id for game in result.dataset.games] == [2]
    assert result.dataset.coverage.discovery_complete is False
    output = tmp_path / "request.json"
    write_atomic(output, result.model_dump_json())
    previous = output.read_text()

    class FailingClient:
        async def fetch_game(self, app_id, **kwargs):
            raise ValueError("Upstream unavailable")

    with pytest.raises(ValueError):
        failed = asyncio.run(
            collect(
                FailingClient(),
                app_ids=[2],
                target_app_id=1,
                earliest=date(2026, 9, 10),
                latest=date(2026, 10, 10),
                region="US",
            )
        )
        write_atomic(output, failed.model_dump_json())
    assert output.read_text() == previous
