"""Partner CSV ingestion: parsing and cleaning."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime

from .models import Showtime
from .normalize import clean_text, normalize_title

REQUIRED_COLUMNS = (
    "theater_name",
    "movie_title",
    "auditorium",
    "start_time",
    "end_time",
    "language",
    "format",
    "rating",
)


class CsvError(ValueError):
    """Raised for a malformed upload; the message is safe to show to users."""


class MissingColumnsError(CsvError):
    """The header does not contain every required column."""

    def __init__(self, missing: list[str], headers: list[str]) -> None:
        super().__init__(f"Missing columns: {', '.join(missing)}")
        self.missing = missing
        self.headers = headers


def read_header_and_samples(content: str, limit: int = 3) -> tuple[list[str], list[list[str]]]:
    """Return the cleaned header row and up to `limit` data rows for inspection."""
    reader = csv.reader(io.StringIO(content.lstrip("﻿")))
    headers = [clean_text(name) for name in next(reader, [])]
    samples: list[list[str]] = []
    for row in reader:
        if any(cell.strip() for cell in row):
            samples.append([clean_text(cell) for cell in row])
        if len(samples) >= limit:
            break
    return headers, samples


@dataclass(frozen=True)
class CsvRow:
    movie_title: str
    normalized_title: str
    auditorium: str
    start_time: datetime
    end_time: datetime
    language: str
    format: str
    rating: str

    @property
    def key(self) -> tuple[str, datetime]:
        """Identity of a showtime within a theater: which movie, and when."""
        return (self.normalized_title, self.start_time)


def _parse_datetime(value: str, column: str, line: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CsvError(f"Line {line}: invalid {column} '{value}'") from None
    if parsed.tzinfo is None:
        raise CsvError(f"Line {line}: {column} must include a timezone")
    return parsed


def parse_csv(
    content: str, theater_name: str, column_mapping: dict[str, str] | None = None
) -> list[CsvRow]:
    """Parse a partner drop for one theater into cleaned, de-duplicated rows.

    Whitespace is trimmed and collapsed in every cell. Rows naming a different
    theater are rejected. When the same movie and start time appears more than
    once, the last row wins, so the result has at most one row per key.

    `column_mapping` renames partner headers to our column names, e.g.
    {"Film": "movie_title"}; it is how uploads with unfamiliar headers get in.
    """
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    rename = {clean_text(k).lower(): v for k, v in (column_mapping or {}).items()}

    def column(name: str) -> str:
        cleaned = clean_text(name).lower()
        return rename.get(cleaned, cleaned)

    header = [column(name) for name in reader.fieldnames or []]
    missing = [name for name in REQUIRED_COLUMNS if name not in header]
    if missing:
        raise MissingColumnsError(missing, [clean_text(n) for n in reader.fieldnames or []])

    expected_theater = clean_text(theater_name).casefold()
    rows: dict[tuple[str, datetime], CsvRow] = {}

    for line, raw in enumerate(reader, start=2):
        cells = {column(k): clean_text(v) for k, v in raw.items() if k}
        if not any(cells.values()):
            continue  # blank line
        if cells["theater_name"].casefold() != expected_theater:
            raise CsvError(f"Line {line}: theater '{cells['theater_name']}' does not match")
        if not cells["movie_title"]:
            raise CsvError(f"Line {line}: movie_title is empty")

        row = CsvRow(
            movie_title=cells["movie_title"],
            normalized_title=normalize_title(cells["movie_title"]),
            auditorium=cells["auditorium"],
            start_time=_parse_datetime(cells["start_time"], "start_time", line),
            end_time=_parse_datetime(cells["end_time"], "end_time", line),
            language=cells["language"],
            format=cells["format"],
            rating=cells["rating"],
        )
        rows[row.key] = row

    return list(rows.values())


# Columns a partner drop is allowed to change on an existing showtime,
# mapped to the camelCase names the UI shows in the preview.
UPDATABLE_FIELDS = {
    "movie_title": "movieTitle",
    "auditorium": "auditorium",
    "end_time": "endTime",
    "language": "language",
    "format": "format",
    "rating": "rating",
}


@dataclass(frozen=True)
class FieldDiff:
    field: str
    old_value: str
    new_value: str


@dataclass
class ScheduleDiff:
    adds: list[CsvRow]
    updates: list[tuple[Showtime, CsvRow, list[FieldDiff]]]
    archives: list[Showtime]


def _as_text(value: object) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)


def row_key(row: CsvRow) -> str:
    """Stable string identity for a CSV row, used to refer to it across requests."""
    return f"{row.normalized_title}|{row.start_time.isoformat()}"


def _field_changes(showtime: Showtime, row: CsvRow) -> list[FieldDiff]:
    changes = [
        FieldDiff(label, _as_text(getattr(showtime, field)), _as_text(getattr(row, field)))
        for field, label in UPDATABLE_FIELDS.items()
        if getattr(showtime, field) != getattr(row, field)
    ]
    if showtime.status != "active":
        changes.append(FieldDiff("status", showtime.status, "active"))
    return changes


def _pick_match(candidates: list[Showtime]) -> Showtime:
    # Prefer the active row; otherwise the most recently touched one.
    active = [row for row in candidates if row.status == "active"]
    pool = active or candidates
    return max(pool, key=lambda row: row.last_updated)


def diff_schedule(existing: list[Showtime], rows: list[CsvRow]) -> ScheduleDiff:
    """Compare the current schedule of one theater with a cleaned CSV drop.

    - A row whose key (normalized title + start time) is unknown is an add.
    - A row matching an existing showtime is an update when any updatable
      field differs or the showtime is not active (it gets re-activated).
    - Active showtimes missing from the drop are archived.
    """
    by_key: dict[tuple[str, datetime], list[Showtime]] = {}
    for showtime in existing:
        by_key.setdefault((showtime.normalized_title, showtime.start_time), []).append(showtime)

    diff = ScheduleDiff(adds=[], updates=[], archives=[])
    seen: set[tuple[str, datetime]] = set()

    for row in rows:
        seen.add(row.key)
        candidates = by_key.get(row.key)
        if not candidates:
            diff.adds.append(row)
            continue

        showtime = _pick_match(candidates)
        changes = _field_changes(showtime, row)
        if changes:
            diff.updates.append((showtime, row, changes))

    for key, candidates in by_key.items():
        if key not in seen:
            diff.archives.extend(row for row in candidates if row.status == "active")

    diff.archives.sort(key=lambda row: row.start_time)
    return diff


def apply_accepted_matches(diff: ScheduleDiff, accepted: dict[str, str]) -> ScheduleDiff:
    """Turn accepted (row key -> showtime id) pairs from an add plus an archive
    into a single update. Pairs that no longer line up are ignored."""
    if not accepted:
        return diff

    archives_by_id = {showtime.id: showtime for showtime in diff.archives}
    remaining_adds: list[CsvRow] = []
    for row in diff.adds:
        showtime = archives_by_id.get(accepted.get(row_key(row), ""))
        if showtime is None or showtime.start_time != row.start_time:
            remaining_adds.append(row)
            continue
        del archives_by_id[showtime.id]
        diff.archives.remove(showtime)
        diff.updates.append((showtime, row, _field_changes(showtime, row)))

    diff.adds = remaining_adds
    return diff
