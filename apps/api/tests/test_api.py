from datetime import UTC, datetime

from fastapi.testclient import TestClient
from ili_api.main import create_app
from ili_api.settings import Settings
from ili_core.domain.steam import (
    SteamGameInspection,
    SteamGameMetadata,
    SteamLiveDataAvailability,
    SteamPlatforms,
    SteamReleaseDate,
    SteamReviewSummary,
)


class FakeSteamClient:
    calls = 0

    async def fetch_game(self, app_id: int, **_: object) -> SteamGameInspection:
        self.calls += 1
        return SteamGameInspection(
            metadata=SteamGameMetadata(
                app_id=app_id,
                store_url=f"https://store.steampowered.com/app/{app_id}/",
                name="Fixture Game",
                platforms=SteamPlatforms(windows=True),
                release_date=SteamReleaseDate(coming_soon=False, raw="Sep 10, 2026"),
                is_free=False,
            ),
            reviews=[],
            review_summary=SteamReviewSummary(
                total_positive=0,
                total_negative=0,
                total_reviews=0,
                returned_reviews=0,
            ),
            current_players=0,
            live_data=SteamLiveDataAvailability(
                reviews_available=True,
                current_players_available=True,
            ),
            fetched_at=datetime.now(UTC),
        )


def test_inspect_endpoint_and_cache() -> None:
    from ili_api.services.steam import SteamInspectionService

    fake_client = FakeSteamClient()
    service = SteamInspectionService(fake_client, cache_ttl_seconds=300)  # type: ignore[arg-type]
    app = create_app(settings=Settings(), steam_service=service)

    with TestClient(app) as client:
        payload = {"steam_url": "https://store.steampowered.com/app/413150/Stardew_Valley/"}
        first = client.post("/api/v1/steam/games/inspect", json=payload)
        second = client.post("/api/v1/steam/games/inspect", json=payload)

    assert first.status_code == 200
    assert first.json()["data"]["metadata"]["app_id"] == 413150
    assert first.json()["meta"]["cache_hit"] is False
    assert second.json()["meta"]["cache_hit"] is True
    assert fake_client.calls == 1


def test_inspect_rejects_non_steam_url() -> None:
    from ili_api.services.steam import SteamInspectionService

    app = create_app(
        settings=Settings(),
        steam_service=SteamInspectionService(FakeSteamClient()),  # type: ignore[arg-type]
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/steam/games/inspect",
            json={"steam_url": "https://example.com/app/413150/something"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_steam_url"
    assert response.headers["x-request-id"]
