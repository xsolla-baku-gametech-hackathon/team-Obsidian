from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from ili_core.domain.auth import UserAccount
from ili_core.domain.marketplace import (
    KeyRequest,
    KeyRequestCollection,
    KeyRequestCreate,
    OwnershipApplication,
    OwnershipApplicationCollection,
    OwnershipApplicationCreate,
    OwnershipStatus,
    PublishedGame,
    PublishedGameCollection,
    PublishedGameCreate,
)
from ili_core.storage.users import AuthForbidden, UserStore
from pydantic import BaseModel, Field

from ili_api.dependencies import active_premium_user, get_user_store

router = APIRouter(prefix="/api/v1/marketplace", tags=["marketplace"])


class OwnershipReview(BaseModel):
    status: OwnershipStatus
    reviewed_notes: str | None = Field(default=None, max_length=1000)


def require_developer(user: UserAccount) -> None:
    if user.premium_role != "game_developer":
        raise AuthForbidden("A game developer account is required.")


def require_creator(user: UserAccount) -> None:
    if user.premium_role != "content_creator":
        raise AuthForbidden("A content creator account is required.")


def require_admin(
    request: Request,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    settings = request.app.state.settings
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise AuthForbidden("Platform owner access is required.")
    return None


@router.post("/ownership/applications", response_model=OwnershipApplication)
async def apply_for_ownership(
    payload: OwnershipApplicationCreate,
    user: Annotated[UserAccount, Depends(active_premium_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> OwnershipApplication:
    require_developer(user)
    return store.create_ownership_application(
        user_id=user.id,
        report_id=payload.report_id,
        studio_name=payload.studio_name,
        applicant_name=payload.applicant_name,
        applicant_title=payload.applicant_title,
        business_email=payload.business_email,
        company_website_url=payload.company_website_url,
        official_contact_url=payload.official_contact_url,
        steamworks_proof_url=payload.steamworks_proof_url,
        proof_url=payload.proof_url,
        proof_notes=payload.proof_notes,
    )


@router.get("/ownership/applications", response_model=OwnershipApplicationCollection)
async def list_ownership_applications(
    user: Annotated[UserAccount, Depends(active_premium_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> OwnershipApplicationCollection:
    require_developer(user)
    return OwnershipApplicationCollection(
        applications=store.list_ownership_applications(user_id=user.id)
    )


@router.post("/games", response_model=PublishedGame)
async def publish_game(
    payload: PublishedGameCreate,
    user: Annotated[UserAccount, Depends(active_premium_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> PublishedGame:
    require_developer(user)
    return store.publish_game(
        user_id=user.id,
        ownership_application_id=payload.ownership_application_id,
        pitch=payload.pitch,
        contact_email=payload.contact_email,
    )


@router.get("/games", response_model=PublishedGameCollection)
async def list_games(
    user: Annotated[UserAccount, Depends(active_premium_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> PublishedGameCollection:
    if user.premium_role not in {"content_creator", "game_developer"}:
        raise AuthForbidden("A premium account is required.")
    return PublishedGameCollection(games=store.list_published_games())


@router.post("/games/{game_id}/key-requests", response_model=KeyRequest)
async def request_key(
    game_id: int,
    payload: KeyRequestCreate,
    user: Annotated[UserAccount, Depends(active_premium_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> KeyRequest:
    require_creator(user)
    return store.create_key_request(
        creator_user_id=user.id,
        game_id=game_id,
        message=payload.message,
    )


@router.get("/key-requests/mine", response_model=KeyRequestCollection)
async def list_my_key_requests(
    user: Annotated[UserAccount, Depends(active_premium_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> KeyRequestCollection:
    require_creator(user)
    return KeyRequestCollection(requests=store.list_creator_key_requests(creator_user_id=user.id))


@router.get("/key-requests/incoming", response_model=KeyRequestCollection)
async def list_incoming_key_requests(
    user: Annotated[UserAccount, Depends(active_premium_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> KeyRequestCollection:
    require_developer(user)
    return KeyRequestCollection(requests=store.list_owner_key_requests(owner_user_id=user.id))


@router.get("/admin/ownership/applications", response_model=OwnershipApplicationCollection)
async def admin_list_ownership_applications(
    _: Annotated[None, Depends(require_admin)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> OwnershipApplicationCollection:
    return OwnershipApplicationCollection(applications=store.list_all_ownership_applications())


@router.post("/admin/ownership/applications/{application_id}", response_model=OwnershipApplication)
async def admin_review_ownership_application(
    application_id: int,
    payload: OwnershipReview,
    _: Annotated[None, Depends(require_admin)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> OwnershipApplication:
    return store.set_ownership_status(
        application_id=application_id,
        status=payload.status,
        reviewed_notes=payload.reviewed_notes,
    )
