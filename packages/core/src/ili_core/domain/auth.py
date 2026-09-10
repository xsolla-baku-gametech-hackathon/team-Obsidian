"""Authentication and account state contracts."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

UserRole = Literal["game_developer", "content_creator"]
SubscriptionPlan = Literal["starter", "pro", "studio"]
SubscriptionStatus = Literal["inactive", "active", "pending_youtube_verification"]


class AuthRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class UserAccount(AuthRecord):
    id: int
    email: str
    display_name: str | None = None
    premium_role: UserRole | None = None
    subscription_plan: SubscriptionPlan | None = None
    subscription_status: SubscriptionStatus = "inactive"
    youtube_channel_id: str | None = None
    youtube_google_subject: str | None = None
    youtube_verified_at: AwareDatetime | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class AuthSession(AuthRecord):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserAccount


class SubscriptionSelection(AuthRecord):
    plan: SubscriptionPlan
    role: UserRole


class YouTubeVerification(AuthRecord):
    channel_id: str = Field(min_length=3, max_length=200)
    google_subject: str = Field(min_length=3, max_length=300)
