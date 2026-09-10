"""Saved report history contracts."""

from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict


class ReportRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ReportSummary(ReportRecord):
    id: int
    steam_url: str
    app_id: int
    game_name: str
    target_source: str
    suggested_price_minor: int | None = None
    price_currency: str | None = None
    release_status: str
    competitor_count: int
    created_at: AwareDatetime


class SavedReport(ReportSummary):
    payload: dict[str, Any]


class ReportCollection(ReportRecord):
    reports: list[ReportSummary]
