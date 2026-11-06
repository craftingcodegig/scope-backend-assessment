from __future__ import annotations

from datetime import datetime

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
