import asyncio
from dataclasses import dataclass
from time import monotonic

from ili_core.domain.steam import SteamGameInspection
from ili_pipeline.sources.steam import SteamClient, extract_app_id

from ili_api.schemas import InspectSteamGameRequest


@dataclass
class CacheEntry:
    expires_at: float
    inspection: SteamGameInspection


class SteamInspectionService:
    def __init__(self, client: SteamClient, cache_ttl_seconds: int = 300) -> None:
        self._client = client
        self._ttl = cache_ttl_seconds
        self._cache: dict[tuple[object, ...], CacheEntry] = {}
        self._lock = asyncio.Lock()

    @property
    def cache_ttl_seconds(self) -> int:
        return self._ttl

    async def inspect(self, request: InspectSteamGameRequest) -> tuple[SteamGameInspection, bool]:
        app_id = extract_app_id(request.steam_url)
        key = (
            app_id,
            request.country_code,
            request.language,
            request.review_language,
            request.review_count,
        )
        now = monotonic()
        entry = self._cache.get(key)
        if entry and entry.expires_at > now:
            return entry.inspection, True

        # Prevent duplicate upstream bursts inside one API worker.
        async with self._lock:
            now = monotonic()
            entry = self._cache.get(key)
            if entry and entry.expires_at > now:
                return entry.inspection, True
            inspection = await self._client.fetch_game(
                app_id,
                country_code=request.country_code,
                language=request.language,
                review_language=request.review_language,
                review_count=request.review_count,
            )
            self._cache[key] = CacheEntry(now + self._ttl, inspection)
            return inspection, False
