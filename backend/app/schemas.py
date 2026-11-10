from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Base for responses: reads ORM objects and serializes as camelCase."""

    model_config = ConfigDict(
        from_attributes=True, alias_generator=to_camel, populate_by_name=True
    )


class TheaterOut(ApiModel):
    id: str
    name: str
    location: str
    timezone: str


class UserOut(ApiModel):
    id: str
    name: str
    email: str
    role: str
    theater_ids: list[str]


class ShowtimeOut(ApiModel):
    id: str
    theater_id: str
    movie_title: str
    movie_status: str
    auditorium: str
    start_time: datetime
    end_time: datetime
    language: str
    format: str
    rating: str
    status: str
    last_updated: datetime


class ShowtimePage(ApiModel):
    items: list[ShowtimeOut]
    total: int
    page: int
    page_size: int


class FilterOptions(ApiModel):
    formats: list[str]
    languages: list[str]
    ratings: list[str]
    auditoriums: list[str]
    movie_statuses: list[str]


MovieStatus = Literal["approved", "draft", "flagged", "needs-review"]
ShowtimeStatus = Literal["active", "inactive", "archived"]


class ShowtimeUpdate(ApiModel):
    movie_status: MovieStatus | None = None
    status: ShowtimeStatus | None = None


class PreviewAdd(ApiModel):
    row_key: str
    movie_title: str
    auditorium: str
    start_time: datetime
    end_time: datetime
    language: str
    format: str
    rating: str


class PreviewFieldDiff(ApiModel):
    field: str
    old_value: str
    new_value: str


class PreviewUpdate(ApiModel):
    id: str
    movie_title: str
    start_time: datetime
    end_time: datetime
    diffs: list[PreviewFieldDiff]


class PreviewArchive(ApiModel):
    id: str
    movie_title: str
    start_time: datetime
    end_time: datetime


class ColumnMappingOut(ApiModel):
    source: str
    target: str


class MatchSuggestionOut(ApiModel):
    row_key: str
    showtime_id: str
    csv_title: str
    existing_title: str
    confidence: float
    reason: str


class ReviewWarningOut(ApiModel):
    movie_title: str
    start_time: str
    message: str


class AssistantOut(ApiModel):
    """What the AI upload assistant contributed to a preview."""

    enabled: bool
    provider: str | None = None  # "gemini" or "anthropic", whichever answered
    column_mapping: list[ColumnMappingOut] = []
    suggestions: list[MatchSuggestionOut] = []
    summary: str | None = None
    warnings: list[ReviewWarningOut] = []


class PreviewChanges(ApiModel):
    adds: list[PreviewAdd]
    updates: list[PreviewUpdate]
    archives: list[PreviewArchive]
    assistant: AssistantOut


class ApplyResult(ApiModel):
    added: int
    updated: int
    archived: int
