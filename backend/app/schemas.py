from __future__ import annotations

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
