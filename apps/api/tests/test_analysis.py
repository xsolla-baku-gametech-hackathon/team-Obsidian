import asyncio
import csv
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from ili_api.main import create_app
from ili_api.services.analysis import AnalyzeRequest, SteamAnalysisService
from ili_api.settings import Settings
from ili_core.domain.steam import (
    SteamGameMetadata,
    SteamGenre,
    SteamPlatforms,
    SteamPrice,
    SteamReleaseDate,
)
from ili_core.storage.catalog import SteamCatalog
from ili_pipeline.catalog import import_catalog, parse_labels
from ili_pipeline.sources.steam import SteamUpstreamError


@pytest.fixture
def catalog(tmp_path):
    source = tmp_path / "synthetic.csv"
    fields = [
        "app_id",
        "name",
        "release_date",
        "genres",
        "tags",
        "price_status",
        "positive",
        "negative",
        "short_description",
    ]
    release = (datetime.now(UTC).date() - timedelta(days=100)).isoformat()
    with source.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for app_id in range(1, 8):
            writer.writerow(
                {
                    "app_id": app_id,
                    "name": f"Synthetic {app_id}",
                    "release_date": release,
                    "genres": json.dumps([{"id": "2", "description": "Strategy"}]),
                    "tags": json.dumps({"Deckbuilding": 15}),
                    "price_status": "paid",
                    "positive": 10,
                    "negative": 2,
                    "short_description": "Build your deck",
                }
            )
    destination = tmp_path / "catalog.sqlite"
    import_catalog(source, destination)
    return SteamCatalog(destination)


class LiveClient:
    calls = 0

    async def fetch_metadata(self, app_id, **kwargs):
        self.calls += 1
        return SteamGameMetadata(
            app_id=app_id,
            name=f"Synthetic {app_id}",
            app_type="game",
            store_url=f"https://store.steampowered.com/app/{app_id}/",
            genres=[SteamGenre(id="2", name="Strategy")],
            short_description="Build your deck",
            platforms=SteamPlatforms(),
            is_free=False,
            release_date=SteamReleaseDate(
                coming_soon=False, raw=(datetime.now(UTC).date() - timedelta(days=100)).isoformat()
            ),
            price=SteamPrice(
                currency="USD", initial_minor=1999, final_minor=999, discount_percent=50
            ),
        )


def test_csv_formats_and_catalog(catalog):
    assert parse_labels('["Strategy"]') == ["Strategy"]
    assert parse_labels('{"Deckbuilding": 10}') == ["Deckbuilding"]
    assert parse_labels('[{"id":"2","description":"Strategy"}]') == ["Strategy"]
    assert catalog.metadata()["game_count"] == 7
    assert catalog.metadata()["source_observed_at"] is None
    target = catalog.get(1)
    assert target.review_count == 12
    assert len(catalog.candidates(target)) == 6
    assert all(game.app_id != 1 for game in catalog.candidates(target))


def test_full_analysis_route_uses_live_regular_prices_and_cache(catalog):
    upstream = LiveClient()
    service = SteamAnalysisService(upstream, catalog)
    with TestClient(create_app(analysis_service=service)) as client:
        first = client.post(
            "/api/v1/steam/games/analyze",
            json={"steam_url": "https://store.steampowered.com/app/1/"},
        )
        second = client.post(
            "/api/v1/steam/games/analyze",
            json={"steam_url": "https://store.steampowered.com/app/1/"},
        )
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["game"]["tags"] == ["Deckbuilding"]
    assert data["report"]["price"]["suggested_price_minor"] == 1999
    assert data["report"]["release"]["status"] == "insufficient_evidence"
    assert len(data["competitors"]) == 6
    assert data["catalog"]["game_count"] == 7
    assert second.json() == data
    assert upstream.calls == 7


def test_network_failure_preserves_catalog_results_without_invented_prices(catalog):
    class Offline:
        async def fetch_metadata(self, *args, **kwargs):
            raise SteamUpstreamError("offline")

    service = SteamAnalysisService(Offline(), catalog)
    result = asyncio.run(
        service.analyze(AnalyzeRequest(steam_url="https://store.steampowered.com/app/1/"))
    )
    assert result.target_source == "downloaded_catalog"
    assert len(result.competitors) == 6
    assert result.report.price.status == "insufficient_evidence"
    assert all(item.regular_price_minor is None for item in result.competitors)


def test_missing_catalog_and_invalid_request(tmp_path):
    settings = Settings(catalog_path=tmp_path / "absent.sqlite")
    with TestClient(create_app(settings=settings)) as client:
        response = client.post(
            "/api/v1/steam/games/analyze",
            json={"steam_url": "https://store.steampowered.com/app/1/"},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "catalog_unavailable"
        invalid = client.post(
            "/api/v1/steam/games/analyze", json={"steam_url": "https://example.com/app/1/"}
        )
        assert invalid.status_code == 422


def test_failed_import_keeps_previous_catalog(catalog, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("wrong,fields\n1,2\n")
    before = catalog.metadata()
    with pytest.raises(ValueError):
        import_catalog(bad, catalog.path)
    assert catalog.metadata() == before
