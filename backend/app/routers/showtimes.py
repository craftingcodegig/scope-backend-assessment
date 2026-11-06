from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..db import get_db
from ..models import Showtime
from ..schemas import ShowtimeOut, ShowtimePage

router = APIRouter(prefix="/showtimes", tags=["showtimes"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=ShowtimePage)
def list_showtimes(
    db: DbSession,
    user: CurrentUser,
    theater_id: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ShowtimePage:
    # Users only ever see theaters they belong to; a user with no theaters
    # gets an empty page rather than an error.
    allowed = set(user.theater_ids)
    if theater_id is not None:
        if theater_id not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Theater not accessible")
        allowed = {theater_id}

    query = select(Showtime).where(Showtime.theater_id.in_(allowed))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Showtime.start_time, Showtime.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return ShowtimePage(
        items=[ShowtimeOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
