from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import AdminUser
from ..db import get_db
from ..ingest import CsvError, ScheduleDiff, diff_schedule, parse_csv
from ..models import Showtime, Theater
from ..schemas import (
    PreviewAdd,
    PreviewArchive,
    PreviewChanges,
    PreviewFieldDiff,
    PreviewUpdate,
)

router = APIRouter(prefix="/theaters/{theater_id}/schedule", tags=["schedule"])

DbSession = Annotated[Session, Depends(get_db)]


def _theater_for_admin(db: Session, user, theater_id: str) -> Theater:
    theater = db.get(Theater, theater_id)
    if theater is None or theater_id not in user.theater_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Theater not found")
    return theater


def _compute_diff(db: Session, theater: Theater, file: UploadFile) -> ScheduleDiff:
    try:
        content = file.file.read().decode("utf-8-sig")
        rows = parse_csv(content, theater.name)
    except UnicodeDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File must be UTF-8 text")
    except CsvError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error))

    existing = db.scalars(select(Showtime).where(Showtime.theater_id == theater.id)).all()
    return diff_schedule(existing, rows)


def _to_preview(diff: ScheduleDiff) -> PreviewChanges:
    return PreviewChanges(
        adds=[PreviewAdd.model_validate(row) for row in diff.adds],
        updates=[
            PreviewUpdate(
                id=showtime.id,
                movie_title=showtime.movie_title,
                start_time=showtime.start_time,
                end_time=showtime.end_time,
                diffs=[PreviewFieldDiff.model_validate(change) for change in changes],
            )
            for showtime, _, changes in diff.updates
        ],
        archives=[PreviewArchive.model_validate(showtime) for showtime in diff.archives],
    )


@router.post("/preview", response_model=PreviewChanges)
def preview_schedule(
    theater_id: str, file: UploadFile, db: DbSession, user: AdminUser
) -> PreviewChanges:
    """Show what a partner CSV would change without touching the database."""
    theater = _theater_for_admin(db, user, theater_id)
    return _to_preview(_compute_diff(db, theater, file))
