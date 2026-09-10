from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from ili_core.domain.auth import (
    AuthSession,
    SubscriptionSelection,
    UserAccount,
    YouTubeVerification,
)
from ili_core.storage.users import UserStore
from pydantic import BaseModel, Field, field_validator

from ili_api.dependencies import current_user, get_user_store

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        email = value.strip().casefold()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return email


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()


@router.post("/signup", response_model=AuthSession, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignupRequest,
    store: Annotated[UserStore, Depends(get_user_store)],
) -> AuthSession:
    user = store.create_user(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
    )
    return store.create_session(user)


@router.post("/login", response_model=AuthSession)
async def login(
    payload: LoginRequest,
    store: Annotated[UserStore, Depends(get_user_store)],
) -> AuthSession:
    user = store.authenticate(email=payload.email, password=payload.password)
    return store.create_session(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    store: Annotated[UserStore, Depends(get_user_store)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if not authorization:
        return
    token_type, _, token = authorization.partition(" ")
    if token_type.casefold() == "bearer" and token:
        store.delete_session(token)


@router.get("/me", response_model=UserAccount)
async def me(user: Annotated[UserAccount, Depends(current_user)]) -> UserAccount:
    return user


@router.post("/subscription", response_model=UserAccount)
async def select_subscription(
    payload: SubscriptionSelection,
    user: Annotated[UserAccount, Depends(current_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> UserAccount:
    return store.select_subscription(user_id=user.id, plan=payload.plan, role=payload.role)


@router.post("/youtube/dev-verify", response_model=UserAccount)
async def verify_youtube_for_dev(
    payload: YouTubeVerification,
    user: Annotated[UserAccount, Depends(current_user)],
    store: Annotated[UserStore, Depends(get_user_store)],
) -> UserAccount:
    return store.verify_youtube(
        user_id=user.id,
        channel_id=payload.channel_id,
        google_subject=payload.google_subject,
    )
