from typing import Annotated

from fastapi import APIRouter, Depends, Request
from ili_core.domain.auth import UserAccount
from ili_core.storage.users import UserStore

from ili_api.dependencies import active_premium_user, get_steam_service, get_user_store
from ili_api.schemas import InspectionMeta, InspectSteamGameRequest, InspectSteamGameResponse
from ili_api.services.analysis import AnalysisResponse, AnalyzeRequest
from ili_api.services.steam import SteamInspectionService

router = APIRouter(prefix="/api/v1/steam", tags=["steam"])


@router.post("/games/analyze", response_model=AnalysisResponse)
async def analyze_game(
    payload: AnalyzeRequest,
    request: Request,
    user: Annotated[UserAccount, Depends(active_premium_user)],
    user_store: Annotated[UserStore, Depends(get_user_store)],
) -> AnalysisResponse:
    result = await request.app.state.analysis_service.analyze(payload)
    user_store.save_report(
        user_id=user.id,
        steam_url=str(payload.steam_url),
        report_payload=result.model_dump(mode="json"),
    )
    return result


@router.post("/games/inspect", response_model=InspectSteamGameResponse)
async def inspect_game(
    payload: InspectSteamGameRequest,
    service: Annotated[SteamInspectionService, Depends(get_steam_service)],
    _user: Annotated[object, Depends(active_premium_user)],
) -> InspectSteamGameResponse:
    inspection, cache_hit = await service.inspect(payload)
    return InspectSteamGameResponse(
        data=inspection,
        meta=InspectionMeta(
            cache_hit=cache_hit,
            cache_ttl_seconds=service.cache_ttl_seconds,
        ),
    )
