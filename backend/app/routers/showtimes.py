from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..db import get_db
from ..models import Showtime, Theater
from ..normalize import normalize_title
from ..schemas import FilterOptions, ShowtimeOut, ShowtimePage

router = APIRouter(prefix="/showtimes", tags=["showtimes"])

DbSession = Annotated[Session, Depends(get_db)]


SortField = Literal[
    "start_time", "end_time", "last_updated", "movie_title", "movie_status", "theater_name"
]

SORT_COLUMNS = {
    "start_time": Showtime.start_time,
    "end_time": Showtime.end_time,
    "last_updated": Showtime.last_updated,
    "movie_title": Showtime.normalized_title,
    "movie_status": Showtime.movie_status,
    "theater_name": Theater.name,
}


def _utc_midnight(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)


def _allowed_theaters(user, theater_id: str | None) -> set[str]:
    allowed = set(user.theater_ids)
    if theater_id is not None:
        if theater_id not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Theater not accessible")
        allowed = {theater_id}
    return allowed


@router.get("/filter-options", response_model=FilterOptions)
def filter_options(
    db: DbSession, user: CurrentUser, theater_id: str | None = None
) -> FilterOptions:
    """Distinct values for the dropdown filters within the user's scope."""
    allowed = _allowed_theaters(user, theater_id)

    def distinct(column) -> list[str]:
        return db.scalars(
            select(column).where(Showtime.theater_id.in_(allowed)).distinct().order_by(column)
        ).all()

    return FilterOptions(
        formats=distinct(Showtime.format),
        languages=distinct(Showtime.language),
        ratings=distinct(Showtime.rating),
        auditoriums=distinct(Showtime.auditorium),
        movie_statuses=distinct(Showtime.movie_status),
    )


@router.get("", response_model=ShowtimePage)
def list_showtimes(
    db: DbSession,
    user: CurrentUser,
    theater_id: str | None = None,
    q: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    movie_status: str | None = None,
    format: str | None = None,
    language: str | None = None,
    rating: str | None = None,
    auditorium: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    sort: SortField = "start_time",
    order: Literal["asc", "desc"] = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ShowtimePage:
    # Users only ever see theaters they belong to; a user with no theaters
    # gets an empty page rather than an error.
    allowed = _allowed_theaters(user, theater_id)

    query = select(Showtime).where(Showtime.theater_id.in_(allowed))

    # Search runs against the normalized title so "spider man" finds
    # "Spider‑Man: Homecoming" and the trigram index can be used.
    if q and (needle := normalize_title(q)):
        query = query.where(Showtime.normalized_title.ilike(f"%{needle}%"))

    exact_filters = {
        Showtime.status: status_filter,
        Showtime.movie_status: movie_status,
        Showtime.format: format,
        Showtime.language: language,
        Showtime.rating: rating,
        Showtime.auditorium: auditorium,
    }
    for column, value in exact_filters.items():
        if value:
            query = query.where(column == value)

    # Date filters are inclusive calendar days in UTC.
    if start_date:
        query = query.where(Showtime.start_time >= _utc_midnight(start_date))
    if end_date:
        query = query.where(Showtime.start_time < _utc_midnight(end_date + timedelta(days=1)))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    if sort == "theater_name":
        query = query.join(Theater, Theater.id == Showtime.theater_id)
    sort_column = SORT_COLUMNS[sort]
    ordering = sort_column.desc() if order == "desc" else sort_column.asc()
    rows = db.scalars(
        query.order_by(ordering, Showtime.id)  # id breaks ties for stable paging
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return ShowtimePage(
        items=[ShowtimeOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
