"""Validated input/output contract for the explainable launch advisor."""

from datetime import date
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class GameProfile(Record):
    app_id: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=1, max_length=300)
    genres: list[str] = Field(default_factory=list, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=100)
    description: str = Field(default="", max_length=10000)
    business_model: Literal["premium", "free"] = "premium"
    playtime_hours: float | None = Field(default=None, gt=0, le=10000)


class Competitor(GameProfile):
    app_id: int = Field(gt=0)
    source: str = Field(min_length=1, max_length=500)
    observed_at: AwareDatetime
    release_date: date | None = None
    release_date_raw: str | None = None
    date_precision: Literal["day", "month", "quarter", "year", "unknown"] = "unknown"
    coming_soon: bool = False
    regular_price_minor: int | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    region: str = Field(default="US", pattern=r"^[A-Z]{2}$")
    attention_weight: float = Field(default=1, ge=1, le=20)
    attention_reason: str | None = None
    attention_source: str | None = Field(default=None, pattern=r"^https?://")
    # A comparable prelaunch signal only; never substitute postlaunch player counts.
    followers: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def exact_dates(self) -> Self:
        if self.attention_weight > 1 and not (self.attention_source and self.attention_reason):
            raise ValueError("Elevated attention requires a source URL and reason")
        if (self.date_precision == "day") != (self.release_date is not None):
            raise ValueError("Only day-precision releases may have a release_date")
        return self


class Coverage(Record):
    horizon_start: date
    horizon_end: date  # exclusive
    discovery_complete: bool = False
    discovery_method: str = Field(min_length=1, max_length=1000)
    notes: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.horizon_end <= self.horizon_start:
            raise ValueError("Coverage end must follow start")
        return self


class MarketDataset(Record):
    dataset_id: str = Field(min_length=1, max_length=200)
    collected_at: AwareDatetime
    coverage: Coverage
    games: list[Competitor] = Field(max_length=50000)

    @model_validator(mode="after")
    def unique_observations(self) -> Self:
        ids = [game.app_id for game in self.games]
        if len(ids) != len(set(ids)):
            raise ValueError("Dataset must contain one observation per app ID")
        if any(game.observed_at > self.collected_at for game in self.games):
            raise ValueError("Game observation cannot be later than dataset collection")
        return self


class LaunchRequest(Record):
    game: GameProfile
    dataset: MarketDataset
    earliest_date: date
    latest_date: date
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    region: str = Field(default="US", pattern=r"^[A-Z]{2}$")

    @model_validator(mode="after")
    def bounded_horizon(self) -> Self:
        days = (self.latest_date - self.earliest_date).days
        if not 6 <= days <= 365:
            raise ValueError("Release horizon must span 7 to 366 calendar days")
        return self


class MatchedCompetitor(Record):
    app_id: int
    name: str
    similarity: float
    shared_genres: list[str]
    shared_tags: list[str]
    release_date: date | None
    followers: int | None
    release_date_raw: str | None = None
    attention_weight: float = 1
    attention_reason: str | None = None
    attention_source: str | None = None


class ReleaseWindow(Record):
    start_date: date
    end_date: date  # inclusive
    rank: int
    competition_score: float
    observed_release_count: int
    evidence_app_ids: list[int]
    explanation: str


class ReleaseAdvice(Record):
    status: Literal["ranked", "insufficient_evidence"]
    best_date: date | None = None
    windows: list[ReleaseWindow] = Field(default_factory=list)
    high_risk_windows: list[ReleaseWindow] = Field(default_factory=list)
    score_method: Literal[
        "release_count", "similarity_and_followers", "upcoming_market_pressure"
    ] = "upcoming_market_pressure"
    undated_competitor_count: int = 0
    explanation: str


class PriceAdvice(Record):
    status: Literal["recommended", "insufficient_evidence", "free_to_play"]
    currency: str
    region: str
    suggested_price_minor: int | None = None
    lower_price_minor: int | None = None
    upper_price_minor: int | None = None
    evidence_app_ids: list[int] = Field(default_factory=list)
    explanation: str


class LaunchReport(Record):
    model_version: str = "launch-baseline-v2"
    policy_version: str = "launch-policy-v2"
    model_type: Literal["explainable_baseline"] = "explainable_baseline"
    dataset_id: str
    generated_at: AwareDatetime
    confidence: Literal["low", "medium"]
    competitors: list[MatchedCompetitor]
    release: ReleaseAdvice
    price: PriceAdvice
    recommendations: list[str]
    warnings: list[str]
