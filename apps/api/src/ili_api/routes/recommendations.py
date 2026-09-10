from typing import Annotated

from fastapi import APIRouter, Depends
from ili_core.domain.launch import LaunchReport, LaunchRequest
from ili_core.recommendation.launch import recommend

from ili_api.dependencies import active_premium_user

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


@router.post("/recommendations", response_model=LaunchReport)
def launch_recommendations(
    payload: LaunchRequest,
    _user: Annotated[object, Depends(active_premium_user)],
) -> LaunchReport:
    """Analyze a validated market snapshot without upstream requests."""
    return recommend(payload)
