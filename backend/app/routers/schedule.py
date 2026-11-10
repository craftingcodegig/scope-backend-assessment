from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..ai import AiClient, get_ai_client
from ..assistant import review_schedule, suggest_column_mapping, suggest_matches
from ..auth import AdminUser
from ..db import get_db
from ..ingest import (
    UPDATABLE_FIELDS,
    CsvError,
    MissingColumnsError,
    ScheduleDiff,
    apply_accepted_matches,
    diff_schedule,
    parse_csv,
    read_header_and_samples,
    row_key,
)
from ..models import Showtime, Theater
from ..schemas import (
    ApplyResult,
    AssistantOut,
    ColumnMappingOut,
    MatchSuggestionOut,
    PreviewAdd,
    PreviewArchive,
    PreviewChanges,
    PreviewFieldDiff,
    PreviewUpdate,
    ReviewWarningOut,
)

router = APIRouter(prefix="/theaters/{theater_id}/schedule", tags=["schedule"])

DbSession = Annotated[Session, Depends(get_db)]
Assistant = Annotated[AiClient, Depends(get_ai_client)]


def _theater_for_admin(db: Session, user, theater_id: str) -> Theater:
    theater = db.get(Theater, theater_id)
    if theater is None or theater_id not in user.theater_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Theater not found")
    return theater


def _read_upload(file: UploadFile) -> str:
    try:
        return file.file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File must be UTF-8 text")


def _parse_json_form(raw: str | None, what: str):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{what} must be JSON")


def _parse_rows(content: str, theater: Theater, ai: AiClient, column_mapping: dict | None):
    """Parse the CSV, asking the assistant for a header mapping if needed.

    Returns (rows, mapping used). The mapping is echoed back in the preview so
    the admin can see how unfamiliar headers were interpreted, and the
    frontend sends it back on apply so the same interpretation is used.
    """
    try:
        return parse_csv(content, theater.name, column_mapping), column_mapping
    except MissingColumnsError as error:
        if column_mapping is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error))
        headers, samples = read_header_and_samples(content)
        mapping = suggest_column_mapping(ai, headers, samples)
        if mapping is None:
            hint = " (the AI assistant could not map the headers)" if ai.enabled else ""
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{error}{hint}")
        try:
            return parse_csv(content, theater.name, mapping), mapping
        except CsvError as inner:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(inner))
    except CsvError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error))


def _compute_diff(
    db: Session, theater: Theater, content: str, ai: AiClient, column_mapping: dict | None
) -> tuple[ScheduleDiff, list[Showtime], dict | None]:
    rows, mapping = _parse_rows(content, theater, ai, column_mapping)
    existing = db.scalars(select(Showtime).where(Showtime.theater_id == theater.id)).all()
    return diff_schedule(existing, rows), existing, mapping


def _to_preview(diff: ScheduleDiff, assistant: AssistantOut) -> PreviewChanges:
    return PreviewChanges(
        adds=[
            PreviewAdd(row_key=row_key(row), **{f: getattr(row, f) for f in PreviewAdd.model_fields if f != "row_key"})
            for row in diff.adds
        ],
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
        assistant=assistant,
    )


@router.post("/preview", response_model=PreviewChanges)
def preview_schedule(
    theater_id: str, file: UploadFile, db: DbSession, user: AdminUser, ai: Assistant
) -> PreviewChanges:
    """Show what a partner CSV would change without touching the database."""
    theater = _theater_for_admin(db, user, theater_id)
    diff, existing, mapping = _compute_diff(db, theater, _read_upload(file), ai, None)

    # The two model calls only read the diff and are independent of each
    # other, so run them side by side instead of paying for both in sequence.
    with ThreadPoolExecutor(max_workers=2) as pool:
        suggestions_job = pool.submit(suggest_matches, ai, diff)
        review_job = pool.submit(review_schedule, ai, theater.name, diff, existing)
    suggestions = suggestions_job.result()
    review = review_job.result()

    assistant = AssistantOut(
        enabled=ai.enabled,
        provider=getattr(ai, "last_provider", None),
        column_mapping=[ColumnMappingOut(source=s, target=t) for s, t in (mapping or {}).items()],
        suggestions=[MatchSuggestionOut.model_validate(s) for s in suggestions],
        summary=review.summary if review else None,
        warnings=[ReviewWarningOut.model_validate(w) for w in review.warnings] if review else [],
    )
    return _to_preview(diff, assistant)


@router.post("/apply", response_model=ApplyResult)
def apply_schedule(
    theater_id: str,
    file: UploadFile,
    db: DbSession,
    user: AdminUser,
    ai: Assistant,
    column_mapping: Annotated[str | None, Form()] = None,
    accepted_matches: Annotated[str | None, Form()] = None,
) -> ApplyResult:
    """Apply a partner CSV in one transaction: insert, update and archive.

    `column_mapping` and `accepted_matches` are the assistant outputs the admin
    saw in the preview, sent back as JSON so apply uses the same decisions.
    """
    theater = _theater_for_admin(db, user, theater_id)
    mapping = _parse_json_form(column_mapping, "column_mapping")
    accepted = {
        item["rowKey"]: item["showtimeId"]
        for item in _parse_json_form(accepted_matches, "accepted_matches") or []
        if isinstance(item, dict) and "rowKey" in item and "showtimeId" in item
    }

    diff, _, _ = _compute_diff(db, theater, _read_upload(file), ai, mapping)
    diff = apply_accepted_matches(diff, accepted)
    now = datetime.now(timezone.utc)

    for row in diff.adds:
        db.add(
            Showtime(
                theater_id=theater.id,
                movie_title=row.movie_title,
                normalized_title=row.normalized_title,
                movie_status="draft",
                auditorium=row.auditorium,
                start_time=row.start_time,
                end_time=row.end_time,
                language=row.language,
                format=row.format,
                rating=row.rating,
                status="active",
                last_updated=now,
            )
        )
    for showtime, row, _ in diff.updates:
        for field in UPDATABLE_FIELDS:
            setattr(showtime, field, getattr(row, field))
        showtime.normalized_title = row.normalized_title
        showtime.status = "active"
        showtime.last_updated = now
    for showtime in diff.archives:
        showtime.status = "archived"
        showtime.last_updated = now

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Upload conflicts with an active showtime")

    return ApplyResult(
        added=len(diff.adds), updated=len(diff.updates), archived=len(diff.archives)
    )


@router.post("/archive-all", response_model=ApplyResult)
def archive_all(theater_id: str, db: DbSession, user: AdminUser) -> ApplyResult:
    """Clear a theater's schedule by archiving every active showtime."""
    theater = _theater_for_admin(db, user, theater_id)
    result = db.execute(
        update(Showtime)
        .where(Showtime.theater_id == theater.id, Showtime.status == "active")
        .values(status="archived", last_updated=datetime.now(timezone.utc))
    )
    db.commit()
    return ApplyResult(added=0, updated=0, archived=result.rowcount)
