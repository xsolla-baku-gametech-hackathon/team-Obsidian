import asyncio
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from ili_core.domain.steam import (
    SteamCategory,
    SteamGameInspection,
    SteamGameMetadata,
    SteamGenre,
    SteamLiveDataAvailability,
    SteamMovie,
    SteamPlatforms,
    SteamPrice,
    SteamReleaseDate,
    SteamRequirements,
    SteamReview,
    SteamReviewAuthor,
    SteamReviewSummary,
    SteamScreenshot,
)

STORE_HOSTS = {"store.steampowered.com", "www.store.steampowered.com"}
APP_PATH = re.compile(r"^/app/(?P<app_id>[1-9]\d*)(?:/|$)")


class InvalidSteamUrl(ValueError):
    pass


class SteamGameNotFound(Exception):
    pass


class SteamUpstreamError(Exception):
    pass


def extract_app_id(steam_url: str) -> int:
    """Extract an app ID without ever requesting the user-provided host."""
    try:
        parsed = urlparse(steam_url.strip())
    except ValueError as exc:
        raise InvalidSteamUrl("Invalid Steam Store URL") from exc

    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in STORE_HOSTS:
        raise InvalidSteamUrl("URL must use store.steampowered.com")

    match = APP_PATH.match(parsed.path)
    if not match:
        raise InvalidSteamUrl("URL must point to a Steam app page, for example /app/413150/")

    app_id = int(match.group("app_id"))
    if app_id > 4_294_967_295:
        raise InvalidSteamUrl("Steam App ID is outside the supported range")
    return app_id


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


class SteamClient:
    def __init__(self, http_client: httpx.AsyncClient, retries: int = 2) -> None:
        self._http = http_client
        self._retries = retries

    async def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self._retries + 1):
            try:
                response = await self._http.get(url, params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "retryable Steam response", request=response.request, response=response
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Steam response was not an object")
                return payload
            except (httpx.HTTPError, ValueError) as exc:
                if attempt == self._retries:
                    raise SteamUpstreamError("Steam did not return a usable response") from exc
                await asyncio.sleep(0.25 * (2**attempt))
        raise AssertionError("unreachable")

    async def fetch_game(
        self,
        app_id: int,
        *,
        country_code: str = "US",
        language: str = "english",
        review_language: str = "all",
        review_count: int = 100,
    ) -> SteamGameInspection:
        details_payload = await self._get_json(
            "https://store.steampowered.com/api/appdetails",
            {"appids": app_id, "cc": country_code.lower(), "l": language},
        )

        details_wrapper = details_payload.get(str(app_id))
        if not isinstance(details_wrapper, dict) or not details_wrapper.get("success"):
            raise SteamGameNotFound(f"Steam app {app_id} was not found or is unavailable")
        details = details_wrapper.get("data")
        if not isinstance(details, dict):
            raise SteamUpstreamError("Steam game metadata was missing")

        metadata = self._metadata(app_id, details)
        review_rows: list[Any] = []
        review_summary: SteamReviewSummary | None = None
        current_players: int | None = None
        unavailable_reasons: list[str] = []

        if metadata.release_date.coming_soon:
            unavailable_reasons.append("reviews are unavailable before release")
            unavailable_reasons.append("current players are unavailable before release")
        else:
            reviews_task = self._get_json(
                f"https://store.steampowered.com/appreviews/{app_id}",
                {
                    "json": 1,
                    "filter": "recent",
                    "language": review_language,
                    "purchase_type": "all",
                    "num_per_page": review_count,
                },
            )
            players_task = self._get_json(
                "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/",
                {"appid": app_id},
            )
            reviews_result, players_result = await asyncio.gather(
                reviews_task, players_task, return_exceptions=True
            )

            if isinstance(reviews_result, Exception):
                unavailable_reasons.append("Steam reviews endpoint did not return usable data")
            else:
                review_rows = reviews_result.get("reviews", [])
                summary = reviews_result.get("query_summary", {})
                if not isinstance(review_rows, list) or not isinstance(summary, dict):
                    unavailable_reasons.append("Steam review data was malformed")
                    review_rows = []
                else:
                    review_summary = SteamReviewSummary(
                        review_score=_integer(summary.get("review_score")),
                        review_score_description=summary.get("review_score_desc"),
                        total_positive=int(summary.get("total_positive", 0)),
                        total_negative=int(summary.get("total_negative", 0)),
                        total_reviews=int(summary.get("total_reviews", 0)),
                        returned_reviews=min(len(review_rows), review_count),
                    )

            if isinstance(players_result, Exception):
                unavailable_reasons.append(
                    "Steam current-player endpoint did not return usable data"
                )
            else:
                player_response = players_result.get("response", {})
                current_players = (
                    _integer(player_response.get("player_count"))
                    if isinstance(player_response, dict)
                    else None
                )
                if current_players is None:
                    unavailable_reasons.append("Steam current-player data was unavailable")

        return SteamGameInspection(
            metadata=metadata,
            reviews=[self._review(row) for row in review_rows[:review_count]],
            review_summary=review_summary,
            current_players=current_players,
            live_data=SteamLiveDataAvailability(
                reviews_available=review_summary is not None,
                current_players_available=current_players is not None,
                unavailable_reasons=unavailable_reasons,
            ),
            fetched_at=datetime.now(UTC),
        )

    @staticmethod
    def _metadata(app_id: int, row: dict[str, Any]) -> SteamGameMetadata:
        price = row.get("price_overview")
        release = row.get("release_date") or {}
        platforms = row.get("platforms") or {}
        metacritic = row.get("metacritic") or {}
        recommendations = row.get("recommendations") or {}
        return SteamGameMetadata(
            app_id=app_id,
            store_url=f"https://store.steampowered.com/app/{app_id}/",
            name=str(row.get("name") or f"Steam app {app_id}"),
            app_type=row.get("type"),
            short_description=row.get("short_description"),
            developers=list(row.get("developers") or []),
            publishers=list(row.get("publishers") or []),
            genres=[
                SteamGenre(id=str(item["id"]), name=str(item["description"]))
                for item in row.get("genres") or []
                if isinstance(item, dict) and "id" in item and "description" in item
            ],
            categories=[
                SteamCategory(id=int(item["id"]), name=str(item["description"]))
                for item in row.get("categories") or []
                if isinstance(item, dict) and "id" in item and "description" in item
            ],
            platforms=SteamPlatforms(
                windows=bool(platforms.get("windows")),
                mac=bool(platforms.get("mac")),
                linux=bool(platforms.get("linux")),
            ),
            release_date=SteamReleaseDate(
                coming_soon=bool(release.get("coming_soon")), raw=release.get("date") or None
            ),
            is_free=bool(row.get("is_free")),
            price=SteamPrice(
                currency=str(price["currency"]),
                initial_minor=int(price["initial"]),
                final_minor=int(price["final"]),
                discount_percent=int(price.get("discount_percent", 0)),
            )
            if isinstance(price, dict)
            else None,
            header_image=row.get("header_image"),
            website=row.get("website") or None,
            screenshots=SteamClient._screenshots(row.get("screenshots")),
            movies=SteamClient._movies(row.get("movies")),
            supported_languages=row.get("supported_languages") or None,
            pc_requirements=SteamClient._requirements(row.get("pc_requirements")),
            mac_requirements=SteamClient._requirements(row.get("mac_requirements")),
            linux_requirements=SteamClient._requirements(row.get("linux_requirements")),
            controller_support=row.get("controller_support") or None,
            content_descriptors=SteamClient._content_descriptors(row.get("content_descriptors")),
            metacritic_score=_integer(metacritic.get("score")),
            recommendation_count=_integer(recommendations.get("total")),
        )

    @staticmethod
    def _screenshots(value: Any) -> list[SteamScreenshot]:
        if not isinstance(value, list):
            return []
        return [
            SteamScreenshot(
                id=_integer(item.get("id")),
                thumbnail_url=item.get("path_thumbnail"),
                full_url=item.get("path_full"),
            )
            for item in value
            if isinstance(item, dict)
        ]

    @staticmethod
    def _movies(value: Any) -> list[SteamMovie]:
        if not isinstance(value, list):
            return []
        movies: list[SteamMovie] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            webm = item.get("webm") or {}
            mp4 = item.get("mp4") or {}
            movies.append(
                SteamMovie(
                    id=_integer(item.get("id")),
                    name=item.get("name"),
                    thumbnail_url=item.get("thumbnail"),
                    webm_url=webm.get("max") or webm.get("480") if isinstance(webm, dict) else None,
                    mp4_url=mp4.get("max") or mp4.get("480") if isinstance(mp4, dict) else None,
                    highlighted=bool(item.get("highlight")),
                )
            )
        return movies

    @staticmethod
    def _requirements(value: Any) -> SteamRequirements | None:
        if not isinstance(value, dict):
            return None
        minimum = value.get("minimum")
        recommended = value.get("recommended")
        if not minimum and not recommended:
            return None
        return SteamRequirements(
            minimum=str(minimum) if minimum else None,
            recommended=str(recommended) if recommended else None,
        )

    @staticmethod
    def _content_descriptors(value: Any) -> list[str]:
        if not isinstance(value, dict):
            return []
        notes = value.get("notes")
        ids = value.get("ids")
        descriptors = _strings(notes)
        if descriptors:
            return descriptors
        return [str(item) for item in ids] if isinstance(ids, list) else []

    @staticmethod
    def _review(row: dict[str, Any]) -> SteamReview:
        author = row.get("author") or {}
        return SteamReview(
            recommendation_id=str(row.get("recommendationid", "")),
            language=str(row.get("language", "unknown")),
            text=str(row.get("review", "")),
            voted_up=bool(row.get("voted_up")),
            votes_up=int(row.get("votes_up", 0)),
            votes_funny=int(row.get("votes_funny", 0)),
            weighted_vote_score=float(row.get("weighted_vote_score", 0)),
            comment_count=int(row.get("comment_count", 0)),
            steam_purchase=bool(row.get("steam_purchase")),
            received_for_free=bool(row.get("received_for_free")),
            written_during_early_access=bool(row.get("written_during_early_access")),
            created_at=_timestamp(row.get("timestamp_created")),
            updated_at=_timestamp(row.get("timestamp_updated")),
            author=SteamReviewAuthor(
                steam_id=str(author.get("steamid", "")),
                games_owned=_integer(author.get("num_games_owned")),
                reviews_written=_integer(author.get("num_reviews")),
                playtime_forever_minutes=_integer(author.get("playtime_forever")),
                playtime_last_two_weeks_minutes=_integer(author.get("playtime_last_two_weeks")),
                playtime_at_review_minutes=_integer(author.get("playtime_at_review")),
                last_played_at=_timestamp(author.get("last_played")),
            ),
        )
