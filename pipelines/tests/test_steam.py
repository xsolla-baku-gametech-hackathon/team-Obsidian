import asyncio

import httpx
import pytest
from ili_pipeline.sources.steam import InvalidSteamUrl, SteamClient, extract_app_id


def test_extract_app_id_from_store_url() -> None:
    assert extract_app_id("https://store.steampowered.com/app/413150/Stardew_Valley/") == 413150


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/app/413150/",
        "https://store.steampowered.com.evil.example/app/413150/",
        "https://store.steampowered.com/search/?term=Stardew",
        "file:///app/413150/",
    ],
)
def test_extract_app_id_rejects_untrusted_or_non_game_urls(url: str) -> None:
    with pytest.raises(InvalidSteamUrl):
        extract_app_id(url)


def test_fetch_game_normalizes_metadata_reviews_and_players() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/appdetails":
            return httpx.Response(
                200,
                json={
                    "413150": {
                        "success": True,
                        "data": {
                            "type": "game",
                            "name": "Stardew Valley",
                            "short_description": "A farming game.",
                            "developers": ["ConcernedApe"],
                            "publishers": ["ConcernedApe"],
                            "genres": [{"id": "23", "description": "Indie"}],
                            "categories": [{"id": 2, "description": "Single-player"}],
                            "platforms": {"windows": True, "mac": True, "linux": True},
                            "release_date": {"coming_soon": False, "date": "Feb 26, 2016"},
                            "is_free": False,
                            "price_overview": {
                                "currency": "USD",
                                "initial": 1499,
                                "final": 1499,
                                "discount_percent": 0,
                            },
                            "screenshots": [
                                {
                                    "id": 1,
                                    "path_thumbnail": "https://cdn.example/thumb.jpg",
                                    "path_full": "https://cdn.example/full.jpg",
                                }
                            ],
                            "movies": [
                                {
                                    "id": 2,
                                    "name": "Launch Trailer",
                                    "thumbnail": "https://cdn.example/movie.jpg",
                                    "webm": {"480": "https://cdn.example/movie.webm"},
                                    "mp4": {"max": "https://cdn.example/movie.mp4"},
                                    "highlight": True,
                                }
                            ],
                            "supported_languages": "English<strong>*</strong>",
                            "pc_requirements": {"minimum": "Requires a 64-bit processor"},
                            "controller_support": "full",
                            "content_descriptors": {"notes": ["Fantasy Violence"]},
                            "recommendations": {"total": 900000},
                        },
                    }
                },
            )
        if request.url.path == "/appreviews/413150":
            assert request.url.params["num_per_page"] == "100"
            return httpx.Response(
                200,
                json={
                    "success": 1,
                    "query_summary": {
                        "review_score": 9,
                        "review_score_desc": "Overwhelmingly Positive",
                        "total_positive": 900,
                        "total_negative": 20,
                        "total_reviews": 920,
                    },
                    "reviews": [
                        {
                            "recommendationid": "1",
                            "author": {
                                "steamid": "123",
                                "num_games_owned": 10,
                                "num_reviews": 2,
                                "playtime_forever": 600,
                            },
                            "language": "english",
                            "review": "Excellent game",
                            "timestamp_created": 1_700_000_000,
                            "timestamp_updated": 1_700_000_000,
                            "voted_up": True,
                            "votes_up": 3,
                            "votes_funny": 0,
                            "weighted_vote_score": "0.8",
                            "comment_count": 0,
                            "steam_purchase": True,
                            "received_for_free": False,
                            "written_during_early_access": False,
                        }
                    ],
                },
            )
        if request.url.path.endswith("/GetNumberOfCurrentPlayers/v1/"):
            return httpx.Response(200, json={"response": {"result": 1, "player_count": 50000}})
        return httpx.Response(404)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            result = await SteamClient(http_client, retries=0).fetch_game(413150)
        assert result.metadata.name == "Stardew Valley"
        assert result.metadata.price is not None
        assert result.metadata.price.final_minor == 1499
        assert result.metadata.screenshots[0].full_url == "https://cdn.example/full.jpg"
        assert result.metadata.movies[0].mp4_url == "https://cdn.example/movie.mp4"
        assert result.metadata.pc_requirements is not None
        assert result.metadata.pc_requirements.minimum == "Requires a 64-bit processor"
        assert result.metadata.content_descriptors == ["Fantasy Violence"]
        assert result.live_data.reviews_available is True
        assert result.review_summary.returned_reviews == 1
        assert result.reviews[0].text == "Excellent game"
        assert result.current_players == 50000

    asyncio.run(run())


def test_fetch_upcoming_game_returns_metadata_without_live_metrics() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/api/appdetails":
            return httpx.Response(
                200,
                json={
                    "999999": {
                        "success": True,
                        "data": {
                            "type": "game",
                            "name": "Future Fixture",
                            "short_description": "Coming soon.",
                            "developers": ["Studio"],
                            "publishers": ["Publisher"],
                            "genres": [{"id": "1", "description": "Action"}],
                            "categories": [{"id": 2, "description": "Single-player"}],
                            "platforms": {"windows": True},
                            "release_date": {"coming_soon": True, "date": "Q4 2026"},
                            "is_free": False,
                            "header_image": "https://cdn.example/header.jpg",
                            "screenshots": [
                                {
                                    "id": 10,
                                    "path_thumbnail": "https://cdn.example/future-thumb.jpg",
                                    "path_full": "https://cdn.example/future-full.jpg",
                                }
                            ],
                        },
                    }
                },
            )
        return httpx.Response(500)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            result = await SteamClient(http_client, retries=0).fetch_game(999999)
        assert result.metadata.release_date.coming_soon is True
        assert result.metadata.release_date.raw == "Q4 2026"
        assert result.metadata.screenshots[0].full_url == "https://cdn.example/future-full.jpg"
        assert result.reviews == []
        assert result.review_summary is None
        assert result.current_players is None
        assert result.live_data.reviews_available is False
        assert result.live_data.current_players_available is False
        assert requested_paths == ["/api/appdetails"]

    asyncio.run(run())
