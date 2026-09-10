from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SteamGenre(BaseModel):
    id: str
    name: str


class SteamCategory(BaseModel):
    id: int
    name: str


class SteamPrice(BaseModel):
    currency: str
    initial_minor: int
    final_minor: int
    discount_percent: int


class SteamPlatforms(BaseModel):
    windows: bool = False
    mac: bool = False
    linux: bool = False


class SteamScreenshot(BaseModel):
    id: int | None = None
    thumbnail_url: str | None = None
    full_url: str | None = None


class SteamMovie(BaseModel):
    id: int | None = None
    name: str | None = None
    thumbnail_url: str | None = None
    webm_url: str | None = None
    mp4_url: str | None = None
    highlighted: bool = False


class SteamRequirements(BaseModel):
    minimum: str | None = None
    recommended: str | None = None


class SteamReleaseDate(BaseModel):
    coming_soon: bool
    raw: str | None = None


class SteamGameMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: int
    store_url: str
    name: str
    app_type: str | None = None
    short_description: str | None = None
    developers: list[str] = Field(default_factory=list)
    publishers: list[str] = Field(default_factory=list)
    genres: list[SteamGenre] = Field(default_factory=list)
    categories: list[SteamCategory] = Field(default_factory=list)
    platforms: SteamPlatforms
    release_date: SteamReleaseDate
    is_free: bool
    price: SteamPrice | None = None
    header_image: str | None = None
    website: str | None = None
    screenshots: list[SteamScreenshot] = Field(default_factory=list)
    movies: list[SteamMovie] = Field(default_factory=list)
    supported_languages: str | None = None
    pc_requirements: SteamRequirements | None = None
    mac_requirements: SteamRequirements | None = None
    linux_requirements: SteamRequirements | None = None
    controller_support: str | None = None
    content_descriptors: list[str] = Field(default_factory=list)
    metacritic_score: int | None = None
    recommendation_count: int | None = None


class SteamReviewAuthor(BaseModel):
    steam_id: str
    games_owned: int | None = None
    reviews_written: int | None = None
    playtime_forever_minutes: int | None = None
    playtime_last_two_weeks_minutes: int | None = None
    playtime_at_review_minutes: int | None = None
    last_played_at: datetime | None = None


class SteamReview(BaseModel):
    recommendation_id: str
    language: str
    text: str
    voted_up: bool
    votes_up: int
    votes_funny: int
    weighted_vote_score: float
    comment_count: int
    steam_purchase: bool
    received_for_free: bool
    written_during_early_access: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    author: SteamReviewAuthor


class SteamReviewSummary(BaseModel):
    review_score: int | None = None
    review_score_description: str | None = None
    total_positive: int
    total_negative: int
    total_reviews: int
    returned_reviews: int


class SteamLiveDataAvailability(BaseModel):
    reviews_available: bool
    current_players_available: bool
    unavailable_reasons: list[str] = Field(default_factory=list)


class SteamGameInspection(BaseModel):
    metadata: SteamGameMetadata
    reviews: list[SteamReview]
    review_summary: SteamReviewSummary | None = None
    current_players: int | None = None
    live_data: SteamLiveDataAvailability
    fetched_at: datetime
