"""Marketplace contracts for developer/creator connection."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OwnershipStatus = Literal["pending", "approved", "rejected"]
KeyRequestStatus = Literal["pending", "approved", "rejected", "cancelled"]


class MarketplaceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class OwnershipApplication(MarketplaceRecord):
    id: int
    user_id: int
    report_id: int
    app_id: int
    game_name: str
    steam_url: str
    studio_name: str
    applicant_name: str
    applicant_title: str
    business_email: str
    company_website_url: str | None = None
    official_contact_url: str | None = None
    steamworks_proof_url: str | None = None
    proof_url: str | None = None
    proof_notes: str
    status: OwnershipStatus
    reviewed_notes: str | None = None
    created_at: datetime
    updated_at: datetime


class OwnershipApplicationCreate(MarketplaceRecord):
    report_id: int = Field(ge=1)
    studio_name: str = Field(min_length=2, max_length=160)
    applicant_name: str = Field(min_length=2, max_length=160)
    applicant_title: str = Field(min_length=2, max_length=120)
    business_email: str = Field(min_length=5, max_length=320)
    company_website_url: str | None = Field(default=None, max_length=500)
    official_contact_url: str | None = Field(default=None, max_length=500)
    steamworks_proof_url: str | None = Field(default=None, max_length=500)
    proof_url: str | None = Field(default=None, max_length=500)
    proof_notes: str = Field(min_length=30, max_length=2000)

    @field_validator("business_email")
    @classmethod
    def valid_business_email(cls, value: str) -> str:
        email = value.strip().casefold()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid business email address")
        if email.endswith(("@gmail.com", "@hotmail.com", "@outlook.com", "@yahoo.com")):
            raise ValueError("Use a studio or company email address")
        return email

    @field_validator(
        "company_website_url",
        "official_contact_url",
        "steamworks_proof_url",
        "proof_url",
    )
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        url = value.strip()
        if not url.startswith(("https://", "http://")):
            raise ValueError("Evidence links must start with http:// or https://")
        return url

    @model_validator(mode="after")
    def enough_evidence(self) -> "OwnershipApplicationCreate":
        has_strong_link = any(
            [self.company_website_url, self.official_contact_url, self.steamworks_proof_url]
        )
        if not has_strong_link:
            raise ValueError(
                "Provide at least one strong proof link: company website, official contact page, "
                "or Steamworks proof"
            )
        return self


class OwnershipApplicationCollection(MarketplaceRecord):
    applications: list[OwnershipApplication]


class PublishedGame(MarketplaceRecord):
    id: int
    owner_user_id: int
    ownership_application_id: int
    app_id: int
    game_name: str
    steam_url: str
    pitch: str
    contact_email: str | None = None
    created_at: datetime
    updated_at: datetime


class PublishedGameCreate(MarketplaceRecord):
    ownership_application_id: int = Field(ge=1)
    pitch: str = Field(min_length=10, max_length=2000)
    contact_email: str | None = Field(default=None, max_length=320)


class PublishedGameCollection(MarketplaceRecord):
    games: list[PublishedGame]


class KeyRequest(MarketplaceRecord):
    id: int
    game_id: int
    creator_user_id: int
    owner_user_id: int
    message: str
    status: KeyRequestStatus
    created_at: datetime
    updated_at: datetime


class KeyRequestCreate(MarketplaceRecord):
    message: str = Field(min_length=10, max_length=1200)


class KeyRequestCollection(MarketplaceRecord):
    requests: list[KeyRequest]
