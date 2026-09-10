from typing import Annotated

from fastapi import APIRouter, Depends, Query
from ili_core.domain.auth import UserAccount
from ili_core.domain.reports import ReportCollection, SavedReport
from ili_core.storage.users import UserStore

from ili_api.dependencies import current_user, get_user_store

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("", response_model=ReportCollection)
async def list_reports(
    user: Annotated[UserAccount, Depends(current_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ReportCollection:
    return ReportCollection(reports=store.list_reports(user_id=user.id, limit=limit))


@router.get("/{report_id}", response_model=SavedReport)
async def get_report(
    report_id: int,
    user: Annotated[UserAccount, Depends(current_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> SavedReport:
    return store.get_report(user_id=user.id, report_id=report_id)
