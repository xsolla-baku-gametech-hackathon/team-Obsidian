from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ili_core.storage.catalog import CatalogUnavailable, SteamCatalog
from ili_pipeline.sources.steam import (
    InvalidSteamUrl,
    SteamClient,
    SteamGameNotFound,
    SteamUpstreamError,
)

from ili_api.routes import health, recommendations, steam
from ili_api.services.analysis import SteamAnalysisService
from ili_api.services.steam import SteamInspectionService
from ili_api.settings import Settings, get_settings


def create_app(
    *,
    settings: Settings | None = None,
    steam_service: SteamInspectionService | None = None,
    analysis_service: SteamAnalysisService | None = None,
) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        timeout = httpx.Timeout(config.steam_timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": config.steam_user_agent, "Accept": "application/json"},
        ) as client:
            app.state.steam_service = steam_service or SteamInspectionService(
                SteamClient(client), cache_ttl_seconds=config.steam_cache_ttl_seconds
            )
            app.state.analysis_service = analysis_service or SteamAnalysisService(
                SteamClient(client), SteamCatalog(config.catalog_path)
            )
            yield

    app = FastAPI(
        title="Indie Launch Intelligence API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any) -> Any:
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    def error(request: Request, status: int, code: str, message: str) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": message, "request_id": request_id}},
        )

    @app.exception_handler(InvalidSteamUrl)
    async def invalid_url(request: Request, exc: InvalidSteamUrl) -> JSONResponse:
        return error(request, 422, "invalid_steam_url", str(exc))

    @app.exception_handler(CatalogUnavailable)
    async def catalog_unavailable(request: Request, exc: CatalogUnavailable) -> JSONResponse:
        return error(request, 503, "catalog_unavailable", str(exc))

    @app.exception_handler(SteamGameNotFound)
    async def not_found(request: Request, exc: SteamGameNotFound) -> JSONResponse:
        return error(request, 404, "steam_game_not_found", str(exc))

    @app.exception_handler(SteamUpstreamError)
    async def upstream_error(request: Request, exc: SteamUpstreamError) -> JSONResponse:
        return error(request, 502, "steam_upstream_error", str(exc))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        return error(request, 422, "validation_error", str(first.get("msg", "Invalid request")))

    app.include_router(health.router)
    app.include_router(steam.router)
    app.include_router(recommendations.router)
    return app


app = create_app()
