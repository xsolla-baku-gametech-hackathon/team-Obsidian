from typing import Annotated

from fastapi import Depends, Header, Request
from ili_core.domain.auth import UserAccount
from ili_core.storage.users import AuthUnauthorized, UserStore

from ili_api.services.steam import SteamInspectionService


def get_steam_service(request: Request) -> SteamInspectionService:
    return request.app.state.steam_service


def get_user_store(request: Request) -> UserStore:
    return request.app.state.user_store


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization:
        raise AuthUnauthorized("Authentication is required.")
    token_type, _, token = authorization.partition(" ")
    if token_type.casefold() != "bearer" or not token:
        raise AuthUnauthorized("Use a bearer access token.")
    return token


def current_user(
    request: Request,
    token: Annotated[str, Depends(bearer_token)],
) -> UserAccount:
    return get_user_store(request).get_user_by_token(token)
