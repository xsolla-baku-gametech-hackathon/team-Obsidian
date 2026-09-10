from fastapi import APIRouter
from ili_core.domain.launch import LaunchReport, LaunchRequest
from ili_core.recommendation.launch import recommend

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


@router.post("/recommendations", response_model=LaunchReport)
def launch_recommendations(payload: LaunchRequest) -> LaunchReport:
    """Analyze a validated market snapshot without upstream requests."""
    return recommend(payload)
