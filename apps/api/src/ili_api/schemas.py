from typing import Annotated, Literal

from ili_core.domain.steam import SteamGameInspection
from pydantic import BaseModel, Field, field_validator


class InspectSteamGameRequest(BaseModel):
    steam_url: str = Field(min_length=20, max_length=500)
    country_code: str = Field(default="US", pattern=r"^[A-Za-z]{2}$")
    language: str = Field(default="english", min_length=2, max_length=32)
    review_language: str = Field(default="all", min_length=2, max_length=32)
    review_count: Annotated[int, Field(ge=1, le=100)] = 100

    @field_validator("country_code")
    @classmethod
    def uppercase_country(cls, value: str) -> str:
        return value.upper()


class InspectionMeta(BaseModel):
    source: Literal["steam"] = "steam"
    cache_hit: bool
    cache_ttl_seconds: int


class InspectSteamGameResponse(BaseModel):
    data: SteamGameInspection
    meta: InspectionMeta


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
