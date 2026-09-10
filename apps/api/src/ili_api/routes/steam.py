from typing import Annotated

from fastapi import APIRouter, Depends, Request

from ili_api.dependencies import get_steam_service
from ili_api.schemas import InspectionMeta, InspectSteamGameRequest, InspectSteamGameResponse
from ili_api.services.analysis import AnalysisResponse, AnalyzeRequest
from ili_api.services.steam import SteamInspectionService

router = APIRouter(prefix="/api/v1/steam", tags=["steam"])


@router.post("/games/analyze", response_model=AnalysisResponse)
async def analyze_game(payload: AnalyzeRequest, request: Request) -> AnalysisResponse:
    return await request.app.state.analysis_service.analyze(payload)


@router.post("/games/inspect", response_model=InspectSteamGameResponse)
async def inspect_game(
    payload: InspectSteamGameRequest,
    service: Annotated[SteamInspectionService, Depends(get_steam_service)],
) -> InspectSteamGameResponse:
    inspection, cache_hit = await service.inspect(payload)
    return InspectSteamGameResponse(
        data=inspection,
        meta=InspectionMeta(
            cache_hit=cache_hit,
            cache_ttl_seconds=service.cache_ttl_seconds,
        ),
    )
