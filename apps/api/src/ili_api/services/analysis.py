"""Steam URL -> catalog neighbors -> refreshed price evidence -> model inference."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from time import monotonic

from ili_core.domain.launch import (
    Competitor,
    Coverage,
    GameProfile,
    LaunchReport,
    LaunchRequest,
    MarketDataset,
    Record,
)
from ili_core.recommendation.launch import MIN_SIMILARITY, recommend, similarity
from ili_core.storage.catalog import CatalogGame, CatalogUnavailable, SteamCatalog
from ili_pipeline.launch import exact_release_date
from ili_pipeline.sources.steam import (
    SteamClient,
    SteamGameNotFound,
    SteamUpstreamError,
    extract_app_id,
)
from ili_pipeline.upcoming import load_snapshot
from pydantic import Field, model_validator
from starlette.concurrency import run_in_threadpool


class AnalyzeRequest(Record):
    steam_url: str = Field(min_length=20, max_length=500)
    country_code: str = Field(default="US", pattern=r"^[A-Z]{2}$")
    earliest_date: date | None = None
    latest_date: date | None = None

    @model_validator(mode="after")
    def dates(self):
        if (self.earliest_date is None) != (self.latest_date is None):
            raise ValueError("Provide both dates, or omit both for the next 90 days")
        if self.earliest_date is not None:
            if self.earliest_date < datetime.now(UTC).date():
                raise ValueError("Earliest date must be today or later")
            if not 6 <= (self.latest_date - self.earliest_date).days <= 365:
                raise ValueError("Release horizon must span 7 to 366 calendar days")
        return self


class CatalogMatch(Record):
    game: CatalogGame
    similarity: float
    regular_price_minor: int | None = None
    currency: str | None = None
    price_refreshed: bool = False


class AnalysisResponse(Record):
    game: GameProfile
    target_source: str
    catalog: dict
    competitors: list[CatalogMatch]
    report: LaunchReport
    refreshed_competitor_count: int
    earliest_date: date
    latest_date: date
    upcoming_catalog: dict = Field(default_factory=dict)


class SteamAnalysisService:
    def __init__(
        self,
        client: SteamClient,
        catalog: SteamCatalog,
        upcoming_path: Path | None = None,
        major_path: Path | None = None,
    ):
        self.client = client
        self.catalog = catalog
        self.upcoming_path = upcoming_path
        self.major_path = major_path
        self._cache: dict[tuple, tuple[float, AnalysisResponse]] = {}
        self._lock = asyncio.Lock()

    async def analyze(self, request: AnalyzeRequest) -> AnalysisResponse:
        # Bound upstream activity across concurrent reports in this API worker.
        async with self._lock:
            result = await self._analyze(request)
            return await self._with_upcoming(result, request)

    async def _analyze(self, request: AnalyzeRequest) -> AnalysisResponse:
        app_id = extract_app_id(request.steam_url)
        earliest = request.earliest_date or datetime.now(UTC).date()
        latest = request.latest_date or earliest + timedelta(days=89)
        try:
            meta = await run_in_threadpool(self.catalog.metadata)
        except CatalogUnavailable:
            return await self._metadata_only_report(app_id, request, earliest, latest)

        key = (app_id, request.country_code, earliest, latest, meta["dataset_id"])
        cached = self._cache.get(key)
        if cached and cached[0] > monotonic():
            return cached[1]
        stored = await run_in_threadpool(self.catalog.get, app_id)
        source = "steam_live"
        warnings = []
        try:
            async with asyncio.timeout(8):
                live = await self.client.fetch_metadata(app_id, country_code=request.country_code)
            if live.app_type != "game":
                raise SteamGameNotFound("Please use a full game's Steam link, not DLC or a demo.")
            target = GameProfile(
                app_id=app_id,
                name=live.name,
                genres=[genre.name for genre in live.genres],
                tags=stored.tags if stored else [],
                description=live.short_description or "",
                business_model="free" if live.is_free else "premium",
            )
        except (TimeoutError, SteamUpstreamError) as exc:
            if stored is None:
                raise SteamUpstreamError(
                    "Steam lookup failed and this game is not in the downloaded catalog. Try again."
                ) from exc
            target = GameProfile.model_validate(
                {name: getattr(stored, name) for name in GameProfile.model_fields}
            )
            source = "downloaded_catalog"
            warnings.append(
                "Live game lookup failed; game details came from the downloaded catalog."
            )

        def select():
            all_candidates = self.catalog.candidates(target)
            recent = self.catalog.candidates(
                target, released_since=datetime.now(UTC).date() - timedelta(days=730)
            )

            def ranked(rows):
                return sorted(
                    [(game, similarity(target, game)) for game in rows],
                    key=lambda item: (-item[1], item[0].app_id),
                )

            return (
                [
                    (game, score)
                    for game, score in ranked(all_candidates)
                    if score >= MIN_SIMILARITY
                    and game.release_date is not None
                    and game.release_date <= datetime.now(UTC).date()
                ][:20],
                [
                    (game, score)
                    for game, score in ranked(recent)
                    if score >= MIN_SIMILARITY and game.business_model == "premium"
                ][:12],
            )

        best, recent = await run_in_threadpool(select)
        # Refresh recent price comparables first, then other displayed matches (max 20 apps).
        refresh_candidates = {game.app_id: game for game, _ in [*recent, *best]}
        refresh_candidates = dict(list(refresh_candidates.items())[:20])
        refreshed: dict[int, Competitor] = {}
        semaphore = asyncio.Semaphore(3)

        async def refresh(game: CatalogGame):
            async with semaphore:
                try:
                    live = await self.client.fetch_metadata(
                        game.app_id, country_code=request.country_code
                    )
                    if live.app_type != "game":
                        return
                    release = exact_release_date(live.release_date.raw)
                    refreshed[game.app_id] = Competitor(
                        app_id=game.app_id,
                        name=live.name,
                        genres=[genre.name for genre in live.genres],
                        tags=game.tags,
                        description=live.short_description or "",
                        business_model="free" if live.is_free else "premium",
                        source=live.store_url,
                        observed_at=datetime.now(UTC),
                        release_date=release,
                        release_date_raw=live.release_date.raw,
                        date_precision="day" if release else "unknown",
                        coming_soon=live.release_date.coming_soon,
                        regular_price_minor=live.price.initial_minor if live.price else None,
                        currency=live.price.currency if live.price else "USD",
                        region=request.country_code,
                    )
                except (SteamGameNotFound, SteamUpstreamError, ValueError):
                    return

        try:
            async with asyncio.timeout(25):
                await asyncio.gather(*(refresh(game) for game in refresh_candidates.values()))
        except TimeoutError:
            warnings.append("Steam price refresh timed out; only completed observations were used.")
        if len(refreshed) < len(refresh_candidates):
            warnings.append("Some competitor prices could not be refreshed from Steam.")
        now = datetime.now(UTC)
        currencies = [
            game.currency for game in refreshed.values() if game.regular_price_minor is not None
        ]
        currency = max(sorted(set(currencies)), key=currencies.count) if currencies else "USD"
        report = recommend(
            LaunchRequest(
                game=target,
                earliest_date=earliest,
                latest_date=latest,
                region=request.country_code,
                currency=currency,
                dataset=MarketDataset(
                    dataset_id=meta["dataset_id"],
                    collected_at=now,
                    games=list(refreshed.values()),
                    coverage=Coverage(
                        horizon_start=earliest,
                        horizon_end=latest + timedelta(days=1),
                        discovery_complete=False,
                        discovery_method="downloaded_catalog_neighbors",
                        notes="Historical catalog search followed by live Steam metadata refresh. "
                        "This does not enumerate the upcoming release market.",
                    ),
                ),
            ),
            now=now,
        )
        report.warnings.extend(
            warnings
            + [
                "Catalog observation time is unknown. Import time is not source freshness; "
                "only prices refreshed from Steam are used for price advice.",
                "Tags and displayed review/player totals are from the downloaded catalog. "
                "Historical popularity is not used to predict upcoming competitor strength.",
            ]
        )
        # Show the catalog matches as well as all fresh pricing evidence used by the model.
        displayed = {game.app_id: (game, score) for game, score in [*best, *recent]}
        matches = []
        for game, score in displayed.values():
            live = refreshed.get(game.app_id)
            matches.append(
                CatalogMatch(
                    game=game,
                    similarity=round(score, 4),
                    regular_price_minor=live.regular_price_minor if live else None,
                    currency=live.currency
                    if live and live.regular_price_minor is not None
                    else None,
                    price_refreshed=live is not None and live.regular_price_minor is not None,
                )
            )
        matches.sort(key=lambda item: (-item.similarity, item.game.app_id))
        result = AnalysisResponse(
            game=target,
            target_source=source,
            catalog=meta,
            competitors=matches,
            report=report,
            refreshed_competitor_count=len(refreshed),
            earliest_date=earliest,
            latest_date=latest,
        )
        self._cache = {key: value for key, value in self._cache.items() if value[0] > monotonic()}
        if len(self._cache) >= 100:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = (monotonic() + 300, result)
        return result

    async def _metadata_only_report(
        self, app_id: int, request: AnalyzeRequest, earliest: date, latest: date
    ) -> AnalysisResponse:
        try:
            async with asyncio.timeout(8):
                live = await self.client.fetch_metadata(app_id, country_code=request.country_code)
        except (TimeoutError, SteamUpstreamError) as exc:
            raise CatalogUnavailable(
                "The Steam catalog has not been imported yet, and live Steam lookup failed."
            ) from exc
        if live.app_type != "game":
            raise SteamGameNotFound("Please use a full game's Steam link, not DLC or a demo.")

        now = datetime.now(UTC)
        target = GameProfile(
            app_id=app_id,
            name=live.name,
            genres=[genre.name for genre in live.genres],
            tags=[],
            description=live.short_description or "",
            business_model="free" if live.is_free else "premium",
        )
        metadata = {
            "dataset_id": "steam-live-metadata-only",
            "game_count": 0,
            "future_release_count": int(live.release_date.coming_soon),
            "source": "steam_live",
            "source_observed_at": now.isoformat(),
            "coverage_status": "catalog_missing",
        }
        report = recommend(
            LaunchRequest(
                game=target,
                earliest_date=earliest,
                latest_date=latest,
                region=request.country_code,
                currency=live.price.currency if live.price else "USD",
                dataset=MarketDataset(
                    dataset_id=metadata["dataset_id"],
                    collected_at=now,
                    games=[],
                    coverage=Coverage(
                        horizon_start=earliest,
                        horizon_end=latest + timedelta(days=1),
                        discovery_complete=False,
                        discovery_method="steam_live_metadata_only",
                        notes="The catalog database is missing, so this report only uses the "
                        "submitted Steam page metadata.",
                    ),
                ),
            ),
            now=now,
        )
        report.warnings.extend(
            [
                "The historical Steam catalog has not been imported yet. "
                "Historical matching and price comparison need the local catalog database.",
                "Live Steam metadata was available for the submitted game, but the report has "
                "no historical pricing sample.",
            ]
        )
        return AnalysisResponse(
            game=target,
            target_source="steam_live_metadata_only",
            catalog=metadata,
            competitors=[],
            report=report,
            refreshed_competitor_count=0,
            earliest_date=earliest,
            latest_date=latest,
        )

    async def _with_upcoming(
        self, result: AnalysisResponse, request: AnalyzeRequest
    ) -> AnalysisResponse:
        # Read on every request so a background refresh is visible without restarting the API.
        # Deep copy protects the historical response cache from mutation.
        result = result.model_copy(deep=True)
        dataset = (
            await run_in_threadpool(load_snapshot, self.upcoming_path, self.major_path)
            if self.upcoming_path
            else None
        )
        if dataset is None:
            result.upcoming_catalog = {"status": "missing", "game_count": 0}
            result.report.competitors = []
            result.report.release.explanation = (
                "The upcoming-release calendar is being prepared or is unavailable. "
                "No launch date can be recommended until it is loaded."
            )
            return result
        now = datetime.now(UTC)
        timing = await run_in_threadpool(
            recommend,
            LaunchRequest(
                game=result.game,
                earliest_date=result.earliest_date,
                latest_date=result.latest_date,
                region=request.country_code,
                dataset=dataset,
            ),
            now=now,
        )
        result.report.release = timing.release
        result.report.competitors = timing.competitors
        result.report.dataset_id = dataset.dataset_id
        result.report.generated_at = now
        result.report.warnings = list(
            dict.fromkeys(
                [
                    *result.report.warnings,
                    *timing.warnings,
                    dataset.coverage.notes,
                ]
            )
        )
        result.report.confidence = (
            "low" if timing.release.undated_competitor_count else timing.confidence
        )
        result.upcoming_catalog = {
            "status": "ready"
            if 0 <= (now - dataset.collected_at).total_seconds() <= 7 * 86400
            else "stale",
            "dataset_id": dataset.dataset_id,
            "game_count": len(dataset.games),
            "collected_at": dataset.collected_at.isoformat(),
            "discovery_complete": dataset.coverage.discovery_complete,
            "notes": dataset.coverage.notes,
        }
        return result
